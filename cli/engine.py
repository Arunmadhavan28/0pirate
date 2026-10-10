# src/client_redactor.py
import re
import sys
import json
from redactor import redact
from abstractor import (
    AbstractionFailed,
    abstract_single_file_text,
    assert_no_identifier_leak,
    detect_language,
)
from typing import Optional


def _ast_safe(content: str) -> tuple[str, dict[str, str]]:
    """Replace <<PLACEHOLDER>> with valid Python identifiers so AST parsing survives redaction.

    Returns (safe_content, reverse_map) where reverse_map maps temp -> original.
    """
    reverse: dict[str, str] = {}

    def _repl(m: re.Match) -> str:
        original = m.group(0)  # e.g. <<REDACTED_X_abc123>>
        inner = m.group(1)
        # Sanitize to [A-Za-z0-9_], keep it a valid identifier
        safe_inner = re.sub(r"[^A-Za-z0-9_]", "_", inner)
        temp = f"__PIRATE_{safe_inner}__"
        reverse[temp] = original
        return temp

    safe = re.sub(r"<<([^<>]+)>>", _repl, content)
    return safe, reverse


def run_redaction(project_files: dict[str, str], allow_list: Optional[list[str]] = None) -> dict:
    """
    Takes raw project files and returns abstracted files and the necessary mapping data.

    Fail-closed contract: raises AbstractionFailed if any file cannot be
    proven safe (parse failure, or identifiers/secrets surviving in the
    output). Callers MUST block the model-facing read on this exception,
    never send the content, weakened or otherwise.
    """
    redacted_files, secret_maps = {}, {}
    abstracted_files, abstraction_maps = {}, {}

    for path, content in project_files.items():
        # Step 1: Redact secrets and PII (no change here)
        redacted_content, secret_map = redact(content)
        redacted_files[path] = redacted_content
        secret_maps[path] = secret_map

        # Step 1b: Make redacted output AST-safe, and protect secret
        # placeholders from being re-abstracted.
        safe_content, reverse = _ast_safe(redacted_content)
        merged_allow = set(allow_list) if allow_list else set()
        merged_allow.update(reverse.keys())  # don't abstract secret placeholders
        merged_allow.update(secret_map.keys())  # belt-and-braces (<<..>> form)

        # Step 2: Abstract the redacted code, now with the allow_list.
        # May raise AbstractionFailed on parse failure: intentional, the
        # caller must block instead of serving a weaker abstraction.
        lang = detect_language(safe_content, filename_hint=path)
        abstracted_safe, abstraction_map = abstract_single_file_text(
            safe_content,
            filename_hint=path,
            level="paranoid", # Default to max security
            allow_list=merged_allow
        )
        # Step 2b: Restore <<..>> placeholder form in output + mapping keys/values
        abstracted_content = abstracted_safe
        fixed_map: dict[str, str] = {}
        for orig, ph in abstraction_map.items():
            fixed_orig = orig
            fixed_ph = ph
            for temp, back in reverse.items():
                if temp in fixed_orig:
                    fixed_orig = fixed_orig.replace(temp, back)
                if temp in fixed_ph:
                    fixed_ph = fixed_ph.replace(temp, back)
            fixed_map[fixed_orig] = fixed_ph
        for temp, back in reverse.items():
            abstracted_content = abstracted_content.replace(temp, back)

        # Step 3: Verify before release. Strict for every language the AST
        # does not cover (fallback paths must hide 100% of identifiers);
        # mapping-level for Python (which intentionally preserves imports).
        # Any failure raises AbstractionFailed -> read is blocked.
        assert_no_identifier_leak(
            safe_content,
            abstracted_content,
            fixed_map,
            language=lang,
            allow_list=merged_allow,
            strict=(lang != "python"),
        )
        for secret_value in secret_map.values():
            if len(secret_value) >= 8 and secret_value in abstracted_content:
                raise AbstractionFailed(
                    "a redacted secret value survived into the output, blocking read"
                )

        abstracted_files[path] = abstracted_content
        abstraction_maps[path] = fixed_map

    return {
        "abstracted_files": abstracted_files,
        "secret_maps": secret_maps,
        "abstraction_maps": abstraction_maps
    }

if __name__ == "__main__":
    # This allows the script to be called from the command line,
    # reading from stdin and writing to stdout.
    try:
        input_data = json.load(sys.stdin)
        project_files = input_data.get("project_files")

        if not project_files:
            raise ValueError("Input JSON must contain a 'project_files' dictionary.")

        output_data = run_redaction(project_files)

        print(json.dumps(output_data))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)