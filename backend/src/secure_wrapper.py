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
import difflib
import traceback

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
    # --- SIGNATURE CHANGE ---
    # Receives pre-abstracted files and the original files for diffing.
    abstracted_project_files: Dict[str, str],
    original_project_files: Dict[str, str],
    # --- END SIGNATURE CHANGE ---
    provider_name: str,
    model: Optional[str],
    task: Optional[str],
    error_log: str,
    token_saver: bool,
    api_keys: Optional[dict] = None,
    provider_timeout: Optional[int] = None
) -> Dict[str, Any]:
    """
    Final, production-hardened orchestrator that now operates on PRE-ABSTRACTED code
    to ensure zero-knowledge principles are maintained on the server.
    """
    provider_timeout = provider_timeout or DEFAULT_PROVIDER_TIMEOUT
    _ensure_size_ok(abstracted_project_files)

    try:
        # --- STEP 1: PRIVACY LAYERS (REMOVED) ---
        # Redaction and abstraction are now handled client-side. This function
        # receives already-sanitized code, ensuring the server never sees the original source.
        files_for_prompt = abstracted_project_files

        # --- STEP 2: BUILD PROMPT AND CALL PROVIDER (Logic remains the same) ---
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
            # If the model returns nothing, we return the initial abstracted files.
            return {"result": abstracted_project_files, "notice": "Model did not return any modified files.", "analysis": analysis}

        # --- STEP 3: RESTORATION (REMOVED) ---
        # The backend NO LONGER restores anything. The validation loop and all subsequent
        # steps operate on the abstracted code. The frontend is responsible for final restoration.
        repaired_files = modified_files.copy()

        # --- STEP 4: INTELLIGENT CORRECTION LOOP (Logic remains the same) ---
        # This powerful feature works perfectly on abstracted code, as linters and
        # syntax checkers are concerned with structure, not variable names.
        last_known_error = None
        for attempt in range(MAX_CORRECTION_ATTEMPTS):
            # 4.1 Run the powerful, multi-tool validator on the AI's latest ABSTRACTED fix
            current_validation = validate_files(repaired_files)
            error_findings = []
            for file_path, report in current_validation.get("files", {}).items():
                for finding in report.get("findings", []):
                    if finding.get("severity") == "error":
                        error_findings.append({"file": file_path, **finding})

            if not error_findings:
                last_known_error = None # Success
                break

            last_known_error = f"In file '{error_findings[0].get('file')}': {error_findings[0].get('message')}"

            # 4.2 If invalid, build a precise correction prompt with the ABSTRACTED code and retry
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

        # --- STEP 5: FINAL SANDBOX AND OUTPUT (UPGRADED) ---
        if last_known_error:
            logger.error(f"AI failed to produce a valid fix after {MAX_CORRECTION_ATTEMPTS} attempts.")
            return {
                "result": repaired_files, # Return the last known ABSTRACTED attempt
                "analysis": analysis,
                "notice": f"AI Correction Failed. The AI's suggested code was invalid and could not be fixed after {MAX_CORRECTION_ATTEMPTS} attempts. Last known error: {last_known_error}",
                "sandbox_result": None,
            }

        # SUCCESS PATH
        # The final result from the backend is the corrected, but still ABSTRACTED, code.
        final_abstracted_files = {**abstracted_project_files, **repaired_files}
        
        # Sandbox execution can still run on the abstracted code for a final check.
        main_file_path = _detect_main_file(final_abstracted_files)
        sandbox_result = None
        if RUN_SANDBOX and main_file_path:
            # Note: We don't have original tests, so we can only run placeholder/generated tests.
            sandbox_result = run_tests_in_sandbox(
                code=final_abstracted_files[main_file_path],
                tests=None, # Tests are not sent to the server in the new flow for privacy.
                language=language_hint_from_filename(main_file_path),
            )

        # The output result is now always in the ABSTRACTED format.
        output_result: Dict[str, Any]
        if token_saver:
            diffs: Dict[str, str] = {}
            # To maintain the zero-knowledge boundary, the diff is now between the
            # original SUBMITTED files and the final CORRECTED files.
            # The client will apply this diff to its original code.
            for path in sorted(repaired_files.keys()):
                original_content = original_project_files.get(path, "")
                # The frontend will be responsible for restoring the new_content before applying the diff
                new_content = final_abstracted_files.get(path, "")
                
                # We need to restore both before diffing to get a meaningful diff
                # Since server can't restore, we must return the full corrected abstracted file
                # and let the client do the diff.
                # THEREFORE, FOR SIMPLICITY AND SECURITY, WE ADJUST THE LOGIC:
                # In token_saver mode, we now return the MODIFIED ABSTRACTED files only.
                # The client will be responsible for diffing against its original files.
            output_result = repaired_files
        else:
            output_result = final_abstracted_files
            
        return {
            "result": output_result,
            "analysis": analysis,
            "notice": "Debug process completed successfully.",
            "sandbox_result": sandbox_result,
        }

    except Exception as e:
        logger.exception("An unhandled error occurred in the processing pipeline.")
        error_details = traceback.format_exc()
        notice = f"An unexpected error occurred: {type(e).__name__}: {e}"
        analysis = f"Processing failed due to a fatal error.\n\nDEBUG INFO:\n{error_details}"
        # Return the original abstracted files on fatal error
        return { "result": abstracted_project_files, "notice": notice, "analysis": analysis }
