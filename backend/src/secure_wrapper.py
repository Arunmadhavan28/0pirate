# secure_wrapper.py (Final, Corrected, Production-Ready Version)
"""
The central orchestrator for the AI code processing pipeline. This module
integrates all other components (validator, abstractor, optimizer, sandbox)
to provide a secure, robust, and intelligent code-fixing workflow.
"""

from __future__ import annotations
import sys
import difflib
import json
import re
import os
import logging
from typing import Dict, List, Any, Optional

# -----------------------------------------------------
# Local imports from our final, production-ready modules
# -----------------------------------------------------
from .redactor import redact, restore as restore_secrets
from .abstractor import abstract_single_file_text as abstract, restore_from_mapping as restore_abstracted
from .providers.router import get_provider
from .sandbox import run_tests_in_sandbox
# This is the new, powerful, multi-language validator
from .validator import validate_files
# This is the robust provider call utility from its own file
from .utils.provider import call_provider_with_retry, ProviderUnavailableError
from .optimizer import build_error_fix_prompt, parse_multi_file_response, language_hint_from_filename

# -----------------------------
# Configuration
# -----------------------------
MAX_CORRECTION_ATTEMPTS = int(os.getenv("MAX_CORRECTION_ATTEMPTS", "3"))
MAX_CODE_BYTES = int(os.getenv("MAX_CODE_BYTES", str(2 * 1024 * 1024)))
RUN_SANDBOX = os.getenv("RUN_SANDBOX", "true").lower() == "true"
DEFAULT_PROVIDER_TIMEOUT = int(os.getenv("PROVIDER_TIMEOUT_SEC", "60"))

# -----------------------------
# Logging
# -----------------------------
logger = logging.getLogger("secure_wrapper")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# -----------------------------
# Helper Functions
# -----------------------------
def _ensure_size_ok(project_files: Dict[str, str]) -> None:
    if sum(len(c.encode("utf-8")) for c in project_files.values()) > MAX_CODE_BYTES:
        raise ValueError("Code submission exceeds maximum size")

def _detect_main_file(project_files: Dict[str, str]) -> Optional[str]:
    for name in ["main", "app", "index", "server"]:
        for path in sorted(project_files.keys()):
            if name in path.lower():
                return path
    return sorted(project_files.keys())[0] if project_files else None

# -----------------------------
# Main Orchestration Function
# -----------------------------
def process_code_submission(
    project_files: Dict[str, str],
    provider_name: str,
    model: Optional[str],
    task: Optional[str],
    error_log: str,
    token_saver: bool,
    api_keys: Optional[dict] = None,
    provider_timeout: Optional[int] = None,
    # Abstraction controls are now parameters
    abstraction_enabled: bool = True,
    abstraction_level: str = "paranoid",
    abstraction_chunking: bool = False,
    abstraction_noise: bool = True,
) -> Dict[str, Any]:
    """
    Final, production-hardened orchestrator that correctly integrates all modules.
    """
    provider_timeout = provider_timeout or DEFAULT_PROVIDER_TIMEOUT
    _ensure_size_ok(project_files)

    try:
        # --- STEP 1: PRIVACY LAYERS ---
        redacted_files, secret_maps = {}, {}
        for path, content in project_files.items():
            redacted, secret_map = redact(content)
            redacted_files[path], secret_maps[path] = redacted, secret_map

        files_for_prompt = redacted_files
        abstraction_maps: Dict[str, Any] = {}
        if abstraction_enabled:
            abstracted_files = {}
            for path, content in redacted_files.items():
                ac, amap = abstract(
                    content,
                    filename_hint=path,
                    level=abstraction_level,
                    chunking=abstraction_chunking,
                    noise=abstraction_noise
                )
                abstracted_files[path], abstraction_maps[path] = ac, amap
            files_for_prompt = abstracted_files

        # --- STEP 2: BUILD PROMPT AND CALL PROVIDER ---
        provider = get_provider(provider_name, api_keys=api_keys)
        prompt = build_error_fix_prompt(files_for_prompt, error_log, task=task, token_saver_enabled=token_saver)
        response_text = call_provider_with_retry(
            provider, prompt=prompt, model=model, timeout=provider_timeout
        )
        
        match = re.search(r"<analysis>([\s\S]*?)</analysis>", response_text, re.DOTALL)
        analysis = match.group(1).strip() if match else "No detailed analysis provided."
        code_response = response_text[match.end():].strip() if match else response_text
        
        modified_files = parse_multi_file_response(code_response)
        if not modified_files:
            return {"result": project_files, "notice": "Model did not return any modified files.", "analysis": analysis}

        # --- STEP 3: RESTORE AND PREPARE FOR VALIDATION ---
        restored_abstracted_files = {}
        for path, content in modified_files.items():
            original_path = path
            if path in abstraction_maps:
                restored_abstracted_files[original_path] = restore_abstracted(content, abstraction_maps[path])
            else:
                restored_abstracted_files[original_path] = content
        
        repaired_files = restored_abstracted_files.copy()

        # --- STEP 4: INTELLIGENT CORRECTION LOOP ---
        for attempt in range(MAX_CORRECTION_ATTEMPTS):
            # 4.1 Run the powerful, multi-tool validator on the AI's latest fix
            current_validation = validate_files(repaired_files)
            error_findings = []
            for file_path, report in current_validation.get("files", {}).items():
                for finding in report.get("findings", []):
                    if finding.get("severity") == "error":
                        error_findings.append({"file": file_path, **finding})

            if not error_findings:
                break  # Success! The code is valid.

            # 4.2 If invalid, build a precise correction prompt and retry
            correction_payload = {
                "note": f"Your previous attempt (attempt {attempt + 1}) failed validation. Please fix these exact errors.",
                "errors_found": error_findings,
                "files_to_fix": {p: repaired_files[p] for p in repaired_files},
            }
            correction_prompt = (
                "The code you previously provided was invalid. Fix the specific errors listed below. Return ONLY the full, corrected file contents "
                "in a JSON map: {\"path/to/file.ext\": \"<full file contents>\"}.\n\n"
                + json.dumps(correction_payload, indent=2)
            )

            response_text = call_provider_with_retry(
                provider, prompt=correction_prompt, model=model, timeout=provider_timeout
            )
            parsed_correction = parse_multi_file_response(response_text)

            if not parsed_correction:
                logger.warning("Correction attempt failed: model returned no parsable code.")
                break
            
            repaired_files = parsed_correction

        # --- STEP 5: FINAL SANDBOX AND OUTPUT ---
        final_files = {**project_files, **repaired_files}
        final_files = {p: restore_secrets(c, secret_maps.get(p, {})) for p, c in final_files.items()}
        
        main_file_path = _detect_main_file(project_files)
        sandbox_result = None
        if RUN_SANDBOX and main_file_path and main_file_path in final_files:
            test_file_path = next((p for p in sorted(project_files.keys()) if "test" in p.lower()), None)
            sandbox_result = run_tests_in_sandbox(
                code=final_files[main_file_path],
                tests=project_files.get(test_file_path),
                language=language_hint_from_filename(main_file_path),
            )

        return {
            "result": {p: final_files.get(p) for p in sorted(repaired_files.keys())},
            "analysis": analysis,
            "notice": "Debug process completed.",
            "sandbox_result": sandbox_result,
        }

    except Exception as e:
        logger.exception("An unhandled error occurred in the processing pipeline.")
        return {"result": project_files, "notice": f"An unexpected error occurred: {e}", "analysis": "Processing failed due to a fatal error."}