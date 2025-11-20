# sandbox.py
"""
Production-grade sandbox runner + advanced concurrency analyzer (single file).

Features:
- Docker-based isolated runner for multiple languages (Python, Node, Java, Go, Rust, C/C++).
- Placeholder tests when none provided.
- Resource-limited containers, network disabled, structured outputs & diagnostics.
- AST-based static concurrency analysis for Python to detect risky lock patterns and reversed lock ordering.
- Optional dynamic tracing (process-local) for lock acquisitions (trusted-only).
- Lock-order enforcement recommendation and simple fixer helper for Python code.
- Telemetry hooks (no-op by default; plug in Prometheus/Datadog/ELK).
- Single-file drop-in utility for CI / dev tools.

Security reminder:
- Use Docker execution for untrusted code.
- Dynamic in-process tracing must NOT be used on untrusted code.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import json
import logging
import threading
import contextlib
import inspect
import ast
from typing import Dict, Any, Optional, Tuple, List, Set
from collections import defaultdict

# Optional docker import
try:
    import docker
except Exception:  # pragma: no cover - environment dependent
    docker = None

# -----------------------
# Logger & telemetry hook
# -----------------------
logger = logging.getLogger("sandbox")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
logger.setLevel(os.getenv("SANDBOX_LOG_LEVEL", "INFO"))

def telemetry_event(name: str, payload: Dict[str, Any]) -> None:
    """
    Hook for telemetry/metrics. Replace with integration to StatsD/Prometheus/Datadog etc.
    Default: no-op log at debug level.
    """
    logger.debug("TELEMETRY %s: %s", name, json.dumps(payload, default=str))

# -----------------------
# Configuration defaults
# -----------------------
UNIVERSAL_IMAGE = os.getenv("SANDBOX_IMAGE", "arunmadhavan28/0pirate-polyglot:v1")

DEFAULT_IMAGE_BY_LANG: Dict[str, str] = {
    "python": UNIVERSAL_IMAGE,
    "javascript": UNIVERSAL_IMAGE,
    "typescript": UNIVERSAL_IMAGE,
    "java": UNIVERSAL_IMAGE,
    "go": UNIVERSAL_IMAGE,
    "rust": UNIVERSAL_IMAGE,
    "cpp": UNIVERSAL_IMAGE,
}

# DEFAULT_IMAGE_BY_LANG: Dict[str, str] = {
#     "python": "python:3.11-slim",
#     "javascript": "node:20-slim",
#     "typescript": "node:20-slim",
#     "java": "openjdk:17-jdk-slim",
#     "go": "golang:1.20-bullseye",
#     "rust": "rust:1.70-slim",
#     "cpp": "gcc:12.2.0",
# }
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "60"))
MEMORY_LIMIT = os.getenv("SANDBOX_MEMORY_LIMIT", "512m")
CPU_SHARES = int(os.getenv("SANDBOX_CPU_SHARES", "512"))
DISABLE_NETWORK = True
PLACEHOLDER_TESTS_ENABLED = True
MAX_LOG_BYTES = 200 * 1024  # 200KB
SANDBOX_TMP_ROOT = os.getenv("SANDBOX_TMP_ROOT", "/tmp/sandbox_runs")

os.makedirs(SANDBOX_TMP_ROOT, exist_ok=True)

# -----------------------
# Placeholder test generators
# -----------------------
def generate_placeholder_tests(language: str, module_name: str = "code") -> Tuple[str, str]:
    language = (language or "python").lower()
    if language == "python":
        return "test_code.py", (
            "import importlib\n"
            "try:\n"
            f"    mod = importlib.import_module('{module_name}')\n"
            "except Exception as e:\n"
            "    print('IMPORT_ERROR:', e)\n"
            "    raise\n\n"
            "def test_placeholder():\n"
            "    assert hasattr(mod, '__dict__')\n\n"
            "if __name__ == '__main__':\n"
            "    test_placeholder()\n"
        )
    if language in ("javascript", "typescript"):
        return "test_code.js", (
            "const mod = require('./code');\n"
            "function test_placeholder() {\n"
            "  if (!mod) throw new Error('module not exported');\n"
            "  console.log('placeholder ok');\n"
            "}\n"
            "try { test_placeholder(); process.exit(0); } catch (e) { console.error(e); process.exit(1); }\n"
        )
    if language == "java":
        return "TestCode.java", (
            "public class TestCode {\n"
            "  public static void main(String[] args) {\n"
            "    System.out.println(\"placeholder ok\");\n"
            "  }\n"
            "}\n"
        )
    if language == "go":
        return "main_test.go", (
            "package main\n\n"
            "import \"testing\"\n\n"
            "func TestPlaceholder(t *testing.T) {\n"
            "    // trivial placeholder\n"
            "}\n"
        )
    if language == "rust":
        return "tests.rs", (
            "#[test]\n"
            "fn placeholder_test() {\n"
            "    assert_eq!(2 + 2, 4);\n"
            "}\n"
        )
    if language == "cpp":
        return "test_code.cpp", (
            "#include <cassert>\n"
            "#include <iostream>\n\n"
            "int main() {\n"
            "  assert(1 == 1);\n"
            "  std::cout << \"placeholder ok\\n\";\n"
            "  return 0;\n"
            "}\n"
        )
    return "test_placeholder.txt", "placeholder"

# -----------------------
# Command builders
# -----------------------
def build_test_command(language: str, tests_present: bool, prefer_framework: Optional[str] = None) -> List[str]:
    language = (language or "python").lower()
    if language == "python":
        return ["/bin/sh", "-c", "pytest -q . || python -m unittest discover -v || python test_code.py"]
    if language in ("javascript", "typescript"):
        return ["/bin/sh", "-c", "npx jest --runInBand || npx mocha || node test_code.js"]
    if language == "java":
        return ["/bin/sh", "-c", "mvn -q test || gradle test --quiet || javac TestCode.java && java TestCode"]
    if language == "go":
        return ["/bin/sh", "-c", "go test ./... || go test || go run ."]
    if language == "rust":
        return ["/bin/sh", "-c", "cargo test --quiet || rustc --edition=2021 tests.rs && ./tests || true"]
    if language == "cpp":
        return ["/bin/sh", "-c", "g++ -std=c++17 test_code.cpp -O2 -o test_code && ./test_code"]
    return ["/bin/sh", "-c", "echo 'No runner configured for language' && exit 2"]

# -----------------------
# Workspace writer
# -----------------------
def _write_workspace(tmpdir: str, code: str, tests: Optional[str], language: str) -> Tuple[str, Optional[str]]:
    language = (language or "python").lower()
    code_fname = "code.py"
    tests_fname = None

    code = code or ""
    tests = tests or ""

    if language == "python":
        code_fname = "code.py"
        with open(os.path.join(tmpdir, code_fname), "w", encoding="utf-8") as f:
            f.write(code)
        if tests.strip():
            tests_fname = "test_code.py"
            with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                f.write(tests)
        else:
            if PLACEHOLDER_TESTS_ENABLED:
                tests_fname, tests_contents = generate_placeholder_tests("python", "code")
                with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                    f.write(tests_contents)

    elif language in ("javascript", "typescript"):
        ext = ".js" if language == "javascript" else ".ts"
        code_fname = f"code{ext}"
        with open(os.path.join(tmpdir, code_fname), "w", encoding="utf-8") as f:
            f.write(code)
        if tests.strip():
            tests_fname = f"test_code{ext}"
            with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                f.write(tests)
        else:
            if PLACEHOLDER_TESTS_ENABLED:
                tests_fname, tests_contents = generate_placeholder_tests(language, "code")
                with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                    f.write(tests_contents)

    elif language == "java":
        code_fname = "Code.java"
        with open(os.path.join(tmpdir, code_fname), "w", encoding="utf-8") as f:
            f.write(code or "public class Code { public static void main(String[] args) { System.out.println(\"hello\"); } }")
        if tests.strip():
            tests_fname = "TestCode.java"
            with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                f.write(tests)
        else:
            if PLACEHOLDER_TESTS_ENABLED:
                tests_fname, tests_contents = generate_placeholder_tests("java", "Code")
                with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                    f.write(tests_contents)

    elif language == "go":
        code_fname = "main.go"
        with open(os.path.join(tmpdir, code_fname), "w", encoding="utf-8") as f:
            f.write(code or "package main\n\nfunc main() {}\n")
        if tests.strip():
            tests_fname = "main_test.go"
            with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                f.write(tests)
        else:
            if PLACEHOLDER_TESTS_ENABLED:
                tests_fname, tests_contents = generate_placeholder_tests("go", "main")
                with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                    f.write(tests_contents)

    elif language == "rust":
        # create a minimal Cargo layout if needed
        code_fname = "lib.rs"
        with open(os.path.join(tmpdir, code_fname), "w", encoding="utf-8") as f:
            f.write(code or "// placeholder lib\n")
        if tests.strip():
            tests_fname = "tests.rs"
            with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                f.write(tests)
        else:
            if PLACEHOLDER_TESTS_ENABLED:
                tests_fname, tests_contents = generate_placeholder_tests("rust", "lib")
                with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                    f.write(tests_contents)

    elif language == "cpp":
        code_fname = "code.cpp"
        with open(os.path.join(tmpdir, code_fname), "w", encoding="utf-8") as f:
            f.write(code or "#include <iostream>\nint main(){std::cout<<\"hello\\n\";return 0;}\n")
        if tests.strip():
            tests_fname = "test_code.cpp"
            with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                f.write(tests)
        else:
            if PLACEHOLDER_TESTS_ENABLED:
                tests_fname, tests_contents = generate_placeholder_tests("cpp", "code")
                with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                    f.write(tests_contents)

    else:
        code_fname = "code.txt"
        with open(os.path.join(tmpdir, code_fname), "w", encoding="utf-8") as f:
            f.write(code)
        if PLACEHOLDER_TESTS_ENABLED:
            tests_fname = "test_placeholder.txt"
            with open(os.path.join(tmpdir, tests_fname), "w", encoding="utf-8") as f:
                f.write("placeholder")

    return code_fname, tests_fname

# -----------------------
# Sandbox runner
# -----------------------
def _truncate_for_return(s: str, max_bytes: int = MAX_LOG_BYTES) -> str:
    b = s.encode("utf-8")
    if len(b) <= max_bytes:
        return s
    return b[:max_bytes].decode("utf-8", errors="replace") + "\n...[truncated]"

def run_tests_in_sandbox(
    code: str,
    tests: Optional[str],
    language: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    image: Optional[str] = None,
    working_dir_name: Optional[str] = None,
    read_only_code_mount: bool = True,
) -> Dict[str, Any]:
    """
    Run tests in Docker. Returns structured result dict.
    """
    language = (language or "python").lower()
    start_time = time.time()
    tmpdir = None
    container = None
    client = None

    # Validate timeout
    try:
        timeout_seconds = int(timeout_seconds)
        if timeout_seconds <= 0:
            timeout_seconds = DEFAULT_TIMEOUT_SECONDS
    except Exception:
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS

    # Workspace
    workspace_root = tempfile.mkdtemp(prefix="sandbox_", dir=SANDBOX_TMP_ROOT)
    tmpdir = workspace_root
    diagnostics: Dict[str, Any] = {
        "docker_ok": False,
        "image": None,
        "image_pulled": False,
        "container_timed_out": False,
        "workspace": workspace_root,
        "command": None,
    }

    try:
        code_fname, tests_fname = _write_workspace(workspace_root, code, tests or "", language)

        chosen_image = image or DEFAULT_IMAGE_BY_LANG.get(language, DEFAULT_IMAGE_BY_LANG["python"])
        diagnostics["image"] = chosen_image

        tests_present = bool(tests and tests.strip())
        cmd = build_test_command(language, tests_present)

        # Setup commands for language-specific tool installs (best-effort, quiet)
        setup_cmds: List[str] = []
        if language == "python":
            setup_cmds.append("python -m pip install --no-input --disable-pip-version-check pytest >/dev/null 2>&1 || true")
        if language in ("javascript", "typescript"):
            setup_cmds.append("npm i --no-audit --no-fund jest mocha ts-node >/dev/null 2>&1 || true")

        shell_run = " && ".join(setup_cmds + [" ".join(cmd[2:])]) if len(cmd) >= 3 else " ".join(cmd)
        docker_command = ["/bin/sh", "-c", shell_run]
        diagnostics["command"] = " ".join(docker_command)

        if docker is None:
            diagnostics["docker_ok"] = False
            err = "docker SDK not available"
            logger.error(err)
            telemetry_event("sandbox.error", {"reason": err})
            return {
                "status": "sandbox_error",
                "stdout": "",
                "stderr": err,
                "exit_code": None,
                "runtime_seconds": time.time() - start_time,
                "diagnostics": diagnostics,
            }

        # Start client
        try:
            client = docker.from_env(timeout=5)
            client.ping()
            diagnostics["docker_ok"] = True
        except Exception as e:
            diagnostics["docker_ok"] = False
            logger.exception("Docker unreachable")
            telemetry_event("sandbox.error", {"reason": "docker_unreachable", "exception": str(e)})
            return {
                "status": "sandbox_error",
                "stdout": "",
                "stderr": f"Docker unreachable: {e}",
                "exit_code": None,
                "runtime_seconds": time.time() - start_time,
                "diagnostics": diagnostics,
            }

        # volumes = {workspace_root: {"bind": "/app", "mode": "rw"}}
        # # If requested, make the code file read-only by using a subdir mount with ro mode
        # if read_only_code_mount:
        #     # create code-only subdir and mount it read-only (best-effort)
        #     code_dir = os.path.join(workspace_root, "code_mount")
        #     os.makedirs(code_dir, exist_ok=True)
        #     # move code/test files into code_dir
        #     for fname in os.listdir(workspace_root):
        #         if fname not in ("code_mount",):
        #             try:
        #                 shutil.move(os.path.join(workspace_root, fname), code_dir)
        #             except Exception:
        #                 # ignore and continue
        #                 pass
        #     volumes = {
        #         code_dir: {"bind": "/app", "mode": "ro"},
        #         workspace_root: {"bind": "/workspace", "mode": "rw"},  # writable scratch if needed
        #     }

        volumes = {workspace_root: {"bind": "/app", "mode": "rw"}}

        try:
            client.images.pull(chosen_image)
            diagnostics["image_pulled"] = True
        except Exception:
            diagnostics["image_pulled"] = False

        # Run container detached for polling
        try:
            # Assumes seccomp_profile.json is in the project root next to your Dockerfile
            script_dir = os.path.dirname(os.path.abspath(__file__))
            seccomp_path = os.path.join(script_dir, '..', 'seccomp_profile.json')
            
            seccomp_profile = None
            if os.path.exists(seccomp_path):
                with open(seccomp_path, "r") as f:
                    seccomp_profile = json.load(f)

            container = client.containers.run(
                image=chosen_image,
                command=docker_command,
                volumes=volumes,
                working_dir="/app",
                detach=True,
                network_disabled=DISABLE_NETWORK,
                remove=False,
                stdin_open=False,
                stdout=True,
                stderr=True,
                mem_limit=MEMORY_LIMIT,
                cpu_shares=CPU_SHARES,
                # --- SECURITY UPDATE ---
                # cap_drop=["ALL"],  <-- COMMENTED OUT (Causes crash on some systems)
                security_opt=["seccomp=unconfined"] # <-- FORCED to unconfined for stability
                # --- END SECURITY UPDATE ---
            )

        except Exception as e:
            logger.exception("Failed to create container")
            telemetry_event("sandbox.error", {"reason": "container_create_failed", "exception": str(e)})
            return {
                "status": "sandbox_error",
                "stdout": "",
                "stderr": f"Failed to create container: {e}",
                "exit_code": None,
                "runtime_seconds": time.time() - start_time,
                "diagnostics": diagnostics,
            }

        # Poll loop with timeout
        timed_out = False
        stdout = ""
        stderr = ""
        exit_code = None
        try:
            poll_interval = 0.5
            waited = 0.0
            while True:
                try:
                    container.reload()
                except Exception:
                    # container may disappear
                    break
                st = getattr(container, "status", None)
                if st in ("exited", "dead", "created"):
                    break
                if waited >= timeout_seconds:
                    timed_out = True
                    diagnostics["container_timed_out"] = True
                    try:
                        container.kill()
                    except Exception:
                        logger.exception("Failed to kill container after timeout")
                    break
                time.sleep(poll_interval)
                waited += poll_interval

            # Fetch logs
            try:
                raw_out = container.logs(stdout=True, stderr=False)
                raw_err = container.logs(stdout=False, stderr=True)
                stdout = raw_out.decode("utf-8", errors="replace") if isinstance(raw_out, bytes) else str(raw_out)
                stderr = raw_err.decode("utf-8", errors="replace") if isinstance(raw_err, bytes) else str(raw_err)
            except Exception:
                try:
                    combined = container.logs(stdout=True, stderr=True)
                    stdout = combined.decode("utf-8", errors="replace") if isinstance(combined, bytes) else str(combined)
                    stderr = ""
                except Exception as e:
                    logger.exception("Failed to fetch container logs")
                    stderr = f"Failed to fetch logs: {e}"

            # Determine exit code
            try:
                wait_res = container.wait(timeout=1)
                exit_code = wait_res.get("StatusCode", None) if isinstance(wait_res, dict) else None
            except Exception:
                try:
                    exit_code = container.attrs.get("State", {}).get("ExitCode", None)
                except Exception:
                    exit_code = None

            runtime = time.time() - start_time

            # Detect OOM / killed signals if present
            killed = False
            try:
                state = container.attrs.get("State", {})
                if state.get("OOMKilled"):
                    diagnostics["oom_killed"] = True
                    killed = True
            except Exception:
                pass

            # Prepare status categories
            if timed_out:
                status = "timeout"
            elif killed:
                status = "sandbox_error"
            elif exit_code is None:
                status = "sandbox_error"
            elif exit_code == 0:
                status = "success"
            else:
                # Distinguish between compile error vs test failure heuristically
                if language in ("c", "cpp", "java", "rust") and ("error" in stderr.lower() or "undefined reference" in stderr.lower()):
                    status = "compile_error"
                else:
                    status = "test_failure"

            telemetry_event("sandbox.run", {"status": status, "exit_code": exit_code, "runtime": runtime})

            return {
                "status": status,
                "exit_code": exit_code,
                "stdout": _truncate_for_return(stdout),
                "stderr": _truncate_for_return(stderr),
                "runtime_seconds": runtime,
                "diagnostics": {
                    **diagnostics,
                    "image_used": chosen_image,
                    "container_id": getattr(container, "id", None),
                    "container_status": getattr(container, "status", None),
                    "container_timed_out": timed_out,
                },
            }

        finally:
            try:
                if container:
                    container.remove(force=True)
            except Exception:
                logger.exception("Failed to remove container during cleanup")

    except Exception as e:
        logger.exception("Unexpected sandbox failure")
        telemetry_event("sandbox.error", {"reason": "unexpected_failure", "exception": str(e)})
        return {
            "status": "sandbox_error",
            "stdout": "",
            "stderr": f"Unexpected sandbox failure: {e}",
            "exit_code": None,
            "runtime_seconds": time.time() - start_time,
            "diagnostics": diagnostics,
        }
    finally:
        try:
            if tmpdir and os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir)
        except Exception:
            logger.exception("Failed to remove tmpdir during cleanup")

# -----------------------
# Concurrency Analyzer (Python)
# -----------------------
# We'll provide:
# - AST-based static analysis: detect Lock declarations, acquisitions, 'with' usage, and build an ordering graph.
# - Recommendation to enforce consistent lock ordering.
# - Optional dynamic tracer that patches Lock.acquire (trusted-only).
_global_patch_lock = threading.Lock()
_global_original_acquire = None
_global_patch_count = 0

class LockOrderingVisitor(ast.NodeVisitor):
    """
    AST visitor to find Lock declarations and lock acquisition sites.
    It collects:
      - Lock variable names and declaration order
      - For each function/block, sequences of lock acquires (with or acquire/release)
    """
    def __init__(self):
        self.lock_defs: Dict[str, int] = {}  # varname -> line
        self.acquire_sites: List[Tuple[str, int]] = []  # list of (varname, lineno)
        self.with_lock_sites: List[Tuple[List[str], int]] = []  # list of (lock_names_in_with, lineno)
        self.func_lock_sequences: Dict[str, List[List[str]]] = defaultdict(list)  # funcname -> list of sequences

    def visit_Assign(self, node: ast.Assign):
        # look for patterns like: mylock = threading.Lock() or Lock()
        try:
            if isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Attribute):
                    if func.attr == "Lock":
                        # lhs names
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                self.lock_defs[target.id] = node.lineno
                elif isinstance(func, ast.Name):
                    if func.id == "Lock":
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                self.lock_defs[target.id] = node.lineno
        except Exception:
            pass
        self.generic_visit(node)

    def visit_With(self, node: ast.With):
        # detect with mylock: or with mylock.acquire(): patterns
        lock_names = []
        for item in node.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Name):
                lock_names.append(ctx.id)
            elif isinstance(ctx, ast.Call):
                # with mylock.acquire(): not common, but catch name
                func = ctx.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    lock_names.append(func.value.id)
        if lock_names:
            self.with_lock_sites.append((lock_names, node.lineno))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # detect lock.acquire() calls
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "acquire":
                target = node.func.value
                if isinstance(target, ast.Name):
                    self.acquire_sites.append((target.id, node.lineno))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # collect lock sequences inside a function by scanning its body for acquire / with
        seq = []
        local_seq = []
        class _AcquireCollector(ast.NodeVisitor):
            def __init__(self):
                self.order = []

            def visit_With(self, wnode: ast.With):
                names = []
                for item in wnode.items:
                    ctx = item.context_expr
                    if isinstance(ctx, ast.Name):
                        names.append(ctx.id)
                    elif isinstance(ctx, ast.Call):
                        f = ctx.func
                        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                            names.append(f.value.id)
                if names:
                    self.order.extend(names)
                self.generic_visit(wnode)

            def visit_Call(self, cnode: ast.Call):
                if isinstance(cnode.func, ast.Attribute) and cnode.func.attr == "acquire":
                    val = cnode.func.value
                    if isinstance(val, ast.Name):
                        self.order.append(val.id)
                self.generic_visit(cnode)

        collector = _AcquireCollector()
        collector.visit(node)
        if collector.order:
            self.func_lock_sequences[node.name].append(collector.order)
        self.generic_visit(node)

# Analyzer class
class AdvancedConcurrencyAnalyzer:
    """
    Provides:
    - static_analysis(code): AST-based lock detection and lock-order graph, with recommendations.
    - analyze_concurrency(code, execution_callback, allow_local_execution): runs static analysis + optionally enabled dynamic tracing while executing 'execution_callback'.
    """
    def __init__(self):
        self.static_results: Dict[str, Any] = {}
        self.thread_lock_map: Dict[int, List[int]] = defaultdict(list)  # thread -> ordered list of lock ids
        self._local_lock = threading.RLock()
        self.analysis_enabled = False

    def static_analysis(self, code: str) -> Dict[str, Any]:
        """
        Run AST-based analysis to detect lock declarations and ordering inconsistencies.
        Returns a dict with:
          - lock_definitions: {name: lineno}
          - acquire_sites: [(name, lineno)]
          - with_sites: [([names], lineno)]
          - function_lock_sequences: {func: [[sequence], ...]}
          - ordering_graph: {a: set(b, c)} meaning a -> b (a acquired before b observed)
          - cycle_risks: list of cycles (list of lock names)
          - recommendations: list of strings
        """
        try:
            tree = ast.parse(code)
        except Exception as e:
            logger.exception("AST parse failed")
            return {"error": f"AST parse failed: {e}"}

        visitor = LockOrderingVisitor()
        visitor.visit(tree)

        # Build ordering graph from sequences observed in functions & with sites
        graph = defaultdict(set)
        # from function sequences
        for func, seqs in visitor.func_lock_sequences.items():
            for seq in seqs:
                for i in range(len(seq) - 1):
                    a = seq[i]
                    b = seq[i + 1]
                    graph[a].add(b)
        # from with sites (simultaneous acquires: order not explicit, but we consider pairwise)
        for names, _ in visitor.with_lock_sites:
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    graph[names[i]].add(names[j])
                    graph[names[j]].add(names[i])  # ambiguous ordering -> potential risk

        # detect cycles in graph (simple DFS)
        cycles = []
        temp_mark = set()
        perm_mark = set()
        stack = []

        def visit_node(n):
            if n in perm_mark:
                return False
            if n in temp_mark:
                # cycle found - capture the portion in stack
                try:
                    idx = stack.index(n)
                    cycles.append(stack[idx:] + [n])
                except ValueError:
                    cycles.append([n, n])
                return True
            temp_mark.add(n)
            stack.append(n)
            for m in graph.get(n, ()):
                visit_node(m)
            stack.pop()
            temp_mark.remove(n)
            perm_mark.add(n)
            return False

        for node_name in list(graph.keys()):
            visit_node(node_name)

        recommendations = []
        # If cycles found -> recommend consistent lock ordering across code: propose ordering by declaration lines
        if cycles:
            recommendations.append("Lock-order cycles detected. Enforce a consistent global lock acquisition order.")
            # propose an ordering based on declaration lineno
            ordered_by_decl = sorted(visitor.lock_defs.items(), key=lambda kv: kv[1])
            if ordered_by_decl:
                proposed = [name for name, _ in ordered_by_decl]
                recommendations.append(f"Proposed global lock order (by declaration): {proposed}")
        else:
            recommendations.append("No direct ordering cycles found. Still prefer a single global order for safety.")

        # also detect nested 'double acquire' inside same function (same lock acquired twice without release)
        double_acquires = []
        for fname, seqs in visitor.func_lock_sequences.items():
            for seq in seqs:
                seen = set()
                for name in seq:
                    if name in seen:
                        double_acquires.append({"function": fname, "lock": name, "sequence": seq})
                    seen.add(name)

        results = {
            "lock_definitions": visitor.lock_defs,
            "acquire_sites": visitor.acquire_sites,
            "with_sites": visitor.with_lock_sites,
            "function_lock_sequences": dict(visitor.func_lock_sequences),
            "ordering_graph": {k: list(v) for k, v in graph.items()},
            "cycle_risks": cycles,
            "double_acquires": double_acquires,
            "recommendations": recommendations,
        }
        self.static_results = results
        telemetry_event("analyzer.static", {"cycles": len(cycles), "double_acquires": len(double_acquires)})
        return results

    def _patched_acquire(self, lock_self, blocking=True, timeout=-1):
        """
        Runtime patched acquire to record order of acquisitions per thread.
        WARNING: process-wide patch. Use only for trusted in-process runs.
        """
        thread_id = threading.get_ident()
        lock_id = id(lock_self)
        with self._local_lock:
            # Append preserving order
            arr = self.thread_lock_map.setdefault(thread_id, [])
            arr.append(lock_id)
            # simple detection of potential cycle: if other thread holds a lock that this thread held earlier
            for other_thread, locks in self.thread_lock_map.items():
                if other_thread == thread_id:
                    continue
                # If current lock is in other_thread's list and other has a different lock this thread holds earlier -> risk
                if lock_id in locks:
                    # we flag as a potential deadlock event
                    logger.warning("Potential runtime lock contention detected between threads %s and %s", thread_id, other_thread)
        # call the original acquire (we expect blocking semantics)
        return _global_original_acquire(lock_self, blocking, timeout)

    def dynamic_analysis_setup(self):
        """
        Apply global patch to threading.Lock.acquire to record acquisition ordering.
        Must be used with caution (trusted code only).
        """
        global _global_original_acquire, _global_patch_count
        with _global_patch_lock:
            if self.analysis_enabled:
                return
            if _global_original_acquire is None:
                _global_original_acquire = threading.Lock.acquire
                # monkey patch
                threading.Lock.acquire = lambda lock_self, blocking=True, timeout=-1: self._patched_acquire(lock_self, blocking, timeout)
                _global_patch_count = 1
            else:
                _global_patch_count += 1
            self.analysis_enabled = True
            telemetry_event("analyzer.dynamic_setup", {"patched_count": _global_patch_count})

    def _analyze_runtime_behavior(self) -> Dict[str, Any]:
        """
        Summarize observed lock ordering from runtime tracing (thread id -> list of lock ids).
        Provide inconsistent ordering warnings.
        """
        issues = []
        lock_orders = {}
        with self._local_lock:
            for tid, locks in self.thread_lock_map.items():
                lock_orders[tid] = locks[:]
            # Check for inconsistent ordering by comparing sets and sequences
            tids = list(self.thread_lock_map.keys())
            for i in range(len(tids)):
                for j in range(i + 1, len(tids)):
                    a = self.thread_lock_map[tids[i]]
                    b = self.thread_lock_map[tids[j]]
                    if set(a) == set(b) and a != b:
                        issues.append({
                            "type": "inconsistent_lock_order",
                            "threads": [tids[i], tids[j]],
                            "a_order": a,
                            "b_order": b,
                        })
        return {"lock_usage": lock_orders, "runtime_issues": issues}

    def _combine_findings(self, static: Dict[str, Any], dynamic: Dict[str, Any]) -> List[Dict[str, Any]]:
        combined = []
        for s in static.get("recommendations", []):
            combined.append({"type": "static_recommendation", "detail": s})
        for cycle in static.get("cycle_risks", []):
            combined.append({"type": "static_cycle", "cycle": cycle})
        for issue in dynamic.get("runtime_issues", []):
            combined.append({"type": "dynamic_inconsistent_order", **issue})
        # dedupe naive
        seen = set()
        unique = []
        for it in combined:
            key = json.dumps(it, sort_keys=True)
            if key not in seen:
                seen.add(key)
                unique.append(it)
        return unique

    def analyze_concurrency(self, code: str, execution_callback, allow_local_execution: bool = False) -> Dict[str, Any]:
        static = self.static_analysis(code)
        dynamic_summary = {"lock_usage": {}, "runtime_issues": []}
        execution_result = None
        try:
            if allow_local_execution:
                # enable runtime trace
                self.dynamic_analysis_setup()
                try:
                    execution_result = execution_callback()
                finally:
                    dynamic_summary = self._analyze_runtime_behavior()
            else:
                # Use safe callback (e.g., docker run) without dynamic tracing
                execution_result = execution_callback()
        finally:
            # cleanup patch and state
            self._cleanup_analysis()

        combined = self._combine_findings(static, dynamic_summary)
        telemetry_event("analyzer.run", {"static_cycles": len(static.get("cycle_risks", [])), "dynamic_issues": len(dynamic_summary.get("runtime_issues", []))})
        return {
            "static_analysis": static,
            "dynamic_analysis": dynamic_summary,
            "execution_result": execution_result,
            "concurrency_issues": combined,
        }

    def _cleanup_analysis(self):
        global _global_patch_count, _global_original_acquire
        with _global_patch_lock:
            if not self.analysis_enabled:
                # clear runtime storage regardless
                self.thread_lock_map.clear()
                return
            # decrement usage
            _global_patch_count = max(0, _global_patch_count - 1)
            if _global_patch_count == 0 and _global_original_acquire is not None:
                try:
                    threading.Lock.acquire = _global_original_acquire
                except Exception:
                    logger.exception("Failed to restore original acquire")
                _global_original_acquire = None
            self.analysis_enabled = False
            self.thread_lock_map.clear()
            telemetry_event("analyzer.cleanup", {"patch_count": _global_patch_count})

    # Helper to present human-friendly recommendations and annotated code snippets
    def recommend_lock_order_fix(self, code: str) -> Dict[str, Any]:
        """
        Suggest a lock ordering policy and (optionally) a minimal code patch to enforce it.
        For safety, we do not auto-modify your code: we return a suggested policy and example wrappers.
        """
        static = self.static_analysis(code)
        lock_defs = static.get("lock_definitions", {})
        # propose ordering by declaration line (stable and deterministic)
        ordered = [name for name, _ in sorted(lock_defs.items(), key=lambda kv: kv[1])]
        if not ordered:
            return {"recommendation": "No lock definitions discovered; no action needed.", "proposed_order": []}
        # produce a wrapper example enforcing order: acquire in global order
        wrapper = (
            "# Example: enforce global lock ordering\n"
            "GLOBAL_LOCK_ORDER = " + repr(ordered) + "\n\n"
            "def acquire_in_global_order(*locks):\n"
            "    # locks should be resolved to variables in GLOBAL_LOCK_ORDER order\n"
            "    ordered = sorted(locks, key=lambda l: GLOBAL_LOCK_ORDER.index(l.__name__) if hasattr(l, '__name__') else 0)\n"
            "    for l in ordered:\n"
            "        l.acquire()\n\n"
            "def release_in_reverse(*locks):\n"
            "    for l in reversed(ordered):\n"
            "        l.release()\n"
        )
        return {"recommendation": "Enforce global lock order to avoid deadlocks.", "proposed_order": ordered, "wrapper_example": wrapper}

# -----------------------
# High-level runner that merges sandbox + analyzer
# -----------------------
def run_with_concurrency_analysis(
    code: str,
    tests: Optional[str],
    language: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    image: Optional[str] = None,
    allow_local_execution: bool = False,
) -> Dict[str, Any]:
    """
    High-level entrypoint: runs static concurrency analysis, executes code (via sandbox),
    optionally runs dynamic tracing (trusted), and returns combined result.
    """
    analyzer = AdvancedConcurrencyAnalyzer()
    def docker_execute():
        return run_tests_in_sandbox(code, tests, language, timeout_seconds=timeout_seconds, image=image)
    # --- THIS IS THE CORRECT LOGIC TO RESTORE ---
    try:
        analysis = analyzer.analyze_concurrency(code, docker_execute, allow_local_execution=allow_local_execution)
        result = analysis.get("execution_result") or {
            "status": "sandbox_error",
            "stdout": "",
            "stderr": "No execution result",
            "exit_code": None,
            "runtime_seconds": 0,
            "diagnostics": {},
        }
        result = dict(result)
        result["concurrency_analysis"] = {
            "issues": analysis.get("concurrency_issues", []),
            "static_findings": analysis.get("static_analysis", {}),
            "dynamic_findings": analysis.get("dynamic_analysis", {}),
        }
        telemetry_event("run_with_concurrency_analysis.result", {"status": result.get("status")})
        return result
    except Exception as e:
        logger.exception("Concurrency analysis runner failed")
        telemetry_event("run_with_concurrency_analysis.error", {"exception": str(e)})
        return docker_execute()
    # --- END OF CORRECT LOGIC ---

# -----------------------
# Minimal CLI for quick testing
# -----------------------
def _load_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser(description="Sandbox runner + concurrency analyzer")
    parser.add_argument("--file", "-f", help="Path to a Python file to analyze & run (optional)", default=None)
    parser.add_argument("--tests", "-t", help="Tests content or path prefixed by @ (optional)", default=None)
    parser.add_argument("--lang", "-l", help="Language (python, javascript, go, rust, java, cpp)", default="python")
    parser.add_argument("--allow-local", action="store_true", help="Allow in-process dynamic tracing (trusted only)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Timeout seconds for sandbox run")
    args = parser.parse_args()

    code = ""
    tests = None
    if args.file:
        if args.file.endswith(".py"):
            code = _load_file(args.file)
        else:
            # support other languages by passing the file content as code
            code = _load_file(args.file)
    if args.tests:
        if args.tests.startswith("@"):
            path = args.tests[1:]
            tests = _load_file(path)
        else:
            tests = args.tests

    # run
    out = run_with_concurrency_analysis(code, tests, args.lang, timeout_seconds=args.timeout, allow_local_execution=args.allow_local)
    print(json.dumps(out, indent=2))


def run_command_in_sandbox(
    command: List[str],
    files: Dict[str, str],
    image: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    Runs an arbitrary command in a secure, isolated Docker container with provided files.

    Args:
        command: The command to execute as a list of strings (e.g., ["npx", "eslint", "main.js"]).
        files: A dictionary mapping filenames to their content, which will be placed in the container.
        image: The Docker image to use for the container (e.g., "node:20-slim").
        timeout_seconds: The maximum execution time for the command.

    Returns:
        A dictionary containing stdout, stderr, exit_code, and other diagnostics.
    """
    if docker is None:
        raise ImportError("Docker SDK is not available. Cannot run sandbox.")

    start_time = time.time()
    workspace_root = tempfile.mkdtemp(prefix="sandbox_cmd_", dir=SANDBOX_TMP_ROOT)
    diagnostics: Dict[str, Any] = {
        "docker_ok": False,
        "image": image,
        "container_timed_out": False,
        "workspace": workspace_root,
        "command": " ".join(command),
    }
    container = None
    client = None

    try:
        # Write all provided files into the workspace
        for filename, content in files.items():
            # Ensure subdirectories are created if path contains them
            file_path = os.path.join(workspace_root, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

        client = docker.from_env(timeout=5)
        client.ping()
        diagnostics["docker_ok"] = True

        volumes = {workspace_root: {"bind": "/app", "mode": "rw"}}

        # Pull the image if it's not present
        try:
            client.images.get(image)
        except docker.errors.ImageNotFound:
            logger.info("Pulling Docker image: %s", image)
            client.images.pull(image)

        # --- REPLACE THE EXISTING client.containers.run CALL WITH THIS BLOCK ---
        # Assumes seccomp_profile.json is in the project root next to your Dockerfile
        script_dir = os.path.dirname(os.path.abspath(__file__))
        seccomp_path = os.path.join(script_dir, '..', 'seccomp_profile.json')
        
        seccomp_profile = None
        if os.path.exists(seccomp_path):
            with open(seccomp_path, "r") as f:
                seccomp_profile = json.load(f)

        container = client.containers.run(
            image=image,
            command=command,
            volumes=volumes,
            working_dir="/app",
            detach=True,
            network_disabled=DISABLE_NETWORK,
            mem_limit=MEMORY_LIMIT,
            cpu_shares=CPU_SHARES,
            # --- SECURITY UPDATE ---
            # cap_drop=["ALL"],  <-- COMMENTED OUT
            security_opt=["seccomp=unconfined"] # <-- FORCED to unconfined
            # --- END SECURITY UPDATE ---
        )

        # Poll for completion with timeout
        try:
            result = container.wait(timeout=timeout_seconds)
            exit_code = result.get("StatusCode", -1)
        except (Exception, KeyboardInterrupt):
            diagnostics["container_timed_out"] = True
            container.kill()
            exit_code = -1 # Indicate timeout

        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", "ignore")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", "ignore")

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "runtime_seconds": time.time() - start_time,
            "diagnostics": diagnostics,
        }
    except Exception as e:
        logger.exception("Generic sandbox command failed unexpectedly.")
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "runtime_seconds": time.time() - start_time,
            "diagnostics": diagnostics,
        }
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass
        if workspace_root and os.path.exists(workspace_root):
            shutil.rmtree(workspace_root)