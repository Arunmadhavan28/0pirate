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
import redis
import hashlib


# -----------------------------------------------------
# Local imports from our final, production-ready modules
# -----------------------------------------------------
from .redactor import redact, restore as restore_secrets
from .abstractor import abstract_single_file_text as abstract, restore_from_mapping as restore_abstracted
from .providers.router import get_provider
from .sandbox import run_tests_in_sandbox
from .sandbox import run_command_in_sandbox
# This is the new, powerful, multi-language validator
from .validator import validate_files
from .validator import validate_files, detect_language as validator_detect_language
# This is the robust provider call utility from its own file
from .utils.provider import call_provider_with_retry, ProviderUnavailableError
from .config import settings
# --- Optimizer import (Safe version to avoid partial or circular import issues) ---
# --- Optimizer imports (final, production-ready) ---
# --- Optimizer Import ---
from . import optimizer as optimizer_module

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

redis_client = None
if settings.redis_url:
    try:
        redis_client = redis.from_url(settings.redis_url, decode_responses=True) # decode_responses=True makes it easier
        redis_client.ping() # Test the connection
        logger.info("Successfully connected to Redis cache.")
    except Exception as e:
        logger.error(f"Failed to connect to Redis at {settings.redis_url}: {e}. Caching will be disabled.")
        redis_client = None
else:
    logger.warning("REDIS_URL not set in config. Caching is disabled.")


# -----------------------------
# Helper Functions
# -----------------------------
def _ensure_size_ok(project_files: Dict[str, str]) -> None:
    if sum(len(c.encode("utf-8")) for c in project_files.values()) > MAX_CODE_BYTES:
        raise ValueError("Code submission exceeds maximum size")

def _detect_main_file(project_files: Dict[str, str], prefer_test: bool = False) -> Optional[str]:
    """Detects the most likely entry point or primary test file."""
    paths = sorted(project_files.keys())
    if not paths:
        return None

    # Prioritize specific test filenames if requested
    if prefer_test:
        for path in paths:
            if 'test' in path.lower() or 'spec' in path.lower():
                return path

    # Look for common main file names
    for name in ["main", "app", "index", "server"]:
        for path in paths:
            # Check for exact name or name as prefix before extension
            basename = os.path.basename(path)
            if basename.startswith(name + '.') or basename == name:
                 # Small heuristic: prefer shorter paths or common locations
                 if 'src/' in path or 'app/' in path or len(path.split('/')) <= 2:
                     return path

    # Fallback: Prefer non-test files if not looking for tests
    if not prefer_test:
        for path in paths:
            if 'test' not in path.lower() and 'spec' not in path.lower():
                return path

    # Ultimate fallback: first file
    return paths[0]

# -----------------------------
# Main Orchestration Function
# -----------------------------


def process_code_submission(
    abstracted_project_files: Dict[str, str],
    original_project_files: Dict[str, str],
    provider_name: str,
    model: Optional[str],
    task: str, # Changed from Optional[str] - task is now required
    error_log: Optional[str], # Keep error_log optional
    token_saver: bool,
    api_keys: Optional[dict] = None,
    provider_timeout: Optional[int] = None,
    use_cove_hardening: bool = False,
    # --- NEW Optional parameter for generate_code ---
    user_prompt_for_generation: Optional[str] = None,
    language_hint_for_generation: Optional[str] = None
) -> Dict[str, Any]:
    """
    Orchestrator now handles fix, generate_tests, and generate_code tasks.
    """
    provider_timeout = provider_timeout or DEFAULT_PROVIDER_TIMEOUT
    # Size check might be less relevant for generate_code if context files are small/absent
    if task != "generate_code":
        _ensure_size_ok(abstracted_project_files)

    try:
        # --- Common Setup ---
        provider = get_provider(provider_name, api_keys=api_keys)
        final_response_text = ""
        analysis = "Analysis not applicable for this task." # Default
        generated_files: Dict[str, str] = {}
        sandbox_result = None
        validation_result = None

        # --- Task-Specific Logic ---

        # === TASK: Generate Code ===
        if task == "generate_code":
            if not user_prompt_for_generation:
                raise ValueError("User prompt is required for the 'generate_code' task.")

            logger.info("Task: Generate Code initiated.")
            prompt = optimizer_module.buildgeneratecodeprompt(

                user_prompt=user_prompt_for_generation,
                context_files=abstracted_project_files or None, # Use uploaded files as context if present
                language_hint=language_hint_for_generation
            )
            # --- CACHE LOGIC for Generate Code ---
            cache_key_gen_code = None
            cached_response_gen_code = None
            can_use_cache = True # TODO: Check user plan

            if redis_client and can_use_cache:
                key_data_gen_code = f"gen_code:{provider_name}:{model or 'default'}:{prompt}"
                cache_key_gen_code = f"cache:{hashlib.sha256(key_data_gen_code.encode('utf-8')).hexdigest()}"
                try:
                    cached_response_gen_code = redis_client.get(cache_key_gen_code)
                    if cached_response_gen_code: logger.info(f"Cache HIT (Gen Code) for key {cache_key_gen_code[:15]}...")
                    else: logger.info(f"Cache MISS (Gen Code) for key {cache_key_gen_code[:15]}...")
                except Exception as e:
                    logger.error(f"Redis GET failed (Gen Code): {e}")
                    cached_response_gen_code = None

            if cached_response_gen_code:
                final_response_text = cached_response_gen_code
            else:
                final_response_text = call_provider_with_retry(
                    provider, prompt=prompt, model=model, timeout=provider_timeout
                )
                if redis_client and can_use_cache and cache_key_gen_code and final_response_text:
                    try:
                        redis_client.set(cache_key_gen_code, final_response_text, ex=3600)
                        logger.info(f"Stored (Gen Code) in cache: {cache_key_gen_code[:15]}...")
                    except Exception as e: logger.error(f"Redis SET failed (Gen Code): {e}")
            # --- END CACHE LOGIC ---

            generated_files = optimizer_module.parsemultifileresponse(final_response_text)

            if not generated_files:
                return {"result": {}, "notice": "Model did not return any generated code.", "analysis": analysis}

            # Run validation on the generated code
            logger.info("Running validation on generated code...")
            try:
                # Use validator's detectlanguage for consistency
                validation_result = validate_files(generated_files)
                # Simple summary for notice
                errors = validation_result.get("overall", {}).get("errors", 0)
                warnings = validation_result.get("overall", {}).get("warnings", 0)
                notice = f"Code generated. Validation found {errors} errors and {warnings} warnings."
                if errors > 0:
                     analysis = f"Generated code has {errors} validation errors. Review findings below."
                elif warnings > 0:
                     analysis = f"Generated code has {warnings} validation warnings. Review findings below."
                else:
                     analysis = "Generated code passed validation."


            except Exception as val_exc:
                logger.error(f"Validation step failed for generated code: {val_exc}")
                validation_result = {"error": f"Validation failed: {val_exc}"}
                notice = "Code generated, but validation process encountered an error."

            generated_files = {
                filename: re.sub(r'<<STRING_[a-f0-9]+>>', '"<redacted>"', 
                                re.sub(r'<<COMMENT_[a-f0-9]+>>', '', content))
                for filename, content in generated_files.items()
            }
            
            return {
                "result": generated_files,
                "analysis": analysis,
                "notice": notice,
                "sandbox_result": None,
                "validation_result": validation_result
            }

        # === TASK: Generate Unit Tests ===
        elif task == "generate_tests":
            logger.info("Task: Generate Unit Tests initiated.")
            if not original_project_files: # Check for original files
                 raise ValueError("Source code files are required to generate tests.")

            # Detect primary file to give hint to LLM (optional)
            target_file_hint = _detect_main_file(original_project_files, prefer_test=False)

            
            # Use original_project_files, not abstracted_project_files
            prompt = optimizer_module.buildgeneratetestsprompt(

                project_files=original_project_files,
                target_file=target_file_hint
            )
            # --- END OF FIX ---

            # --- CACHE LOGIC for Generate Tests ---
            cache_key_gen_test = None
            cached_response_gen_test = None
            can_use_cache = True # TODO: Check user plan

            if redis_client and can_use_cache:
                key_data_gen_test = f"gen_test:{provider_name}:{model or 'default'}:{prompt}"
                cache_key_gen_test = f"cache:{hashlib.sha256(key_data_gen_test.encode('utf-8')).hexdigest()}"
                try:
                    cached_response_gen_test = redis_client.get(cache_key_gen_test)
                    if cached_response_gen_test: logger.info(f"Cache HIT (Gen Test) for key {cache_key_gen_test[:15]}...")
                    else: logger.info(f"Cache MISS (Gen Test) for key {cache_key_gen_test[:15]}...")
                except Exception as e:
                    logger.error(f"Redis GET failed (Gen Test): {e}")
                    cached_response_gen_test = None

            if cached_response_gen_test:
                final_response_text = cached_response_gen_test
            else:
                final_response_text = call_provider_with_retry(
                    provider, prompt=prompt, model=model, timeout=provider_timeout
                )
                if redis_client and can_use_cache and cache_key_gen_test and final_response_text:
                    try:
                        redis_client.set(cache_key_gen_test, final_response_text, ex=3600)
                        logger.info(f"Stored (Gen Test) in cache: {cache_key_gen_test[:15]}...")
                    except Exception as e: logger.error(f"Redis SET failed (Gen Test): {e}")
            # --- END CACHE LOGIC ---

            generated_files = optimizer_module.parsemultifileresponse(final_response_text)

            if not generated_files:
                return {"result": {}, "notice": "Model did not return any generated test files.", "analysis": analysis}

            # Run the generated tests against the original (abstracted) code in the sandbox
            logger.info("Running generated tests in sandbox...")
            # We need to determine the primary code file and the primary test file
            main_code_file_path = _detect_main_file(original_project_files, prefer_test=False) # Use original files
            main_test_file_path = _detect_main_file(generated_files, prefer_test=True)

            if main_code_file_path and main_test_file_path:
                code_to_test = original_project_files.get(main_code_file_path, "") # Use original code
                test_code = generated_files.get(main_test_file_path, "")
                lang = optimizer_module.languagehintfromfilename(main_code_file_path) or validator_detect_language(code_to_test, main_code_file_path)

                # Combine original code and generated tests for the sandbox environment
                sandbox_files_combined = {**original_project_files, **generated_files} # Use original

                try:
                    # Run tests using the detected language of the CODE file
                     sandbox_result = run_tests_in_sandbox(
                         code=code_to_test,
                         tests=test_code,
                         language=lang,
                     )
                     status = sandbox_result.get("status", "unknown")
                     exit_code = sandbox_result.get("exit_code", None)
                     if status == "success":
                          notice = f"Tests generated and all {status}!"
                          analysis = "AI generated unit tests. Sandbox execution indicates tests passed against the provided code."
                     elif status in ("test_failure", "compile_error", "timeout", "sandbox_error"):
                          notice = f"Tests generated, but sandbox execution resulted in status: {status} (exit code: {exit_code}). See details below."
                          analysis = f"AI generated unit tests. Sandbox execution failed with status '{status}'. Check sandbox output for errors."
                     else:
                          notice = f"Tests generated. Sandbox status: {status}."
                          analysis = "AI generated unit tests. Review sandbox output for details."

                except Exception as sandbox_exc:
                    logger.error(f"Sandbox execution failed for generated tests: {sandbox_exc}")
                    sandbox_result = {"error": f"Sandbox failed: {sandbox_exc}"}
                    notice = "Tests generated, but sandbox execution failed."
            else:
                notice = "Tests generated, but could not determine main code/test file for sandbox execution."
                analysis = "AI generated unit tests, but automated execution was skipped."


            # Result includes the generated test files
            return {
                "result": generated_files, # Return the generated (abstracted) test files
                "analysis": analysis,
                "notice": notice,
                "sandbox_result": sandbox_result # Include sandbox test run report
            }

        # === TASK: Fix Code (Existing Logic) ===
        # Use elif to ensure it's distinct from the new tasks
        elif task in ("fix_and_secure", "code_review", "documentation", "refactor", "explain"): # Add other valid tasks here
            # --- This is mostly your existing logic for fixing errors ---
            logger.info(f"Task: {task} initiated.")
            if not error_log and task == "fix_and_secure": # Error log is essential for fixing
                 raise ValueError("Error log is required for the 'fix_and_secure' task.")

            # Determine the base prompt function based on task
            if task == "fix_and_secure":
                 prompt_builder = optimizer_module.builderrorfixprompt

            else:
                 # For other tasks like review, refactor, document, explain,
                 # use buildmultifiletaskprompt. The 'task' description itself
                 # guides the LLM. Error log is context here, not the primary focus.
                 prompt_builder = lambda files, log, task_desc, **kwargs: optimizer_module.buildmultifiletaskprompt(

                      project_files=files,
                      task=task_desc + (f"\nConsider this log output for context:\n```\n{log}\n```" if log else "")
                 )


            files_for_prompt = abstracted_project_files
            prompt_v1 = prompt_builder(files_for_prompt, error_log, task=task, token_saver_enabled=token_saver)

            # --- CACHE LOGIC (V1 - Fix/Review etc.) ---
            cache_key_v1 = None
            cached_response_text_v1 = None
            can_use_cache = True # TODO: Check user plan
            if redis_client and can_use_cache:
                key_data_v1 = f"v1:{provider_name}:{model or 'default'}:{prompt_v1}"
                cache_key_v1 = f"cache:{hashlib.sha256(key_data_v1.encode('utf-8')).hexdigest()}"
                try:
                    cached_response_text_v1 = redis_client.get(cache_key_v1)
                    if cached_response_text_v1: logger.info(f"Cache HIT (V1 Fix) key {cache_key_v1[:15]}...")
                    else: logger.info(f"Cache MISS (V1 Fix) key {cache_key_v1[:15]}...")
                except Exception as e: logger.error(f"Redis GET failed (V1 Fix): {e}"); cached_response_text_v1 = None
            # --- (Rest of V1 cache logic + CoVe logic remains the same) ---
            if cached_response_text_v1:
                response_text_v1 = cached_response_text_v1
            else:
                logger.info("Generating baseline response (V1) via LLM...")
                response_text_v1 = call_provider_with_retry(
                    provider, prompt=prompt_v1, model=model, timeout=provider_timeout
                )
                if redis_client and can_use_cache and cache_key_v1 and response_text_v1:
                    try:
                        redis_client.set(cache_key_v1, response_text_v1, ex=3600)
                        logger.info(f"Stored V1 response in cache: {cache_key_v1[:15]}...")
                    except Exception as e: logger.error(f"Redis SET failed (V1 Fix): {e}")

            match_v1 = re.search(r"<analysis>([\s\S]*?)</analysis>", response_text_v1, re.DOTALL)
            analysis_v1 = match_v1.group(1).strip() if match_v1 else f"Analysis for task '{task}'."



            # --- CHAIN-OF-VERIFICATION (CoVe) ---
            if use_cove_hardening and task == "fix_and_secure": # CoVe mainly makes sense for fixes
                 # --- (CoVe Cache logic remains the same) ---
                cove_cache_key = None
                cached_final_response_text = None
                if redis_client and can_use_cache:
                    key_data_cove = f"cove_v2:{provider_name}:{model or 'default'}:{prompt_v1}:{hashlib.sha256(analysis_v1.encode('utf-8')).hexdigest()}"
                    cove_cache_key = f"cache:{hashlib.sha256(key_data_cove.encode('utf-8')).hexdigest()}"
                    try:
                        cached_final_response_text = redis_client.get(cove_cache_key)
                        if cached_final_response_text: logger.info(f"CoVe Cache HIT key {cove_cache_key[:15]}...")
                        else: logger.info(f"CoVe Cache MISS key {cove_cache_key[:15]}...")
                    except Exception as e: logger.error(f"Redis GET failed (CoVe): {e}"); cached_final_response_text = None

                if cached_final_response_text:
                    final_response_text = cached_final_response_text
                    temp_match_final = re.search(r"<analysis>([\s\S]*?)</analysis>", final_response_text, re.DOTALL)
                    temp_analysis_final = temp_match_final.group(1).strip() if temp_match_final else ""
                    verification_analysis_marker = "--- Verification Audit ---"
                    if verification_analysis_marker in temp_analysis_final:
                        verification_analysis = temp_analysis_final.split(verification_analysis_marker, 1)[1].strip()
                    else: verification_analysis = "Analysis retrieved from cache."
                    analysis = f"--- CoVe-Verified Analysis ---\n{analysis_v1}\n\n--- Verification Audit ---\n{verification_analysis}"
                else:
                    logger.info("Engaging Chain-of-Verification (CoVe)...")

                    # --- Safety check before using optimizer's verification prompt builder ---
                    if not hasattr(optimizer_module, "buildverificationplanningprompt"):

                        logger.error(
                            "Optimizer module missing buildverificationplanningprompt. "
                            "Available symbols: %s", dir(optimizer_module)
                        )
                        raise ImportError(
                            "optimizer_module missing required function 'buildverificationplanningprompt'. "
                            "Ensure optimizer.py defines it correctly."
                        )

                    # --- Plan Verifications ---
                    verification_prompt = optimizer_module.buildverificationplanningprompt(
                    error_log or "No error log provided.",
                    files_for_prompt,
                    analysis_v1
                )

                    verification_response_text = call_provider_with_retry(
                        provider, prompt=verification_prompt, model=model, timeout=provider_timeout
                    )

                    match_v2_analysis = re.search(r"<analysis>([\s\S]*?)</analysis>", verification_response_text, re.DOTALL)
                    verification_analysis = match_v2_analysis.group(1).strip() if match_v2_analysis else "Verification failed."

                    
                    # (Generate Final Fix)
                    final_fix_prompt = optimizer_module.buildfinalverifiedfixprompt(error_log or "No error log provided.", files_for_prompt, analysis_v1, verification_analysis)

                    final_response_text = call_provider_with_retry(provider, prompt=final_fix_prompt, model=model, timeout=provider_timeout)
                    
                    if redis_client and can_use_cache and cove_cache_key and final_response_text:
                        try: 
                            redis_client.set(cove_cache_key, final_response_text, ex=3600)
                            logger.info(f"Stored CoVe response cache: {cove_cache_key[:15]}...")
                        except Exception as e: 
                            logger.error(f"Redis SET failed (CoVe): {e}")
                    
                    analysis = f"--- CoVe-Verified Analysis ---\n{analysis_v1}\n\n--- Verification Audit ---\n{verification_analysis}"

                

            # This part should be at the end, aligned with the 'if use_cove_hardening'
            if not final_response_text: # Handle case where CoVe was skipped or failed
                final_response_text = response_text_v1
                analysis = analysis_v1 # Use V1 analysis directly if no CoVe

            # --- PARSE FINAL RESPONSE (Fix/Review etc.) ---
            match_final = re.search(r"<analysis>([\s\S]*?)</analysis>", final_response_text, re.DOTALL)
            analysis = match_final.group(1).strip() if match_final else analysis # Update analysis if found in final response
            code_response = final_response_text[match_final.end():].strip() if match_final else final_response_text
            modified_files = optimizer_module.parsemultifileresponse(code_response)

            if not modified_files:
                return {"result": abstracted_project_files, "notice": f"Model did not return modifications for task '{task}'.", "analysis": analysis}

            repaired_files = modified_files.copy()

            # --- INTELLIGENT CORRECTION LOOP (Only for fix_and_secure) ---
            last_known_error = None
            if task == "fix_and_secure":
                 for attempt in range(MAX_CORRECTION_ATTEMPTS):
                    current_validation = validate_files(repaired_files)
                    error_findings = [
                        {"file": fp, **f} for fp, r in current_validation.get("files", {}).items()
                        for f in r.get("findings", []) if f.get("severity") == "error"
                    ]

                    if not error_findings: last_known_error = None; break
                    last_known_error = f"In file '{error_findings[0].get('file')}': {error_findings[0].get('message')}"

                    correction_payload = {"note": f"Attempt {attempt + 1} failed validation. Fix errors.", "errors_found": error_findings, "files_to_fix": repaired_files}
                    correction_prompt = ("Fix errors listed below. Return ONLY full, corrected files in JSON: {\"path\": \"<content>\"}.\n\n" + json.dumps(correction_payload, indent=2))
                    response_text = call_provider_with_retry(provider, prompt=correction_prompt, model=model, timeout=provider_timeout)
                    parsed_correction = optimizer_module.parsemultifileresponse(response_text)

                    if not parsed_correction: logger.warning("Correction attempt failed: no parsable code."); break
                    repaired_files = parsed_correction # Update with the latest attempt

            # --- FINAL SANDBOX (Only for fix_and_secure) & OUTPUT ---
            if last_known_error: # Only possible if task was fix_and_secure and loop failed
                logger.error(f"AI failed validation after {MAX_CORRECTION_ATTEMPTS} attempts.")
                return {"result": repaired_files, "analysis": analysis, "notice": f"AI Correction Failed. Last error: {last_known_error}", "sandbox_result": None}

            # SUCCESS PATH for Fix/Review etc.
            final_abstracted_files = {**abstracted_project_files, **repaired_files}

            if task == "fix_and_secure" and RUN_SANDBOX:
                main_file_path = _detect_main_file(final_abstracted_files, prefer_test=False)
                if main_file_path:
                    lang = optimizer_module.languagehintfromfilename(main_file_path) or validator_detect_language(final_abstracted_files[main_file_path], main_file_path)
                    try:
                         sandbox_result = run_tests_in_sandbox(
                              code=final_abstracted_files[main_file_path],
                              tests=None, # Assuming fix task doesn't involve tests here
                              language=lang,
                         )
                    except Exception as sandbox_exc:
                         logger.error(f"Sandbox execution failed during fix: {sandbox_exc}")
                         sandbox_result = {"error": f"Sandbox failed: {sandbox_exc}"}


            output_result = repaired_files if token_saver else final_abstracted_files
            
            # De-abstract before returning
            output_result = {
                filename: re.sub(r'<<STRING_[a-f0-9]+>>', '"<redacted>"', 
                                re.sub(r'<<COMMENT_[a-f0-9]+>>', '', content))
                for filename, content in output_result.items()
            }
            
            notice_message = f"Task '{task}' completed successfully."
            if task == "fix_and_secure" and sandbox_result:
                 sb_status = sandbox_result.get("status", "unknown")
                 if sb_status != "success":
                      notice_message += f" Sandbox status: {sb_status}."

            return {
                "result": output_result,
                "analysis": analysis,
                "notice": notice_message,
                "sandbox_result": sandbox_result,
            }


        else:
             # --- Handle unknown task ---
             logger.error(f"Received unknown task type: {task}")
             raise ValueError(f"Unknown task type specified: {task}")
        


    except Exception as e:
        logger.exception("An unhandled error occurred in the processing pipeline.")
        error_details = traceback.format_exc()
        notice = f"An unexpected error occurred: {type(e).__name__}: {e}"
        analysis = f"Processing failed due to a fatal error.\n\nDEBUG INFO:\n{error_details}"
        # Return abstracted files even on error for debugging context if available
        # --- FIX: Return original_project_files if abstracted_project_files is empty ---
        files_to_return = abstracted_project_files if abstracted_project_files else original_project_files
        return { "result": files_to_return, "notice": notice, "analysis": analysis }