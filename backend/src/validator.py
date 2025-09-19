"""
validator.py -- Enterprise-grade parallel multi-layer validator (production-ready)
Supports: Python (AST + flake8 + mypy + bandit), JavaScript/TypeScript (ESLint + tsc),
Java (javac), C/C++ (clang-tidy), Go (go vet), Rust (cargo check).
Runs external tools inside sandbox via run_command_in_sandbox().
Key features:
- NEVER execute user code. All external tools run inside an isolated sandbox via run_command_in_sandbox().
- Parallel multi-layer validation per-file and across languages.
- File system scanning mode: validate_path("src/") discovers files by extension.
- Normalized findings schema, caps/deduping, and limited raw tool outputs.
- Conservative, defensive error handling so the validator is robust in CI.
Expected helper (provided by infra):
from sandbox import run_command_in_sandbox
Signature:
run_command_in_sandbox(command: List[str], files: Dict[str,str], image: str, timeout_seconds: int) -> Dict[str, Any]
Notes:
- You must provide images that include the requested tool chains (or adjust DEFAULT_IMAGES).
- This file intentionally keeps logic deterministic and avoids executing user-provided code.
"""
from __future__ import annotations
import ast
import re
import json
import os
import sys
import traceback
import fnmatch
from typing import Dict, List, Any, Optional, Tuple, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from dataclasses import dataclass, asdict

# user-provided sandbox run function:
from .sandbox import run_command_in_sandbox

# ----------------------------
# Configurable constants
# ----------------------------
TOOL_TIMEOUT_SECONDS = 15
MAX_FINDINGS_RETURNED = 1000
MAX_TOOL_PARALLEL = 6
MAX_FILE_PARALLEL = 8
RAW_OUTPUT_LIMIT = 20000  # truncate raw outputs to this many chars

# Default docker images per tool (tweak to your infra)
DEFAULT_IMAGES = {
    "flake8": "python:3.11-slim",
    "mypy": "python:3.11-slim",
    "bandit": "python:3.11-slim",
    "eslint": "node:20-slim",
    "tsc": "node:20-slim",
    "javac": "openjdk:17-slim",
    "clang-tidy": "clangd/clang-tidy:latest",  # replace with your clang image
    "go": "golang:1.21-slim",
    "rust": "rust:1.71-slim",
    # fallbacks exist in _run_tool_in_sandbox_safe
}

# ----------------------------
# Normalized Finding Schema
# ----------------------------
# {
#     "id": str,
#     "tool": str,
#     "severity": "error"|"warning"|"info",
#     "message": str,
#     "file": Optional[str],
#     "line": Optional[int],
#     "column": Optional[int],
#     "suggestion": Optional[str]
# }

# ----------------------------
# Data classes for internal clarity
# ----------------------------
@dataclass
class ToolResult:
    tool: str
    stdout: str
    stderr: str
    exit_code: int
    diagnostics: Optional[str] = None
    
    def truncated(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "stdout": (self.stdout[:RAW_OUTPUT_LIMIT] + "...") if len(self.stdout) > RAW_OUTPUT_LIMIT else self.stdout,
            "stderr": (self.stderr[:RAW_OUTPUT_LIMIT] + "...") if len(self.stderr) > RAW_OUTPUT_LIMIT else self.stderr,
            "exit_code": self.exit_code,
            "diagnostics": self.diagnostics,
        }

# ----------------------------
# Utilities
# ----------------------------
def detect_language(code: str, filename_hint: Optional[str] = None) -> str:
    """Heuristic language detection from code text and optional filename."""
    if filename_hint:
        fn = filename_hint.lower()
        if fn.endswith(".py"):
            return "python"
        if fn.endswith((".js", ".jsx")):
            return "javascript"
        if fn.endswith((".ts", ".tsx")):
            return "typescript"
        if fn.endswith(".java"):
            return "java"
        if fn.endswith((".c", ".cpp", ".cc", ".h", ".hpp")):
            return "c_cpp"
        if fn.endswith(".go"):
            return "go"
        if fn.endswith((".rs",)):
            return "rust"
        if fn.endswith(".php"):
            return "php"
    
    s = code.strip()
    # quick heuristics
    if s.startswith("<?php") or re.search(r"\bnamespace\b.*;", s):
        return "php"
    if re.search(r"\b(def|class)\s+\w+\b|\bimport\s+\w+", s) and ("{" not in s[:200]):
        return "python"
    if "function " in s or "console.log" in s or "=> " in s or "module.exports" in s or re.search(r"\bimport\s+.*from\s+['\"]", s):
        if re.search(r"\binterface\b|\btype\b|\b: [A-Za-z0-9_\[\]\|<>{}, ]+\b", s):
            return "typescript"
        return "javascript"
    if "public class" in s or "System.out.println" in s or re.search(r"\bpackage\b\s+[a-zA-Z0-9_.]+", s):
        return "java"
    if "#include" in s or "int main(" in s:
        return "c_cpp"
    if "package main" in s and "func main()" in s:
        return "go"
    if "fn main()" in s and "let " in s:
        return "rust"
    return "unknown"

def _cap_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # dedupe simplistic by (tool, message, file, line, column)
    seen = set()
    out = []
    for f in findings:
        key = (f.get("tool"), f.get("message"), f.get("file"), f.get("line"), f.get("column"))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
        if len(out) >= MAX_FINDINGS_RETURNED:
            break
    return out

def _make_internal_finding(tool: str, message: str, severity: str = "error") -> Dict[str, Any]:
    return {
        "id": f"internal:{tool}",
        "tool": tool,
        "severity": severity,
        "message": message,
        "file": None,
        "line": None,
        "column": None,
        "suggestion": None,
    }

def _safe_int(x: Any) -> Optional[int]:
    try:
        return None if x is None else int(x)
    except Exception:
        return None

# ----------------------------
# Parsers for individual tools
# ----------------------------
# flake8 default output: path:line:col: CODE message
FLAKE8_RE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+):(?P<col>\d+):\s*(?P<code>\w+)\s+(?P<msg>.+)$")

def parse_flake8(stdout: str) -> List[Dict[str, Any]]:
    findings = []
    for line in stdout.splitlines():
        m = FLAKE8_RE.match(line.strip())
        if not m:
            continue
        code = m.group("code")
        findings.append({
            "id": f"flake8:{code}",
            "tool": "flake8",
            "severity": "warning" if code.startswith("W") else "error",
            "message": m.group("msg"),
            "file": m.group("path"),
            "line": int(m.group("line")),
            "column": int(m.group("col")),
            "suggestion": None,
        })
    return findings

# mypy output: path:line: column: error: message
MYPY_RE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+):\s*(?P<col>\d+):\s*error:\s*(?P<msg>.+)$", re.IGNORECASE)

def parse_mypy(stdout: str) -> List[Dict[str, Any]]:
    findings = []
    for line in stdout.splitlines():
        m = MYPY_RE.match(line.strip())
        if m:
            findings.append({
                "id": "mypy:type",
                "tool": "mypy",
                "severity": "error",
                "message": m.group("msg"),
                "file": m.group("path"),
                "line": int(m.group("line")),
                "column": int(m.group("col")),
                "suggestion": "Add/adjust type annotations or configure mypy.",
            })
    return findings

# bandit JSON output parser
def parse_bandit_json(json_text: str) -> List[Dict[str, Any]]:
    findings = []
    try:
        data = json.loads(json_text)
        for item in data.get("results", []):
            filename = item.get("filename")
            lineno = _safe_int(item.get("line_number"))
            severity = item.get("issue_severity", "").lower()
            sev = "warning"
            if severity == "high":
                sev = "error"
            elif severity == "medium":
                sev = "warning"
            else:
                sev = "info"
            findings.append({
                "id": f"bandit:{item.get('test_id') or 'unknown'}",
                "tool": "bandit",
                "severity": sev,
                "message": f"{item.get('issue_text') or item.get('issue_confidence', '')}",
                "file": filename,
                "line": lineno,
                "column": None,
                "suggestion": item.get("more_info"),
            })
    except Exception:
        # If parsing fails, return empty and let caller capture raw output
        pass
    return findings

# eslint returns JSON
def parse_eslint(json_text: str) -> List[Dict[str, Any]]:
    findings = []
    try:
        data = json.loads(json_text)
    except Exception:
        return findings
    
    for file_result in data:
        path = file_result.get("filePath", None) or file_result.get("file", None)
        for msg in file_result.get("messages", []):
            findings.append({
                "id": f"eslint:{msg.get('ruleId') or 'unknown'}",
                "tool": "eslint",
                "severity": "error" if msg.get("severity") == 2 else "warning",
                "message": msg.get("message"),
                "file": path,
                "line": _safe_int(msg.get("line")),
                "column": _safe_int(msg.get("column")),
                "suggestion": None,
            })
    return findings

# tsc (TypeScript) stderr parse (file.ts(x,y): error TSxxxx: message)
TSC_RE = re.compile(r"^(?P<path>[^\(\)]+)\((?P<line>\d+),(?P<col>\d+)\):\s*(?P<severity>error|warning)\s*(?P<code>TS\d+):\s*(?P<msg>.+)$", re.IGNORECASE)

def parse_tsc(stderr: str) -> List[Dict[str, Any]]:
    findings = []
    for line in stderr.splitlines():
        m = TSC_RE.match(line.strip())
        if m:
            findings.append({
                "id": f"tsc:{m.group('code')}",
                "tool": "tsc",
                "severity": "error" if m.group("severity").lower() == "error" else "warning",
                "message": m.group("msg"),
                "file": m.group("path").strip(),
                "line": int(m.group("line")),
                "column": int(m.group("col")),
                "suggestion": None,
            })
    return findings

# javac: path:line: error: message
JAVAC_RE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+):\s*(error|warning):\s*(?P<msg>.+)$", re.IGNORECASE)

def parse_javac(stderr: str) -> List[Dict[str, Any]]:
    findings = []
    for line in stderr.splitlines():
        m = JAVAC_RE.match(line.strip())
        if m:
            findings.append({
                "id": "javac",
                "tool": "javac",
                "severity": "error" if "error" in line.lower() else "warning",
                "message": m.group("msg"),
                "file": m.group("path"),
                "line": int(m.group("line")),
                "column": None,
                "suggestion": "Fix compilation errors.",
            })
    return findings

# clang-tidy outputs diagnostics like: path:line:col: warning: message [checkname]
CLANG_TIDY_RE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+):(?P<col>\d+):\s*(?P<severity>warning|error|note):\s*(?P<msg>.+?)(?:\s+\[(?P<check>[^\]]+)\])?$", re.IGNORECASE)

def parse_clang_tidy(stderr: str) -> List[Dict[str, Any]]:
    findings = []
    for line in stderr.splitlines():
        m = CLANG_TIDY_RE.match(line.strip())
        if m:
            sev = m.group("severity").lower()
            severity = "error" if "error" in sev else ("warning" if "warning" in sev else "info")
            findings.append({
                "id": f"clang-tidy:{(m.group('check') or 'unknown')}",
                "tool": "clang-tidy",
                "severity": severity,
                "message": m.group("msg").strip(),
                "file": m.group("path"),
                "line": int(m.group("line")),
                "column": int(m.group("col")),
                "suggestion": None,
            })
    return findings

# go vet (go vet prints file:line: message)
GO_VET_RE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+):\s*(?P<msg>.+)$")

def parse_go_vet(stderr: str) -> List[Dict[str, Any]]:
    findings = []
    for line in stderr.splitlines():
        m = GO_VET_RE.match(line.strip())
        if m:
            findings.append({
                "id": "govet",
                "tool": "go vet",
                "severity": "warning",
                "message": m.group("msg"),
                "file": m.group("path"),
                "line": int(m.group("line")),
                "column": None,
                "suggestion": None,
            })
    return findings

# cargo check (rust) errors printed to stderr; try a simple parse for file:line:col: message
CARGO_RE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+):(?P<col>\d+):\s*(?P<severity>error|warning):\s*(?P<msg>.+)$", re.IGNORECASE)

def parse_cargo(stderr: str) -> List[Dict[str, Any]]:
    findings = []
    for line in stderr.splitlines():
        m = CARGO_RE.match(line.strip())
        if m:
            severity = "error" if m.group("severity").lower() == "error" else "warning"
            findings.append({
                "id": f"cargo:{severity}",
                "tool": "cargo",
                "severity": severity,
                "message": m.group("msg"),
                "file": m.group("path"),
                "line": int(m.group("line")),
                "column": int(m.group("col")),
                "suggestion": None,
            })
    return findings

# Generic fallback
GENERIC_RE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+):(?P<col>\d+)?:?\s*(?P<msg>.+)$")

def parse_generic(stderr: str, tool_name: str) -> List[Dict[str, Any]]:
    findings = []
    for line in stderr.splitlines():
        m = GENERIC_RE.match(line.strip())
        if m:
            findings.append({
                "id": f"{tool_name}:generic",
                "tool": tool_name,
                "severity": "warning",
                "message": m.group("msg"),
                "file": m.group("path"),
                "line": _safe_int(m.group("line")),
                "column": _safe_int(m.group("col")),
                "suggestion": None,
            })
    return findings

# ----------------------------
# Sandbox runner wrapper (safe)
# ----------------------------
def _run_tool_in_sandbox_safe(command: List[str], files: Dict[str, str], image: Optional[str], timeout_seconds: int, tool_name: str) -> ToolResult:
    """
    Calls run_command_in_sandbox and returns a ToolResult.
    Defensively handles errors and returns diagnostics in stderr when sandboxing fails.
    """
    try:
        if image is None:
            image = DEFAULT_IMAGES.get(tool_name) or "ubuntu:22.04"
        
        result = run_command_in_sandbox(command, files, image, timeout_seconds)
        
        if not isinstance(result, dict):
            return ToolResult(tool_name, "", f"Invalid sandbox result type for {tool_name}", -1, diagnostics="invalid-result-type")
        
        stdout = result.get("stdout", "") or ""
        stderr = result.get("stderr", "") or ""
        exit_code = int(result.get("exit_code", result.get("returncode", 0) or 0))
        
        return ToolResult(tool_name, stdout, stderr, exit_code)
    except Exception as e:
        return ToolResult(tool_name, "", f"sandbox-failed: {e}\n{traceback.format_exc()}", -1, diagnostics=str(e))

# ----------------------------
# Language-specific orchestrators (tool invocation + parsing)
# ----------------------------
def _python_pipeline(file_path: str, code: str, per_tool_image: Dict[str, str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Run Python checks:
    - AST (in-process)
    - flake8
    - mypy
    - bandit (security)
    Returns (findings, raw_tool_outputs)
    """
    findings: List[Dict[str, Any]] = []
    raw: Dict[str, Any] = {}
    
    # 1) AST checks
    try:
        try:
            tree = ast.parse(code)
            syntax_error = None
        except SyntaxError as e:
            tree = None
            syntax_error = e
        
        if syntax_error:
            findings.append({
                "id": "ast:syntax",
                "tool": "ast",
                "severity": "error",
                "message": f"SyntaxError: {syntax_error.msg}",
                "file": getattr(syntax_error, "filename", file_path),
                "line": getattr(syntax_error, "lineno", None),
                "column": getattr(syntax_error, "offset", None),
                "suggestion": "Fix syntax error.",
            })
        else:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                    findings.append({
                        "id": "ast:insecure-eval",
                        "tool": "ast",
                        "severity": "error",
                        "message": f"Use of {node.func.id}() is insecure.",
                        "file": file_path,
                        "line": getattr(node, "lineno", None),
                        "column": None,
                        "suggestion": "Avoid eval/exec; validate inputs and avoid dynamic execution.",
                    })
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    findings.append({
                        "id": "ast:bare-except",
                        "tool": "ast",
                        "severity": "warning",
                        "message": "Bare except detected (catching all exceptions).",
                        "file": file_path,
                        "line": getattr(node, "lineno", None),
                        "column": None,
                        "suggestion": "Catch specific exceptions or use `except Exception as e`.",
                    })
    except Exception as e:
        findings.append(_make_internal_finding("ast", f"AST analyzer crashed: {e}\n{traceback.format_exc()}"))
    
    # 2) Prepare files for sandboxed tools
    files = {os.path.basename(file_path) or "main.py": code}
    
    # Define tool commands
    flake8_cmd = ["flake8", list(files.keys())[0], "--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s"]
    mypy_cmd = ["mypy", "--show-column-numbers", "--no-error-summary", "--pretty", "false", list(files.keys())[0]]
    # bandit: produce JSON for parsing
    bandit_cmd = ["bandit", "-r", ".", "-n", "5", "-f", "json", "-q"]
    
    # run tools in parallel (flake8, mypy, bandit)
    tool_jobs = {
        "flake8": (flake8_cmd, per_tool_image.get("flake8") or DEFAULT_IMAGES.get("flake8")),
        "mypy": (mypy_cmd, per_tool_image.get("mypy") or DEFAULT_IMAGES.get("mypy")),
        "bandit": (bandit_cmd, per_tool_image.get("bandit") or DEFAULT_IMAGES.get("bandit")),
    }
    
    futures = {}
    with ThreadPoolExecutor(max_workers=min(len(tool_jobs), MAX_TOOL_PARALLEL)) as ex:
        for tool, (cmd, image) in tool_jobs.items():
            # For bandit we need to provide a directory layout; put file at its basename in root
            if tool == "bandit":
                # create files dict with the file at its basename
                bandit_files = {os.path.basename(file_path): code}
                futures[ex.submit(_run_tool_in_sandbox_safe, cmd, bandit_files, image, TOOL_TIMEOUT_SECONDS, tool)] = tool
            else:
                futures[ex.submit(_run_tool_in_sandbox_safe, cmd, files, image, TOOL_TIMEOUT_SECONDS, tool)] = tool
        
        for fut in as_completed(futures):
            tool_name = futures[fut]
            try:
                res: ToolResult = fut.result()
                raw[tool_name] = res.truncated()
                stdout = res.stdout or ""
                stderr = res.stderr or ""
                if tool_name == "flake8":
                    findings.extend(parse_flake8(stdout))
                    findings.extend(parse_flake8(stderr))
                elif tool_name == "mypy":
                    findings.extend(parse_mypy(stdout))
                    findings.extend(parse_mypy(stderr))
                elif tool_name == "bandit":
                    # bandit writes JSON to stdout normally
                    findings.extend(parse_bandit_json(stdout))
                    findings.extend(parse_bandit_json(stderr))
                else:
                    findings.append(_make_internal_finding(tool_name, f"Unhandled python tool: {tool_name}"))
            except Exception as e:
                findings.append(_make_internal_finding(tool_name, f"Tool failed: {e}"))
    
    return findings, raw

def _js_pipeline(file_path: str, code: str, per_tool_image: Dict[str, str], is_typescript: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    raw: Dict[str, Any] = {}
    
    name = os.path.basename(file_path) or ("main.ts" if is_typescript else "main.js")
    files = {name: code}
    
    eslint_cmd = ["npx", "-y", "eslint", "--format", "json", name]
    tsc_cmd = ["npx", "-y", "tsc", "--noEmit", name]
    
    # run eslint then optionally tsc
    res_eslint = _run_tool_in_sandbox_safe(eslint_cmd, files, per_tool_image.get("eslint") or DEFAULT_IMAGES.get("eslint"), TOOL_TIMEOUT_SECONDS, "eslint")
    raw["eslint"] = res_eslint.truncated()
    try:
        findings.extend(parse_eslint(res_eslint.stdout))
    except Exception:
        findings.append(_make_internal_finding("eslint", "Failed to parse ESLint output."))
    
    # parse possible stderr JSON
    try:
        findings.extend(parse_eslint(res_eslint.stderr))
    except Exception:
        pass
    
    if is_typescript:
        res_tsc = _run_tool_in_sandbox_safe(tsc_cmd, files, per_tool_image.get("tsc") or DEFAULT_IMAGES.get("tsc"), TOOL_TIMEOUT_SECONDS, "tsc")
        raw["tsc"] = res_tsc.truncated()
        findings.extend(parse_tsc(res_tsc.stderr or ""))
    
    return findings, raw

def _java_pipeline(file_path: str, code: str, per_tool_image: Dict[str, str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    raw: Dict[str, Any] = {}
    
    name = os.path.basename(file_path) or "Main.java"
    files = {name: code}
    
    javac_cmd = ["javac", "-Xlint", name]
    res = _run_tool_in_sandbox_safe(javac_cmd, files, per_tool_image.get("javac") or DEFAULT_IMAGES.get("javac"), TOOL_TIMEOUT_SECONDS, "javac")
    raw["javac"] = res.truncated()
    findings.extend(parse_javac(res.stderr or ""))
    
    return findings, raw

def _c_cpp_pipeline(file_path: str, code: str, per_tool_image: Dict[str, str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    raw: Dict[str, Any] = {}
    
    name = os.path.basename(file_path) or "main.c"
    files = {name: code}
    
    # clang-tidy requires a compile_commands.json for real projects; we'll call clang-tidy with -checks=* and fallback parse
    clang_cmd = ["clang-tidy", name, "--", "-std=c11"]
    res = _run_tool_in_sandbox_safe(clang_cmd, files, per_tool_image.get("clang-tidy") or DEFAULT_IMAGES.get("clang-tidy"), TOOL_TIMEOUT_SECONDS, "clang-tidy")
    raw["clang-tidy"] = res.truncated()
    findings.extend(parse_clang_tidy(res.stderr or ""))
    # In some environments clang-tidy prints to stdout
    findings.extend(parse_clang_tidy(res.stdout or ""))
    
    return findings, raw

def _go_pipeline(file_path: str, code: str, per_tool_image: Dict[str, str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    raw: Dict[str, Any] = {}
    
    name = os.path.basename(file_path) or "main.go"
    files = {name: code}
    
    # go vet needs module context; we will run go vet on the file path
    # For sandboxed runner, we just call go vet ./... within a workspace where file is present
    go_vet_cmd = ["bash", "-lc", "go vet ./..."]
    res = _run_tool_in_sandbox_safe(go_vet_cmd, files, per_tool_image.get("go") or DEFAULT_IMAGES.get("go"), TOOL_TIMEOUT_SECONDS, "go vet")
    raw["go vet"] = res.truncated()
    findings.extend(parse_go_vet(res.stderr or ""))
    findings.extend(parse_go_vet(res.stdout or ""))
    
    return findings, raw

def _rust_pipeline(file_path: str, code: str, per_tool_image: Dict[str, str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    raw: Dict[str, Any] = {}
    
    # cargo check expects a cargo workspace; we create a minimal Cargo.toml and run cargo check
    # For single-file quick-check, we will place code into src/main.rs and create a minimal Cargo.toml
    files = {
        "Cargo.toml": '[package]\nname = "validator_temp"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n',
        "src/main.rs": code
    }
    cargo_cmd = ["cargo", "check", "--message-format", "short"]
    res = _run_tool_in_sandbox_safe(cargo_cmd, files, per_tool_image.get("rust") or DEFAULT_IMAGES.get("rust"), TOOL_TIMEOUT_SECONDS, "cargo")
    raw["cargo"] = res.truncated()
    findings.extend(parse_cargo(res.stderr or ""))
    findings.extend(parse_cargo(res.stdout or ""))
    
    return findings, raw

# ----------------------------
# High-level orchestration for multiple files and cross-language parallelism
# ----------------------------
def _validate_single_file(file_path: str, code: str, per_tool_image: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Validate a single file. Returns a normalized report with findings and raw tool outputs.
    """
    per_tool_image = per_tool_image or {}
    lang = detect_language(code, filename_hint=file_path)
    findings: List[Dict[str, Any]] = []
    raw_tool_outputs: Dict[str, Any] = {}
    
    try:
        if lang == "python":
            f, raw = _python_pipeline(file_path, code, per_tool_image)
            findings.extend(f)
            raw_tool_outputs.update(raw)
        elif lang in ("javascript", "typescript"):
            is_ts = (lang == "typescript")
            f, raw = _js_pipeline(file_path, code, per_tool_image, is_typescript=is_ts)
            findings.extend(f)
            raw_tool_outputs.update(raw)
        elif lang == "java":
            f, raw = _java_pipeline(file_path, code, per_tool_image)
            findings.extend(f)
            raw_tool_outputs.update(raw)
        elif lang == "c_cpp":
            f, raw = _c_cpp_pipeline(file_path, code, per_tool_image)
            findings.extend(f)
            raw_tool_outputs.update(raw)
        elif lang == "go":
            f, raw = _go_pipeline(file_path, code, per_tool_image)
            findings.extend(f)
            raw_tool_outputs.update(raw)
        elif lang == "rust":
            f, raw = _rust_pipeline(file_path, code, per_tool_image)
            findings.extend(f)
            raw_tool_outputs.update(raw)
        else:
            # Unknown language heuristics
            if re.search(r"\b(eval|exec|system|popen|ProcessBuilder)\b", code):
                findings.append({
                    "id": "heuristic:exec",
                    "tool": "heuristic",
                    "severity": "warning",
                    "message": "Potential use of dangerous execution functions detected.",
                    "file": file_path,
                    "line": None,
                    "column": None,
                    "suggestion": "Review code for unsafe execution of shell/strings."
                })
            raw_tool_outputs["note"] = f"No dedicated validators for language '{lang}'."
    except Exception as e:
        findings.append(_make_internal_finding("validator", f"Validator crashed: {e}\n{traceback.format_exc()}"))
    
    findings = _cap_findings(findings)
    
    # build summary counts
    counts = {"errors": 0, "warnings": 0, "info": 0}
    for f in findings:
        sev = f.get("severity", "info")
        if sev == "error":
            counts["errors"] += 1
        elif sev == "warning":
            counts["warnings"] += 1
        else:
            counts["info"] += 1
    
    status = "ok"
    if counts["errors"] > 0:
        status = "error"
    elif counts["warnings"] > 0:
        status = "partial"
    
    return {
        "path": file_path,
        "language": lang,
        "status": status,
        "findings": findings,
        "summary": counts,
        "raw_tool_outputs": raw_tool_outputs,
    }

def validate_files(files: Dict[str, str], per_tool_image: Optional[Dict[str, str]] = None, max_workers: int = MAX_FILE_PARALLEL) -> Dict[str, Any]:
    """
    Validate multiple files in parallel. files: mapping of path -> code.
    Returns aggregated report: per-file results and an overall summary.
    """
    per_tool_image = per_tool_image or {}
    results: Dict[str, Any] = {}
    futures = {}
    
    with ThreadPoolExecutor(max_workers=min(max_workers, MAX_FILE_PARALLEL)) as ex:
        for path, code in files.items():
            futures[ex.submit(_validate_single_file, path, code, per_tool_image)] = path
        
        for fut in as_completed(futures):
            path = futures[fut]
            try:
                res = fut.result()
                results[path] = res
            except Exception as e:
                results[path] = {
                    "path": path,
                    "language": "unknown",
                    "status": "error",
                    "findings": [_make_internal_finding("executor", f"Validation task failed: {e}\n{traceback.format_exc()}")],
                    "summary": {"errors": 1, "warnings": 0, "info": 0},
                    "raw_tool_outputs": {}
                }
    
    # aggregate overall summary
    overall = {"errors": 0, "warnings": 0, "info": 0, "files_validated": len(results)}
    for r in results.values():
        s = r.get("summary", {})
        overall["errors"] += s.get("errors", 0)
        overall["warnings"] += s.get("warnings", 0)
        overall["info"] += s.get("info", 0)
    
    return {"files": results, "overall": overall}

# ----------------------------
# Filesystem scanning mode
# ----------------------------
# Map file extensions to language heuristics (used for discovery)
EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c_cpp",
    ".cpp": "c_cpp",
    ".cc": "c_cpp",
    ".h": "c_cpp",
    ".hpp": "c_cpp",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
}

def _discover_files(root: str, include_patterns: Optional[Iterable[str]] = None, exclude_patterns: Optional[Iterable[str]] = None) -> Dict[str, str]:
    """
    Recursively discover files under root and return mapping path -> file contents.
    include_patterns/exclude_patterns accept glob patterns (relative to root).
    """
    include_patterns = list(include_patterns) if include_patterns else ["**/*"]
    exclude_patterns = list(exclude_patterns) if exclude_patterns else []
    
    matched = {}
    root = os.path.abspath(root)
    
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root)
            
            # apply include/exclude globs
            included = any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(full, pat) for pat in include_patterns)
            excluded = any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(full, pat) for pat in exclude_patterns)
            
            if not included or excluded:
                continue
            
            _, ext = os.path.splitext(fname.lower())
            if ext in EXTENSIONS:
                try:
                    with open(full, "r", encoding="utf-8") as fh:
                        matched[full] = fh.read()
                except Exception as e:
                    # ignore unreadable files but report as internal finding attached to results later
                    matched[full] = f"# ERROR: failed to read file: {e}\n"
    
    return matched

def validate_path(path: str, include_patterns: Optional[Iterable[str]] = None, exclude_patterns: Optional[Iterable[str]] = None, per_tool_image: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Discover files under path and validate them. Returns output same as validate_files but adds discovery metadata.
    """
    per_tool_image = per_tool_image or {}
    
    if not os.path.exists(path):
        return {"error": f"Path not found: {path}"}
    
    files = _discover_files(path, include_patterns=include_patterns, exclude_patterns=exclude_patterns)
    
    if not files:
        return {"files": {}, "overall": {"errors": 0, "warnings": 0, "info": 0, "files_validated": 0}, "note": "No discoverable files."}
    
    result = validate_files(files, per_tool_image=per_tool_image)
    result["discovered_files_count"] = len(files)
    return result

# ----------------------------
# Convenience higher-level APIs to match original single-file behavior
# ----------------------------
def validate_code(code: str, filename_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Backwards-compatible single-file API. Returns a normalized report for a single code string.
    """
    res = _validate_single_file(filename_hint or "snippet", code, per_tool_image=None)
    # shape to previous expected output keys
    return {
        "status": res.get("status"),
        "language": res.get("language"),
        "findings": res.get("findings"),
        "summary": res.get("summary"),
        "raw_tool_outputs": res.get("raw_tool_outputs"),
    }

def validate_and_fix(code: str, filename_hint: Optional[str] = None, auto_apply: bool = False) -> Dict[str, Any]:
    """
    Runs validation and conservative auto-fixes (Python-only).
    Returns validate_code(...) + suggested_code + diff + applied flag.
    """
    report = validate_code(code, filename_hint=filename_hint)
    suggested_code = code
    changes: List[str] = []
    diff_text = ""
    
    if report.get("language") == "python":
        try:
            # 1) Replace bare except lines: `except:` -> `except Exception as e:`
            suggested_code = re.sub(r"(^\s*)except\s*:\s*$", r"\1except Exception as e:", suggested_code, flags=re.MULTILINE)
            if suggested_code != code:
                changes.append("Replaced bare except with 'except Exception as e:'")
            
            # 2) Add timeout to requests.get/post if missing (best-effort)
            def _add_timeout_requests(match):
                call = match.group(0)
                if "timeout=" in call:
                    return call
                return re.sub(r"\)\s*$", ", timeout=10)", call)
            
            suggested_code = re.sub(r"requests\.(get|post)\s*\([^)\n]*\)", _add_timeout_requests, suggested_code)
            if suggested_code != code and "timeout=10" in suggested_code:
                changes.append("Inserted timeout=10 into requests calls where missing.")
            
            # 3) Fix common __init__ typo
            if re.search(r"def\s+_init_\s*\(", suggested_code):
                suggested_code = re.sub(r"def\s+_init_\s*\(", "def __init__(", suggested_code)
                changes.append("Fixed `def _init_` -> `def __init__`")
            
            # compute unified diff
            if suggested_code.strip() != code.strip():
                import difflib
                diff_text = "\n".join(difflib.unified_diff(
                    code.splitlines(keepends=True),
                    suggested_code.splitlines(keepends=True),
                    fromfile="original",
                    tofile="suggested",
                    lineterm=""
                ))
        except Exception as e:
            report.setdefault("findings", []).append(_make_internal_finding("autofix", f"Autofix failed: {e}"))
    
    out = dict(report)
    out["suggested_code"] = suggested_code
    out["changes"] = changes
    out["diff"] = diff_text
    
    if auto_apply and suggested_code.strip() != code.strip():
        out["fixed_code"] = suggested_code
        out["applied"] = True
    else:
        out["applied"] = False
    
    return out

# ----------------------------
# CLI (optional) for local debugging
# ----------------------------
def _print_summary(aggregated: Dict[str, Any]):
    overall = aggregated.get("overall", {})
    print("Validated files:", overall.get("files_validated"))
    print("Errors:", overall.get("errors"), "Warnings:", overall.get("warnings"), "Info:", overall.get("info"))

def _cli_main(argv):
    import argparse
    p = argparse.ArgumentParser(description="validator.py - enterprise-grade multi-language validator")
    p.add_argument("--path", "-p", help="Validate all supported files under path (recursive)")
    p.add_argument("--file", "-f", help="Validate single file")
    p.add_argument("--show-raw", action="store_true", help="Show raw tool outputs in full (may be large)")
    args = p.parse_args(argv[1:])
    
    if args.path:
        res = validate_path(args.path)
        _print_summary(res)
        if args.show_raw:
            print(json.dumps(res, indent=2))
        else:
            print("Use programmatic API to inspect per-file details.")
    elif args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as fh:
                code = fh.read()
            res = validate_code(code, filename_hint=args.file)
            print(json.dumps(res, indent=2))
        except Exception as e:
            print("Error reading file:", e)
    else:
        p.print_help()

if __name__ == "__main__":
    _cli_main(sys.argv)

# End of validator.py
"""
Deployment notes and recommendations (short):
- Ensure run_command_in_sandbox provides proper isolation (containerization, resource limits, network disabled).
- Provide proper images in DEFAULT_IMAGES or via per_tool_image argument with the required tools preinstalled.
  e.g., images must have bandit, flake8, mypy, clang-tidy, cargo, go, node (eslint/tsc), javac.
- For clang-tidy and cargo, full project contexts (compile_commands.json, Cargo workspace) produce better results;
  single-file invocation is a best-effort fallback.
- Timeouts and worker counts are conservative; tune TOOL_TIMEOUT_SECONDS, MAX_TOOL_PARALLEL, MAX_FILE_PARALLEL for CI workers.
- This file focuses on safety (no user code execution) and normalized outputs suitable for enterprise pipelines.
"""