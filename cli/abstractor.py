# src/abstractor.py
"""
Enterprise-Grade Multi-Language Code Abstractor

Features:
- Deterministic placeholders (stable hashing) for reproducible abstraction.
- Python: AST-based abstraction with regex fallback for robustness.
- Other languages: Regex-based abstraction for strings, numbers, comments.
- Noise injection (dummy vars, funcs, classes) for privacy layers.
- Chunking per function/class optional.
- Strictness levels: basic | strong | paranoid.
- Filesystem scanning with parallel processing.
- Safe, reversible restoration of original code.
- Structured JSON logging and optional Prometheus metrics.
- CLI for direct usage.
"""

from __future__ import annotations
import ast
import os
import re
import json
import time
import hashlib
import logging
import builtins
import random
import string
from pathlib import Path
from typing import Tuple, Dict, List, Optional, Callable, Any
import concurrent.futures
import argparse

# -------------------------------
# Optional Prometheus metrics
# -------------------------------
try:
    from prometheus_client import Counter, Histogram
    METRICS_ENABLED = True
    MET_FILES_PROCESSED = Counter("abstractor_files_processed_total", "Number of files processed by abstractor")
    MET_ERRORS = Counter("abstractor_errors_total", "Number of abstraction/restore errors")
    MET_DURATION = Histogram("abstractor_duration_seconds", "Time spent abstracting files")
except ImportError:
    METRICS_ENABLED = False

# -------------------------------
# Structured JSON Logger
# -------------------------------
logger = logging.getLogger("abstractor")
if not logger.handlers:
    handler = logging.StreamHandler()
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            payload = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
                "level": record.levelname,
                "name": record.name,
                "msg": record.getMessage(),
            }
            if hasattr(record, "extra") and isinstance(record.extra, dict): payload.update(record.extra)
            if record.exc_info: payload["exc"] = self.formatException(record.exc_info)
            return json.dumps(payload, default=str)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# -------------------------------
# Utilities
# -------------------------------
def _hex_digest(value: str, salt: Optional[str] = None, digest_size: int = 8) -> str:
    h = hashlib.blake2b(digest_size=digest_size)
    if salt: h.update(salt.encode("utf-8"))
    h.update(value.encode("utf-8"))
    return h.hexdigest()

def stable_placeholder(original: str, category: str, salt: Optional[str] = None) -> str:
    digest = _hex_digest(original, salt=salt, digest_size=6)
    safe_cat = re.sub(r"[^A-Za-z0-9]", "", category.upper())[:16]
    return f"<<{safe_cat}_{digest}>>"

def random_placeholder(prefix: str, length: int = 8) -> str:
    token = "".join(random.choices(string.ascii_letters + string.digits, k=length))
    return f"{prefix}_{token}"

# -------------------------------
# Language Detection
# -------------------------------
def detect_language(code: str, filename_hint: Optional[str] = None) -> str:
    if filename_hint:
        ext = Path(filename_hint).suffix.lower()
        if ext == ".py": return "python"
        if ext in (".js", ".jsx"): return "javascript"
        if ext in (".ts", ".tsx"): return "typescript"
        if ext == ".java": return "java"
    s = code.strip()
    if re.search(r"\b(def|class)\s+\w+\b|\bimport\s+\w+", s): return "python"
    if "function " in s or "console.log" in s:
        if re.search(r"\binterface\b|\btype\b", s): return "typescript"
        return "javascript"
    if "public class" in s: return "java"
    return "unknown"

# -------------------------------
# Python AST Abstractor
# -------------------------------
class PythonAbstractor(ast.NodeTransformer):
    def __init__(self, level: str = "basic", salt: Optional[str] = None, noise: bool = True, allow_list: Optional[Set[str]] = None):
        self.mapping: Dict[str, str] = {}
        self.reverse: Dict[str, str] = {}
        # This is the key change: we merge the user's list with the built-in ignores.
        self.ignore_names = set(dir(builtins)) | {"self", "cls"} | (allow_list or set())
        self.level = level
        self.salt = salt
        self.noise = noise

    def _map(self, original: str, category: str) -> str:
        if original in self.ignore_names: return original
        if original not in self.mapping:
            ph = stable_placeholder(original, category, salt=self.salt)
            base, suffix = ph, 0
            while ph in self.reverse:
                suffix += 1
                ph = f"{base}_{suffix}"
            self.mapping[original] = ph
            self.reverse[ph] = original
        return self.mapping[original]

    def visit_Name(self, node: ast.Name) -> ast.AST:
        node.id = self._map(node.id, "var")
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.name = self._map(node.name, "func")
        if ast.get_docstring(node):
            node.body[0] = ast.Expr(ast.Constant(value=stable_placeholder("DOCSTRING", "doc", salt=self.salt)))
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node.name = self._map(node.name, "class")
        if ast.get_docstring(node):
            node.body[0] = ast.Expr(ast.Constant(value=stable_placeholder("DOCSTRING", "doc", salt=self.salt)))
        self.generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:
        if node.arg: node.arg = self._map(node.arg, "param")
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, str) and node.value and not node.value.startswith("<<DOC"):
            ph = self._map(node.value, "str")
            return ast.copy_location(ast.Constant(value=ph), node)
        if isinstance(node.value, (int, float, complex)):
            ph = self._map(str(node.value), "num")
            return ast.copy_location(ast.Constant(value=ph), node)
        return node

# -------------------------------
# Regex Abstractor (JS/TS/Java/Unknown)
# -------------------------------
def regex_abstract(code: str, level: str = "basic", salt: Optional[str] = None) -> Tuple[str, Dict[str, str]]:
    mapping: Dict[str, str] = {}
    def make_ph(original: str, category: str) -> str:
        if original in mapping: return mapping[original]
        ph = stable_placeholder(original, category, salt=salt)
        base, suffix = ph, 0
        while ph in mapping.values():
            suffix += 1
            ph = f"{base}_{suffix}"
        mapping[original] = ph
        return ph

    string_pattern = re.compile(r"('''.*?'''|\"\"\".*?\"\"\"|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`)", re.DOTALL)
    code = string_pattern.sub(lambda m: make_ph(m.group(0), "STRING"), code)
    number_pattern = re.compile(r"\b-?\d+(\.\d+)?([eE][+-]?\d+)?\b")
    code = number_pattern.sub(lambda m: make_ph(m.group(0), "NUMBER"), code)
    code = re.sub(r"//[^\n]*|#([^\n]*)|/\*[\s\S]*?\*/", lambda m: make_ph(m.group(0), "COMMENT"), code)
    return code, mapping



# -------------------------------
# Registry & Orchestration
# -------------------------------
def _python_wrapper(code: str, level: str, salt: Optional[str], noise: bool, chunking: bool, allow_list: Optional[Set[str]] = None) -> Tuple[str, Dict[str, str]]:
    """Orchestrates abstraction for Python, handling chunking, noise, and fallbacks."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return regex_abstract(code, salt=salt)

    if chunking:
        abstracted_blocks: List[str] = []
        global_mapping: Dict[str, str] = {}
        for node in tree.body:
            block_ast = ast.Module(body=[node], type_ignores=[])
            # Pass the allow_list to the transformer
            transformer = PythonAbstractor(salt=salt, allow_list=allow_list)
            transformed_chunk = transformer.visit(block_ast)
            abstracted_code_chunk = ast.unparse(transformed_chunk)
            chunk_scrubbed, comment_map = regex_abstract(abstracted_code_chunk, salt=salt)
            abstracted_blocks.append(chunk_scrubbed)
            global_mapping.update(transformer.mapping)
            global_mapping.update(comment_map)
        abstracted_code = "\n\n".join(abstracted_blocks)
        mapping = global_mapping
    else:
        # Pass the allow_list to the transformer
        transformer = PythonAbstractor(salt=salt, allow_list=allow_list)
        transformed_tree = transformer.visit(tree)
        abstracted_code = ast.unparse(transformed_tree)
        abstracted_code, comment_map = regex_abstract(abstracted_code, salt=salt)
        mapping = {**transformer.mapping, **comment_map}

    if noise:
        noise_salt = (salt or "") + "_noise"
        if level in ("strong", "paranoid"):
            noise_func = f"def {stable_placeholder('noise_func', 'noise', noise_salt)}(): return {stable_placeholder('NOISE', 'str', noise_salt)}"
            abstracted_code = noise_func + "\n\n" + abstracted_code
        if level == "paranoid":
            noise_class = f"class {stable_placeholder('noise_class', 'noise', noise_salt)}: pass"
            abstracted_code = noise_class + "\n\n" + abstracted_code
    
    return abstracted_code, mapping


# --- MODIFIED: Simplified the REGISTRY as regex_abstract doesn't use level/noise ---
REGISTRY: Dict[str, Callable] = {
    "python": _python_wrapper,
    "javascript": regex_abstract,
    "typescript": regex_abstract,
    "java": regex_abstract,
    "unknown": regex_abstract,
}


# -------------------------------
# Core Functions
# -------------------------------
def abstract_single_file_text(
    code: str, filename_hint: Optional[str] = None, level: str = "basic", 
    salt: Optional[str] = None, noise: bool = True, chunking: bool = False,
    # --- ADD THE NEW PARAMETER ---
    allow_list: Optional[Set[str]] = None
) -> Tuple[str, Dict[str, str]]:
    lang = detect_language(code, filename_hint=filename_hint)
    abstractor = REGISTRY.get(lang, REGISTRY["unknown"])
    try:
        if lang == "python":
            # Pass the allow_list down to the python wrapper
            return abstractor(code, level, salt, noise, chunking, allow_list=allow_list)
        else:
            # Regex abstractor does not currently use an allow list, but could be modified in the future
            return abstractor(code, salt=salt)
    except Exception as e:
        if METRICS_ENABLED: MET_ERRORS.inc()
        logger.exception("Abstractor failed, falling back to basic regex", exc_info=e)
        return regex_abstract(code, salt=salt)

def restore_from_mapping(abstracted_code: str, mapping: Dict[str, str]) -> str:
    reverse = {v: k for k, v in mapping.items()}
    placeholders_sorted = sorted(reverse.keys(), key=len, reverse=True)
    restored = abstracted_code
    for ph in placeholders_sorted:
        restored = restored.replace(ph, reverse[ph])
    return "\n".join(line.rstrip() for line in restored.splitlines())

# -------------------------------
# Filesystem Scanning & Parallel Abstraction
# -------------------------------
def _abstract_file_worker(
    file_path: Path, level: str, salt: Optional[str], noise: bool, chunking: bool
) -> Dict[str, Any]:
    try:
        code = file_path.read_text(encoding="utf-8", errors="ignore")
        abstracted, mapping = abstract_single_file_text(
            code, filename_hint=str(file_path), level=level, salt=salt, noise=noise, chunking=chunking
        )
        return {"abstracted": abstracted, "mapping": mapping, "error": None}
    except Exception as e:
        return {"abstracted": None, "mapping": {}, "error": str(e)}

# --- FEATURE FIX: Added 'chunking' parameter and restored file discovery logic ---
def abstract_path(
    path: str, level: str = "basic", salt: Optional[str] = None, 
    workers: int = 4, follow_symlinks: bool = False, noise: bool = True, chunking: bool = False
) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    files: List[Path] = []
    p = Path(path)

    # --- BUG FIX: The file discovery loop was missing. It has been restored. ---
    if p.is_file():
        files.append(p)
    elif p.is_dir():
        for f in p.rglob("*"):
            if f.is_file() and (follow_symlinks or not f.is_symlink()):
                files.append(f)

    # --- OPTIMIZATION: Using ProcessPoolExecutor for CPU-bound work ---
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        process_file_partial = partial(
            _abstract_file_worker, level=level, salt=salt, noise=noise, chunking=chunking
        )
        future_to_path = {executor.submit(process_file_partial, f): f for f in files}
        for future in concurrent.futures.as_completed(future_to_path):
            file_path = future_to_path[future]
            try:
                results[str(file_path)] = future.result()
            
            except Exception as e:
                if METRICS_ENABLED: MET_ERRORS.inc()
                logger.exception(f"Worker failed for {file_path}", exc_info=e)
                results[str(file_path)] = {"abstracted": "", "mapping": {}, "error": str(e)}

# -------------------------------
# CLI
# -------------------------------
def _print_json(obj: Any):
    print(json.dumps(obj, indent=2, ensure_ascii=False))

def main_cli():
    parser = argparse.ArgumentParser(description="Enterprise Code Abstractor")
    parser.add_argument("path", help="File or directory to abstract")
    parser.add_argument("--level", choices=["basic", "strong", "paranoid"], default="basic")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--salt", type=str, default=None)
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--follow-symlinks", action="store_true")
    parser.add_argument("--noise", action="store_true", help="Inject dummy noise")
    args = parser.parse_args()

    start = time.time()
    results = abstract_path(args.path, level=args.level, salt=args.salt, workers=args.workers, follow_symlinks=args.follow_symlinks, noise=args.noise)
    duration = time.time() - start

    if METRICS_ENABLED: MET_DURATION.observe(duration)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Abstracted results written to {args.out}")
    else:
        _print_json(results)

if __name__ == "__main__":
    main_cli()
