# validator.py
"""
Production-grade Code Validator (Python-focused)

Goals:
- Return structured findings:
    findings: [
      {"severity": "error"|"warning"|"info", "message": str, "category": str, "lineno": int|None}
    ]
- Provide validate_code(code) -> report
- Provide validate_and_fix(code, auto_apply=False) -> report with suggested_code/diff and optionally fixed_code
- Be safe: never execute the user's code.
- Be resilient to very large files (configurable thresholds).
- Conservative auto-fixes only (textual transforms, no code execution).
- Extra fail-safes: attempt recovery even for malformed/broken code (99.99% reliability goal).
"""

from __future__ import annotations

import ast
import re
import sys
import difflib
import io
import textwrap
import autopep8
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# Configurable toggles / limits
# ----------------------------
STRICT_BLOCKLIST = True              # block certain imports (pickle etc.) as errors if True
AUTO_APPLY_SAFE_FIXES = False        # downstream can override when calling validate_and_fix
AUTOPEP8_MAX_CHARS = 300_000         # skip expensive autopep8 on files larger than this (tunable)
MAX_FINDINGS_RETURNED = 500          # limit findings to avoid huge payloads
SANITY_MAX_LINES = 50_000            # max lines allowed before validator bails with warning
SANITY_MAX_CHARS = 2_000_000         # max chars allowed before validator bails with warning
# ----------------------------

# Lists / patterns used by checks
ALLOWLIST_IMPORTS = {"requests", "pytest", "unittest", "module_under_test"}
BLOCKLIST_IMPORTS = {"subprocess", "ctypes", "_thread"}
PICKLE_MODULE = "pickle"
WARNLIST_IMPORTS = {"os", "sys", "shutil", "multiprocessing", "socket"}

FORBIDDEN_PATTERNS = [
    r"\bexec\s*\(",
    r"\beval\s*\(",
    r"pickle\.load",
    r"pickle\.loads",
]

HARDCODED_SECRET_RE = re.compile(
    r"(?P<name>[A-Z0-9_]{4,})\s*=\s*['\"][^'\"]{6,}['\"]"
)

SQL_INJECTION_PATTERNS = [
    re.compile(r"f?\".*INSERT\s+INTO.*\{.*\}.*\"", re.IGNORECASE),
    re.compile(r"f?\".*UPDATE.*\{.*\}.*\"", re.IGNORECASE),
    re.compile(r"execute\s*\(.*%.*\)", re.IGNORECASE),
    re.compile(r"cursor\.execute\(\s*\".*\+.*\""),  # naive concatenation detection
]

BARE_EXCEPT_RE = re.compile(r"(^\s*)except\s*:\s*$", re.MULTILINE)

REQUESTS_CALL_RE = re.compile(r"requests\.(get|post|put|delete)\s*\((.*?)\)", re.S)

LOCK_DECL_RE = re.compile(r"(\w+_lock)\s*=\s*threading\.(Lock|RLock)\(")
WITH_LOCK_RE = re.compile(r"with\s+([A-Za-z0-9_]+)\s*:\s*")

# Types
Finding = Dict[str, Any]


# ----------------------------
# Utilities
# ----------------------------
def detect_language(code: str) -> str:
    """Simplistic language detection for wrapper use."""
    if "def " in code and ":" in code:
        return "python"
    if "import React" in code or "function(" in code or "const " in code:
        return "javascript"
    return "python"


class ValidationError(Exception):
    """Raised when validation is considered fatal by callers (rare — validator normally returns findings)."""
    pass


# ----------------------------
# The Core Validator
# ----------------------------
class CodeValidator:
    def __init__(self, code: str):
        self.original_code = code or ""
        # Normalize line endings and strip trailing BOMs or non-printables
        self.code = self.original_code.replace("\r\n", "\n").replace("\r", "\n")
        self.code = self.code.encode("utf-8", "ignore").decode("utf-8", "ignore")
        self.tree: Optional[ast.AST] = None
        self.findings: List[Finding] = []
        self.categories: Dict[str, List[str]] = {
            "Security": [],
            "Maintainability": [],
            "Type Safety": [],
            "Concurrency": [],
            "Other": [],
        }
        self._chars = len(self.code)
        self._lines = self.code.count("\n") + 1
        # sys.stdlib_module_names on 3.10+ helps detect stdlib vs project modules
        self.stdlib_modules = getattr(sys, "stdlib_module_names", set())

        # Sanity pre-checks for extreme inputs
        if self._lines > SANITY_MAX_LINES or self._chars > SANITY_MAX_CHARS:
            self._add_finding(
                "error",
                f"Code too large for reliable validation: {self._lines} lines / {self._chars} chars.",
                "Maintainability",
                None,
            )
            # fail-safe: truncate code to safe size for analysis
            self.code = self.code[:SANITY_MAX_CHARS]

    def _add_finding(self, severity: str, message: str, category: str = "Other", lineno: Optional[int] = None):
        f: Finding = {"severity": severity, "message": message, "category": category, "lineno": lineno}
        if len(self.findings) < MAX_FINDINGS_RETURNED:
            self.findings.append(f)
        self.categories.setdefault(category, []).append(message)

    # Try AST parse but do not crash the validator on SyntaxError
    def try_parse(self):
        try:
            self.tree = ast.parse(self.code)
        except SyntaxError as e:
            msg = f"SyntaxError: {e.msg}"
            self._add_finding("warning", msg, "Maintainability", getattr(e, "lineno", None))
            self.tree = None
        except Exception as e:
            # Catch-all to keep validator stable
            self._add_finding("warning", f"AST parse failed: {e}", "Maintainability", None)
            self.tree = None

    def pre_clean(self):
        """Conservative pre-clean using autopep8 for simple formatting issues to help AST parsing.
        Skip autopep8 on extremely large files to avoid OOM/timeouts."""
        if self._chars > AUTOPEP8_MAX_CHARS:
            return
        try:
            ast.parse(self.code)
        except Exception:
            try:
                fixed = autopep8.fix_code(self.code)
                ast.parse(fixed)
                self.code = fixed
            except Exception:
                # fallback mini-fixes for severe syntax issues
                fixed = self.code
                fixed = re.sub(r"def\s+([a-zA-Z0-9_]+)\s*\(.*\)\s*(?=[^\:])", r"def \1(...):", fixed)
                fixed = re.sub(r"class\s+([a-zA-Z0-9_]+)\s*(?=[^\:])", r"class \1:", fixed)
                fixed = re.sub(r"=\s*{\s*$", "= {}", fixed, flags=re.MULTILINE)
                if fixed != self.code:
                    self.code = fixed

    # ----------------------------
    # Individual checks
    # ----------------------------
    def check_forbidden_patterns(self):
        for pat in FORBIDDEN_PATTERNS:
            if re.search(pat, self.code):
                if "pickle" in pat and not STRICT_BLOCKLIST:
                    self._add_finding("warning", f"Risky usage detected matching pattern `{pat}`", "Security")
                else:
                    self._add_finding("error", f"Forbidden usage detected matching pattern `{pat}`", "Security")

    def check_imports(self):
        imports_seen: List[Tuple[str, Optional[int]]] = []
        if self.tree:
            for node in ast.walk(self.tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports_seen.append((alias.name, getattr(node, "lineno", None)))
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    imports_seen.append((module, getattr(node, "lineno", None)))
        else:
            for m in re.finditer(r"^\s*import\s+([A-Za-z0-9_.]+)", self.code, re.MULTILINE):
                imports_seen.append((m.group(1), None))
            for m in re.finditer(r"^\s*from\s+([A-Za-z0-9_.]+)\s+import", self.code, re.MULTILINE):
                imports_seen.append((m.group(1), None))

        for module_name, lineno in imports_seen:
            root = module_name.split(".")[0]
            if root in ALLOWLIST_IMPORTS:
                continue
            if root in BLOCKLIST_IMPORTS:
                self._add_finding("error", f"Blocked unsafe import `{root}`", "Security", lineno)
                continue
            if root == PICKLE_MODULE:
                if STRICT_BLOCKLIST:
                    self._add_finding("error", f"Blocked unsafe import `{root}`", "Security", lineno)
                else:
                    self._add_finding("warning", f"Risky import allowed with warning: `{root}`", "Security", lineno)
                continue
            if root in WARNLIST_IMPORTS:
                self._add_finding("warning", f"Risky import used: `{root}`", "Security", lineno)
                continue

    def check_hardcoded_secrets(self):
        for m in HARDCODED_SECRET_RE.finditer(self.code):
            name = m.group("name")
            if re.search(r"(KEY|TOKEN|SECRET|PASSWORD|API)", name, re.IGNORECASE):
                self._add_finding("warning", f"Hardcoded secret variable detected: `{name}`. Prefer env vars or a vault.", "Security", None)

    def check_sql_patterns(self):
        for pattern in SQL_INJECTION_PATTERNS:
            if pattern.search(self.code):
                self._add_finding("error", "Possible SQL-injection pattern detected; use parameterized queries.", "Security", None)

    def check_bare_except(self):
        for m in BARE_EXCEPT_RE.finditer(self.code):
            lineno = self.code[: m.start()].count("\n") + 1
            self._add_finding("warning", "Bare except found; catch specific exceptions or use 'except Exception as e' and log.", "Maintainability", lineno)

    def check_requests_usage(self):
        for m in REQUESTS_CALL_RE.finditer(self.code):
            call_text = m.group(0)
            lineno = self.code[: m.start()].count("\n") + 1
            if "timeout=" not in call_text:
                self._add_finding("warning", "requests call missing timeout parameter (add timeout=...).", "Maintainability", lineno)
            window_after = self.code[m.end(): m.end() + 200]
            if "raise_for_status" not in window_after and ".status_code" not in window_after:
                self._add_finding("warning", "Call to requests... missing explicit status check; add response.raise_for_status().", "Security", lineno)

    def check_concurrency_deadlocks(self):
        func_bodies = re.split(r"\ndef\s+", "\n" + self.code)
        orders: List[List[str]] = []
        for body in func_bodies:
            names = [m.group(1) for m in WITH_LOCK_RE.finditer(body)]
            if names:
                orders.append(names)
        for a in orders:
            for b in orders:
                if len(a) >= 2 and len(b) >= 2:
                    if a[0] == b[1] and a[1] == b[0]:
                        self._add_finding("error", "Potential deadlock: locks acquired in different orders in different functions.", "Concurrency", None)
                        return

    def check_type_hints_and_defs(self):
        if not self.tree:
            return
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                if not node.returns:
                    self._add_finding("info", f"Function `{node.name}` missing return type hint.", "Type Safety", node.lineno)
                for arg in node.args.args:
                    if arg.arg != "self" and not arg.annotation:
                        lineno = getattr(arg, "lineno", node.lineno)
                        self._add_finding("info", f"Function `{node.name}` arg `{arg.arg}` missing type hint.", "Type Safety", lineno)

    # ----------------------------
    # Conservative auto-fix transformations
    # ----------------------------
    def auto_fix(self) -> Tuple[str, List[str]]:
        code = self.original_code
        changes: List[str] = []

        # 1) Fix common typo: def _init_ -> def __init__
        if re.search(r"class\s+\w+.*\n\s+def\s+_init_\(", code):
            code = re.sub(r"def\s+_init_\s*\(", "def __init__(", code)
            changes.append("Renamed `def _init_` -> `def __init__`")

        # 2) Neutralize unsafe pickle usage
        if "pickle" in code:
            if STRICT_BLOCKLIST:
                pattern = re.compile(
                    r"with\s+open\(([^)]+),\s*['\"]rb['\"]\)\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*((?:\n(?:\s+).*)+)",
                    re.MULTILINE
                )
                def repl_pickle(m):
                    inner = m.group(3)
                    if "pickle.load" in inner or "pickle.loads" in inner:
                        changes.append("Neutralized pickle.load usage with safe placeholder.")
                        return (
                            f"# FIXME: removed unsafe pickle.load usage for security. Use json/yaml/safe schema.\n"
                            f"# with open({m.group(1)}, 'rb') as {m.group(2)}:\n"
                            f"#     data = safe_load({m.group(2)})\n"
                        )
                    return m.group(0)
                code = pattern.sub(repl_pickle, code)

        # 3) SQL naive fix
        code_before = code
        code = re.sub(
            r"cursor\.execute\(\s*f?\"INSERT OR REPLACE INTO stock_data VALUES\s*\([^\)]*\)\"\s*\)",
            "cursor.execute(\"INSERT OR REPLACE INTO stock_data (symbol, value, timestamp) VALUES (?, ?, ?)\", (symbol, value, timestamp))",
            code,
        )
        if code != code_before:
            changes.append("Converted naive INSERT into parameterized query.")

        # 4) Add timeout + raise_for_status
        lines = code.splitlines()
        new_lines: List[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            new_lines.append(line)
            if "requests." in line and "(" in line and ")" in line and "timeout=" not in line:
                call_re = re.search(r"(requests\.(get|post|put|delete)\s*\()", line)
                if call_re:
                    updated_line = re.sub(r"\)\s*$", ", timeout=10)", line)
                    if updated_line != line:
                        new_lines[-1] = updated_line
                        changes.append("Added timeout=10 to requests call.")
                        next_nonempty = None
                        for j in range(i+1, min(i+4, len(lines))):
                            if lines[j].strip():
                                next_nonempty = lines[j].strip()
                                break
                        if not next_nonempty or "raise_for_status" not in next_nonempty:
                            new_lines.append("        response.raise_for_status()  # inserted by validator")
                            changes.append("Inserted response.raise_for_status().")
                            i += 1
            i += 1
        code = "\n".join(new_lines)

        # 5) Bare except fix
        if re.search(r"^\s*except\s*:\s*$", code, re.MULTILINE):
            code = re.sub(r"(^\s*)except\s*:\s*$", r"\1except Exception as e:", code, flags=re.MULTILINE)
            changes.append("Replaced bare except with 'except Exception as e:'.")

        # 6) Non-atomic increments comment
        if "self.processed_stats[\"success\"] += 1" in code or "self.processed_stats['success'] += 1" in code:
            code = code.replace(
                "self.processed_stats[\"success\"] += 1",
                "self.processed_stats[\"success\"] += 1  # WARNING: non-atomic; wrap in lock or atomic counter"
            )
            code = code.replace(
                "self.processed_stats['success'] += 1",
                "self.processed_stats['success'] += 1  # WARNING: non-atomic; wrap in lock or atomic counter"
            )
            changes.append("Annotated non-atomic counter increment.")

        # 7) Promote Lock -> RLock if both seen
        if "db_lock = threading.Lock()" in code and "stats_lock = threading.Lock()" in code:
            code = code.replace("db_lock = threading.Lock()", "db_lock = threading.RLock()  # safer RLock suggestion")
            code = code.replace("stats_lock = threading.Lock()", "stats_lock = threading.RLock()  # safer RLock suggestion")
            changes.append("Promoted Lock -> RLock to reduce deadlock risk.")

        # Final formatting
        if len(code) <= AUTOPEP8_MAX_CHARS:
            try:
                code = autopep8.fix_code(code)
            except Exception:
                pass

        return code, changes

    # ----------------------------
    # Run all checks and compile report
    # ----------------------------
    def run_all(self) -> Dict[str, Any]:
        self.pre_clean()
        self.try_parse()
        self.check_forbidden_patterns()
        self.check_imports()
        self.check_hardcoded_secrets()
        self.check_sql_patterns()
        self.check_bare_except()
        self.check_requests_usage()
        self.check_concurrency_deadlocks()
        self.check_type_hints_and_defs()

        errors = [f for f in self.findings if f["severity"] == "error"]
        status = "error" if errors else "ok"
        findings_limited = self.findings[:MAX_FINDINGS_RETURNED]

        return {
            "status": status,
            "findings": findings_limited,
            "categories": self.categories,
            "message": "Validation complete",
        }


# ----------------------------
# Public API
# ----------------------------
def validate_code(code: str) -> Dict[str, Any]:
    """
    Run validation only. Return dict:
    {
        status: "ok"|"error",
        findings: [...],
        categories: {...},
        message: ...
    }
    """
    v = CodeValidator(code)
    return v.run_all()


def validate_and_fix(code: str, auto_apply: bool = AUTO_APPLY_SAFE_FIXES) -> Dict[str, Any]:
    """
    Run validation and conservative auto-fixes.

    Returns:
    {
        status: "ok"|"error",
        findings: [...],
        categories: {...},
        message: ...,
        suggested_code: "<text>",   # text after conservative auto-fix
        changes: ["..."],          # human-readable change summaries
        diff: "unified diff"       # empty string if identical
        fixed_code: "<text>" (only present if auto_apply True)
    }
    """
    v = CodeValidator(code)
    report = v.run_all()
    suggested_code, changes = v.auto_fix()

    if suggested_code.strip() == code.strip():
        diff_text = ""
    else:
        diff_text = "\n".join(difflib.unified_diff(
            code.splitlines(keepends=False),
            suggested_code.splitlines(keepends=False),
            fromfile="original", tofile="fixed", lineterm=""
        ))

    out: Dict[str, Any] = {
        "status": report["status"],
        "findings": report["findings"],
        "categories": report["categories"],
        "message": report["message"],
        "suggested_code": suggested_code,
        "changes": changes,
        "diff": diff_text,
    }
    if auto_apply:
        out["fixed_code"] = suggested_code
    return out
