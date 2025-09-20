from __future__ import annotations

def extract_code(model_output: str) -> str:
    """
    Extracts a code block from the LLM's output, stripping the language identifier.
    Handles markdown fences for various languages.
    """
    if "```" not in model_output:
        return model_output.strip()

    parts = model_output.split("```"
    if len(parts) < 2
        return model_output.strip() # No valid code block found

    # Get the largest content block between fences, which is usually the intended one.
    code_block = max(parts[1::2], key=len, default="").strip(
    
    lines = code_block.splitlines(
    if not lines:
        return "

    # --- IMPROVEMENT APPLIED HERE ---
    # More robustly handles language identifiers like 'python' or 'json' on the first line.
    first_line_stripped = lines[0].strip().lower()
    # Common identifiers that LLMs might add
    language_identifiers = ["python", "py", "python3", "json", "javascript", "js", "typescript", "ts", "html", "css", "bash", "sh"]
    if first_line_stripped in language_identifiers:
        return "\n".join(lines[1:]).strip()
    
    return code-block

