# secure_wrapper.py (production-ready, hardened for privacy & stability)
from __future__ import annotations

import sys
import difflib
import json
import time
import random
import re
import os
import logging
import ast
from typing import Dict, List, Any, Optional, Callable

# -----------------------------------------------------
# Local imports (ensure these modules exist in project)
# -----------------------------------------------------

from .redactor import redact, restore as restore_secrets
from .abstractor import abstract, restore as restore_abstracted
from .providers.router import get_provider
from .sandbox import run_tests_in_sandbox
from .validator import validate_code, validate_and_fix

# --- NEW: Import only the new multi-file functions ---
from .optimizer import build_multi_file_task_prompt, parse_multi_file_response
# -----------------------------
# Configuration / Feature flags
# -----------------------------
MAX_CORRECTION_ATTEMPTS = int(os.getenv("MAX_CORRECTION_ATTEMPTS", "3"))
MAX_API_RETRIES = int(os.getenv("MAX_API_RETRIES", "6"))
BASE_API_DELAY = float(os.getenv("BASE_API_DELAY", "3.0"))
MAX_FAST_FIX_ATTEMPTS = int(os.getenv("MAX_FAST_FIX_ATTEMPTS", "10"))
MAX_CODE_BYTES = int(os.getenv("MAX_CODE_BYTES", str(2 * 1024 * 1024)))  # 2MB

AUTO_APPLY_SAFE_FIXES = os.getenv("AUTO_APPLY_SAFE_FIXES", "false").lower() == "true"
STRICT_VALIDATOR_BLOCKS = os.getenv("STRICT_VALIDATOR_BLOCKS", "true").lower() == "true"

RUN_SANDBOX = os.getenv("RUN_SANDBOX", "true").lower() == "true"
SANDBOX_VERBOSE = os.getenv("SANDBOX_VERBOSE", "false").lower() == "true"

DEFAULT_PROVIDER_TIMEOUT = int(os.getenv("PROVIDER_TIMEOUT_SEC", "60"))

# -----------------------------
# Logging & Telemetry
# -----------------------------
logger = logging.getLogger("secure_wrapper")
if not logger.handlers:
    ch = logging.StreamHandler(stream=sys.stderr)
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))
    logger.addHandler(ch)
logger.setLevel(os.getenv("SECURE_WRAPPER_LOG_LEVEL", "INFO"))

telemetry_hook: Optional[Callable[[str, Dict[str, Any]], None]] = None


def register_telemetry_hook(hook: Callable[[str, Dict[str, Any]], None]) -> None:
    global telemetry_hook
    telemetry_hook = hook


def _emit_telemetry(name: str, data: Dict[str, Any]) -> None:
    try:
        if telemetry_hook:
            telemetry_hook(name, data)
    except Exception:
        logger.debug("Telemetry hook failure", exc_info=True)


# -----------------------------
# Provider utilities
# -----------------------------
def _is_transient_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return any(t in s for t in ("429", "rate limit", "timeout", "temporarily", "unavailable"))


def call_provider_with_retry(provider, timeout: Optional[int] = None, max_retries: Optional[int] = None, **kwargs):
    max_retries = max_retries or MAX_API_RETRIES
    attempt = 0
    last_exc = None
    start = time.time()
    while attempt < max_retries:
        try:
            args = {**kwargs, "timeout": timeout} if timeout else kwargs
            resp = provider.complete(**args)
            latency = time.time() - start
            _emit_telemetry("provider_call", {"provider": getattr(provider, "name", "unknown"), "attempt": attempt + 1, "latency": latency})
            return resp
        except Exception as e:
            last_exc = e
            transient = _is_transient_error(e)
            logger.warning("Provider failed attempt %d/%d transient=%s: %s", attempt + 1, max_retries, transient, str(e))
            _emit_telemetry("provider_error", {"provider": getattr(provider, "name", "unknown"), "attempt": attempt + 1, "transient": transient})
            if attempt < max_retries - 1 and transient:
                delay = BASE_API_DELAY * (2 ** attempt) + random.uniform(0, 1.0)
                time.sleep(delay)
                attempt += 1
                continue
            break
    raise last_exc or Exception("Provider unavailable")


# -----------------------------
# Validator formatter
# -----------------------------
def _format_validator_output(vreport: Dict[str, Any]) -> Dict[str, Any]:
    findings = vreport.get("findings", []) or []
    return {
        "status": vreport.get("status", "ok"),
        "errors": [f for f in findings if f.get("severity") == "error"],
        "warnings": [f for f in findings if f.get("severity") == "warning"],
        "infos": [f for f in findings if f.get("severity") == "info"],
        "categories": vreport.get("categories", {}),
        "message": vreport.get("message", ""),
        "suggested_code": vreport.get("suggested_code"),
        "diff": vreport.get("diff"),
        "changes": vreport.get("changes", []),
    }


# -----------------------------
# Sandbox helpers
# -----------------------------
_COMPILE_PATTERNS = [r"error: ", r"could not compile", r"compilation terminated", r"javac: "]
_TEST_FAIL_PATTERNS = [r"=== FAILURES ===", r"AssertionError", r"FAIL\s+\[", r"\bfailures\b"]
_RUNTIME_ERROR_PATTERNS = [r"Traceback \(most recent call last\):", r"ReferenceError|TypeError|SyntaxError", r"panic:"]


def _detect_failure_category(stdout: str) -> str:
    text = stdout or ""
    for p in _COMPILE_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return "compile_error"
    for p in _TEST_FAIL_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return "test_failure"
    for p in _RUNTIME_ERROR_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return "runtime_error"
    return "test_failure"


def _normalize_sandbox_output(result: Dict[str, Any]) -> Dict[str, Any]:
    status = result.get("status")
    category = "success" if status == "success" else "failure"
    if status == "failure":
        category = _detect_failure_category(result.get("stdout", ""))
    if status == "error":
        category = "timeout" if result.get("diagnostics", {}).get("container_timed_out") else "infra_error"
    if not SANDBOX_VERBOSE:
        return {"status": status, "stdout": result.get("stdout", "")[:4096], "exit_code": result.get("exit_code"), "category": category}
    return {**result, "category": category}


# -----------------------------
# Helper: Validate final code (added for safety)
# -----------------------------
def _is_valid_python(code: str) -> bool:
    try:
        if not code or not isinstance(code, str):
            return False
        ast.parse(code)
        return True
    except Exception:
        return False


# -----------------------------
# HAIS pipeline (Preserved as requested)
# -----------------------------
def _run_hais_pipeline(raw_code: str, provider_name: str, model: Optional[str], language: str,
                       token_saver: bool, validator_output: Dict[str, Any], abstraction_enabled: bool,
                       tests: Optional[str] = None, provider_timeout: Optional[int] = None) -> Dict[str, Any]:
    provider_timeout = provider_timeout or DEFAULT_PROVIDER_TIMEOUT
    try:
        provider = get_provider(provider_name)
    except Exception:
        return {"result": None, "notice": "Provider init failed", "provider_status": "offline", "validator": validator_output}

    working_code = raw_code
    if AUTO_APPLY_SAFE_FIXES and validator_output.get("suggested_code"):
        working_code = validator_output["suggested_code"]

    abstract_mapping = {}
    try:
        if abstraction_enabled:
            working_code, abstract_mapping = abstract(working_code, chunking=True, level="paranoid", add_noise=True)
    except Exception:
        abstract_mapping = {}

    try:
        # Stage 1: Analysis
        analysis_prompt = build_hais_analysis_prompt(working_code, language)

        try:
            analysis_resp = call_provider_with_retry(provider, prompt=analysis_prompt, model=model, timeout=provider_timeout)
        except Exception as e:
            logger.warning("HAIS analysis stage provider call failed: %s", e)
            fallback = _run_simple_fix(raw_code, "hais_analysis_fallback")
            if fallback.get("result"):
                return {"result": fallback.get("result"), "notice": "HAIS analysis fallback applied", "provider_status": fallback.get("provider_status"), "validator": validator_output}
            return {"result": None, "notice": f"HAIS analysis failed: {e}", "provider_status": "offline", "validator": validator_output}

        raw_plan = extract_code(analysis_resp) or "[]"
        try:
            plan = json.loads(raw_plan)
        except Exception:
            match = re.search(r"(\[.*\])", raw_plan, re.DOTALL)
            plan = json.loads(match.group(1)) if match else []
        if not isinstance(plan, list):
            plan = []

        # Stage 2: Micro-fixes
        current_code = working_code
        for issue in plan:
            try:
                micro_prompt = build_hais_micro_fix_prompt(current_code, language, issue)
                try:
                    resp = call_provider_with_retry(provider, prompt=micro_prompt, model=model, timeout=provider_timeout)
                except Exception:
                    logger.debug("micro-fix provider call failed for issue %s; continuing", issue)
                    continue
                current_code = extract_code(resp) or current_code
            except Exception:
                continue

        # Stage 3: Integration
        integration_prompt = build_hais_integration_prompt(working_code, current_code, language, plan)
        try:
            resp = call_provider_with_retry(provider, prompt=integration_prompt, model=model, timeout=provider_timeout)
        except Exception as e:
            logger.warning("HAIS integration stage provider call failed: %s", e)
            fallback = _run_simple_fix(raw_code, "hais_integration_fallback")
            if fallback.get("result"):
                return {"result": fallback.get("result"), "notice": "HAIS integration fallback applied", "provider_status": fallback.get("provider_status"), "validator": validator_output}
            return {"result": None, "notice": f"HAIS integration failed: {e}", "provider_status": "offline", "validator": validator_output}

        integrated = extract_code(resp) or current_code

        if abstraction_enabled:
            try:
                integrated = restore_abstracted(integrated, abstract_mapping)
            except Exception:
                pass

        final_report = validate_and_fix(integrated, auto_apply=False)

        sandbox_result = None
        if RUN_SANDBOX:
            try:
                sandbox_result = _normalize_sandbox_output(run_tests_in_sandbox(integrated, tests, language))
            except Exception:
                sandbox_result = {"status": "error", "category": "infra_error"}

        if token_saver:
            diff = "\n".join(difflib.unified_diff(raw_code.splitlines(), integrated.splitlines(), fromfile="original", tofile="fixed", lineterm=""))
            return {"result": diff or "No changes", "notice": "HAIS diff done", "provider_status": "ok", "validator": _format_validator_output(final_report), "sandbox": sandbox_result}
        
        if not _is_valid_python(integrated):
            logger.warning("HAIS produced invalid python after integration; trying simple-fix fallback")
            fallback = _run_simple_fix(raw_code, "hais_final_validation_fallback")
            if fallback.get("result"):
                return {"result": fallback.get("result"), "notice": "HAIS final validation fallback applied", "provider_status": fallback.get("provider_status"), "validator": validator_output, "sandbox": sandbox_result}
            return {"result": restore_abstracted(raw_code, abstract_mapping) if abstraction_enabled else raw_code, "notice": "HAIS failed: produced invalid code and fallback failed", "provider_status": "offline", "validator": validator_output, "sandbox": sandbox_result}

        return {"result": integrated, "notice": "HAIS complete", "provider_status": "ok", "validator": _format_validator_output(final_report), "sandbox": sandbox_result}
    except Exception as e:
        try:
            logger.warning("HAIS top-level exception: %s; attempting simple-fix fallback", e)
            fallback = _run_simple_fix(raw_code, "hais_top_level_fallback")
            if fallback.get("result"):
                return {"result": fallback.get("result"), "notice": "HAIS top-level fallback applied", "provider_status": fallback.get("provider_status"), "validator": validator_output}
        except Exception as inner:
            logger.debug("simple-fix fallback crashed: %s", inner)
        restored = restore_abstracted(raw_code, abstract_mapping) if abstraction_enabled else raw_code
        return {"result": restored, "notice": f"HAIS failed: {e}", "provider_status": "ok", "validator": validator_output}

# -----------------------------
# Entrypoints (FIXED and COMPLETE)
# -----------------------------
def _ensure_size_ok(project_files: Dict[str, str]) -> None:
    """Checks if the total size of all file contents is within the limit."""
    total_bytes = sum(len(content.encode("utf-8")) for content in project_files.values())
    if total_bytes > MAX_CODE_BYTES:
        raise ValueError(f"Code too large: {total_bytes} bytes > {MAX_CODE_BYTES}")


def process_code_submission(
    project_files: Dict[str, str],
    provider_name: str,
    model: Optional[str],
    task: str,
    token_saver: bool,
    abstraction_enabled: bool,
    api_keys: Optional[dict] = None,
    tests: Optional[str] = None,
    provider_timeout: Optional[int] = None
) -> Dict[str, Any]:
    """
    Processes a multi-file project submission, handling redaction, abstraction,
    prompt generation, provider calls, and response parsing.
    """
    provider_timeout = provider_timeout or DEFAULT_PROVIDER_TIMEOUT
    _ensure_size_ok(project_files)

    # 1. Redact secrets from all files
    redacted_files: Dict[str, str] = {}
    secret_maps: Dict[str, dict] = {}
    for path, content in project_files.items():
        try:
            redacted_code, secret_map = redact(content)
            redacted_files[path] = redacted_code
            secret_maps[path] = secret_map
        except Exception as e:
            logger.error(f"Redaction failed for file {path}: {e}", exc_info=True)
            redacted_files[path] = content
            secret_maps[path] = {}

    # --- FIX for Max Security (Part 1: Abstraction) ---
    abstraction_maps: Dict[str, dict] = {}
    if abstraction_enabled:
        logger.info("Max Security enabled. Performing code abstraction.")
        abstracted_files: Dict[str, str] = {}
        for path, content in redacted_files.items():
            try:
                abstracted_code, abstraction_map = abstract(content, add_noise=True, level="paranoid")
                abstracted_files[path] = abstracted_code
                abstraction_maps[path] = abstraction_map
            except Exception as e:
                logger.error(f"Abstraction failed for file {path}: {e}", exc_info=True)
                abstracted_files[path] = content # Fallback to non-abstracted content
        files_for_prompt = abstracted_files
    else:
        files_for_prompt = redacted_files
    # --- END of Max Security Fix (Part 1) ---

    try:
        # 3. Build the multi-file prompt
        prompt = build_multi_file_task_prompt(files_for_prompt, task)

        # 4. Get and call the provider
        provider = get_provider(provider_name, api_keys=api_keys)
        response_text = call_provider_with_retry(
            provider, prompt=prompt, model=model, timeout=provider_timeout
        )

        # 5. Parse the multi-file response
        modified_files = parse_multi_file_response(response_text)
        if not modified_files:
            return {"result": project_files, "notice": "Model did not return any modified files.", "provider_status": "ok"}

        # --- FIX for Max Security (Part 2: Restoration) ---
        restored_abstracted_files: Dict[str, str] = {}
        if abstraction_enabled:
            logger.info("Restoring abstracted code.")
            for path, content in modified_files.items():
                # Use the map for the specific file that was abstracted
                if path in abstraction_maps:
                    restored_abstracted_files[path] = restore_abstracted(content, abstraction_maps[path])
                else:
                    # This handles new files created by the LLM
                    restored_abstracted_files[path] = content
        else:
            restored_abstracted_files = modified_files
        # --- END of Max Security Fix (Part 2) ---
            
        # 7. Restore secrets
        final_files: Dict[str, str] = {}
        for path, content in restored_abstracted_files.items():
            secret_map_for_file = secret_maps.get(path, {})
            final_files[path] = restore_secrets(content, secret_map_for_file)
        
        # --- FIX for Token Saver ---
        # 8. If "Token Saver" is ON, generate diffs for each modified file
        if token_saver:
            logger.info("Token Saver enabled. Generating diffs.")
            diff_results: Dict[str, str] = {}
            for path, new_content in final_files.items():
                original_content = project_files.get(path, "")
                if original_content == new_content:
                    diff_results[path] = "No changes."
                    continue
                
                diff_lines = difflib.unified_diff(
                    original_content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                )
                diff_string = "".join(diff_lines)
                diff_results[path] = diff_string if diff_string else "No changes."
            
            return {
                "result": diff_results,
                "notice": f"Task '{task}' completed. Diffs generated.",
                "provider_status": "ok"
            }
        # --- END of Token Saver Fix ---

        # If Token Saver is OFF, return the full files
        return {
            "result": final_files,
            "notice": f"Task '{task}' completed successfully.",
            "provider_status": "ok",
        }

    except Exception as e:
        logger.exception("An error occurred during the code processing pipeline.")
        original_files_restored: Dict[str, str] = {}
        for path, content in redacted_files.items():
            original_files_restored[path] = restore_secrets(content, secret_maps.get(path, {}))
        
        return {
            "result": original_files_restored,
            "notice": f"An unexpected error occurred: {e}",
            "provider_status": "error"
        }


def run_general_task_pipeline(
    project_files: Dict[str, str],
    provider_name: str,
    model: Optional[str],
    task: str,
    api_keys: Optional[dict],
    token_saver: bool,
    abstraction_enabled: bool,
    provider_timeout: Optional[int] = None
) -> Dict[str, Any]:
    """
    Refactored version of run_general_task_pipeline for multi-file and BYOK.
    """
    return process_code_submission(
        project_files=project_files,
        provider_name=provider_name,
        model=model,
        task=task,
        token_saver=token_saver,
        abstraction_enabled=abstraction_enabled,
        api_keys=api_keys,
        provider_timeout=provider_timeout
    )


# -----------------------------
# Fallback Simple Fix Mode (Preserved as requested)
# -----------------------------
def _run_simple_fix(code: str, task: str) -> Dict[str, Any]:
    """
    Fallback path when HAIS pipeline or provider calls fail badly.
    Sends the broken code directly to provider with a simpler prompt.
    Returns a dict consistent with other entrypoints:
    {"result": <code or None>, "notice": <str>, "provider_status": "ok"/"offline"}
    """
    prompt = (
        "The following Python code is broken.\n\n"
        "Fix ALL syntax and structural errors and return ONLY the corrected code (no commentary, no extra text)."
    )
    try:
        try:
            provider = get_provider("default")
        except Exception:
            provider = get_provider(None)

        payload = prompt + "\n\n" + code
        resp = call_provider_with_retry(provider, prompt=payload, model=os.getenv("FALLBACK_MODEL", "gpt-4"), timeout=DEFAULT_PROVIDER_TIMEOUT)
        
        # This function is not available in the provided code, assuming a simple extraction or direct use
        try:
            from .parser import extract_code
            fixed = extract_code(resp) or resp
        except ImportError:
            fixed = resp # Fallback if extract_code is not available

        if not _is_valid_python(fixed):
            logger.warning("Simple-fix produced invalid python for task %s", task)
            return {"result": None, "notice": f"Fallback simple-fix produced invalid code for {task}", "provider_status": "offline"}

        return {"result": fixed, "notice": f"Fallback simple-fix for {task}", "provider_status": "ok"}
    except Exception as e:
        logger.error("Fallback simple-fix failed for %s: %s", task, e, exc_info=True)
        return {"result": None, "notice": f"Fallback simple-fix also failed: {e}", "provider_status": "offline"}