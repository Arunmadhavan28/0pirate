# src/client_redactor.py
import sys
import json
from .redactor import redact
from .abstractor import abstract_single_file_text
from typing import Optional

def run_redaction(project_files: dict[str, str], allow_list: Optional[list[str]] = None) -> dict:
    """
    Takes raw project files and returns abstracted files and the necessary mapping data.
    """
    redacted_files, secret_maps = {}, {}
    abstracted_files, abstraction_maps = {}, {}
    
    # Convert list to a set for efficient lookups
    allow_set = set(allow_list) if allow_list else None

    for path, content in project_files.items():
        # Step 1: Redact secrets and PII (no change here)
        redacted_content, secret_map = redact(content)
        redacted_files[path] = redacted_content
        secret_maps[path] = secret_map

        # Step 2: Abstract the redacted code, now with the allow_list
        abstracted_content, abstraction_map = abstract_single_file_text(
            redacted_content,
            filename_hint=path,
            level="paranoid", # Default to max security
            allow_list=allow_set # <-- PASS THE SET HERE
        )
        abstracted_files[path] = abstracted_content
        abstraction_maps[path] = abstraction_map

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