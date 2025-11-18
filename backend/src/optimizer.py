# optimizer.py
"""
Production-grade optimizer utilities for LLM-driven code transformations and
analysis. Features:
 - Multi-file prompt builder (file tree + language fences)
 - Robust parsing of multi-file LLM responses
 - Fenced-code extraction, JSON-safe parsing with fallback heuristics
 - Strict-mode retry prompts generator for malformed outputs
 - Language hints (filename-aware + content-detection) and multi-language support
 - Minimal pluggable logging/telemetry hooks
 - Utilities to normalize code and prepare patches/diffs

This module focuses on building/validating/normalizing prompts and parsing responses.
It does NOT call external providers (LLMs) directly — keep provider-specific code elsewhere.

Author: generated/produced for Data Drift Labs
Date: 2025-09-15
"""

from __future__ import annotations

import json
import logging
import re
import time
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable, Any

# Required user-specified imports
from typing import Dict  # duplicate but harmless; requested by user
from .validator import detect_language  # user-provided language detection

# Module-level logger (pluggable replacement allowed by consumer)
logger = logging.getLogger(__name__)
if not logger.handlers:
    # Basic default logging configuration if none configured by host app
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [optimizer] %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# -------------------------
# Exceptions & small types
# -------------------------
class ParseError(Exception):
    """Raised when parsing an LLM response fails irrecoverably."""


@dataclass
class RetryConfig:
    attempts: int = 3
    backoff_base: float = 0.5  # seconds
    jitter: float = 0.2
    exponential: bool = True


# -------------------------
# Internal helpers
# -------------------------
def _safe_json_loads(text: str) -> Any:
    """
    Safely parse JSON that may be embedded in surrounding text.
    Tries direct load, trims code fences, and heuristically finds JSON-like substrings.
    """
    if not text or not isinstance(text, str):
        return None

    # quick direct attempt
    try:
        return json.loads(text)
    except Exception:
        pass

    # If the JSON is inside fenced block ```json ... ```
    fenced_json = re.search(r"```(?:json)?\s*({[\s\S]*?})\s*```", text, re.IGNORECASE)
    if fenced_json:
        try:
            return json.loads(fenced_json.group(1))
        except Exception:
            pass

    # Attempt to locate top-level JSON object or array by scanning for balanced braces/brackets
    # This is a best-effort heuristic to extract the largest JSON-shaped substring
    braces_positions = []
    stack = []
    start = None
    for i, ch in enumerate(text):
        if ch in ["{", "["]:
            if start is None:
                start = i
            stack.append(ch)
        elif ch in ["}", "]"] and stack:
            stack.pop()
            if not stack and start is not None:
                snippet = text[start : i + 1]
                try:
                    return json.loads(snippet)
                except Exception:
                    start = None
                    continue

    # Fallback: try to find any {...} substring
    match = re.search(r"({[\s\S]*})", text)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # If all fails, return None for caller to handle
    return None


def extractfencedcodeblocks(text: str) -> List[Tuple[Optional[str], str]]:
    """
    Extracts fenced code blocks from text.

    Returns list of tuples: (language_hint_or_none, code_string)
    Finds both ```lang ... ``` and indented/inline triple backtick forms.
    """
    if not text:
        return []

    pattern = re.compile(r"```(?:\s*([\w+-.#]*))?\n([\s\S]*?)\n```", re.MULTILINE)
    blocks = []
    for m in pattern.finditer(text):
        lang = m.group(1).strip() if m.group(1) else None
        code = m.group(2)
        blocks.append((lang or None, code))
    return blocks


def ensurecodeformat(code: str) -> str:
    """
    Ensure code string is normalized: str type, ends with newline, and strips \r.
    This avoids tiny diffs in downstream patching.
    """
    if code is None:
        return ""
    if not isinstance(code, str):
        code = str(code)
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    if not code.endswith("\n"):
        code = code + "\n"
    return code


def languagehintfromfilename(filename: str) -> Optional[str]:
    """
    Return a language hint based on file extension, commonly used in fenced code blocks.
    Examples: 'py', 'js', 'ts', 'java', 'c', 'cpp', 'go', 'rs', 'html', 'css', 'json', 'yaml'
    """
    if not filename or "." not in filename:
        return None
    ext = filename.lower().rsplit(".", 1)[-1]
    map_ext = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "jsx": "jsx",
        "tsx": "tsx",
        "java": "java",
        "kt": "kotlin",
        "c": "c",
        "cpp": "cpp",
        "h": "c",
        "hpp": "cpp",
        "go": "go",
        "rs": "rust",
        "rb": "ruby",
        "php": "php",
        "html": "html",
        "htm": "html",
        "css": "css",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "md": "markdown",
        "sh": "bash",
        "zsh": "bash",
        "ps1": "powershell",
        "psm1": "powershell",
        "sql": "sql",
        "Dockerfile": "dockerfile",
    }
    return map_ext.get(ext, ext)


def _random_jitter(base: float, jitter: float = 0.2) -> float:
    return base + random.uniform(-jitter, jitter)


def retry_with_backoff(
    fn: Callable[..., Any], retry_cfg: Optional[RetryConfig] = None, on_retry: Optional[Callable[[int], None]] = None
) -> Callable[..., Any]:
    """
    Wrap a callable and retry on exceptions with exponential backoff.
    This is a simple decorator-style wrapper that returns a lambda which executes.
    """

    cfg = retry_cfg or RetryConfig()

    def wrapper(*args, **kwargs):
        attempt = 0
        last_exc = None
        while attempt < cfg.attempts:
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                last_exc = e
                attempt += 1
                if on_retry:
                    try:
                        on_retry(attempt)
                    except Exception:
                        pass
                backoff = cfg.backoff_base * (2 ** (attempt - 1)) if cfg.exponential else cfg.backoff_base
                # add jitter
                backoff = max(0.0, _random_jitter(backoff, cfg.jitter))
                logger.debug("Retry attempt %d failed: %s; sleeping %.2fs", attempt, str(e), backoff)
                time.sleep(backoff)
        logger.error("All %d retry attempts failed. Last error: %s", cfg.attempts, str(last_exc))
        raise last_exc

    return wrapper



def buildgeneratetestsprompt(
    project_files: Dict[str, str],
    target_file: Optional[str] = None, # Optional: Specify which file to test
    framework_hint: Optional[str] = None # Optional: e.g., 'pytest', 'jest'
) -> str:
    """
    Builds a prompt asking the LLM to generate unit tests for the provided code.
    """
    # 1. Assemble project structure tree (context)
    file_tree = "".join(f"- {path}\n" for path in sorted(project_files.keys()))

    # 2. Prepare file contents with safe code fences
    files_content = ""
    for path, content in project_files.items():
        lang = languagehintfromfilename(path) or detect_language(content) or "plaintext"
        safe_content = content.replace("```", "``\\`")
        files_content += f"---\n**File: {path}**\n```{lang}\n{safe_content}\n```\n\n"

    # 3. Specific instructions for test generation
    target_instruction = f"Focus on generating tests primarily for the file: `{target_file}`." if target_file else "Generate comprehensive tests covering the main functionalities."
    framework_instruction = f"Use the `{framework_hint}` testing framework." if framework_hint else "Use the most appropriate standard testing framework for the language (e.g., pytest for Python, Jest for JS/TS, JUnit for Java)."

    instructions = (
        "ROLE: Expert Software Engineer in Test (SDET)\n"
        "TASK: Generate high-quality unit tests for the provided code.\n\n"
        f"{target_instruction}\n"
        f"{framework_instruction}\n\n"
        "RESPONSE RULES:\n"
        "- Return ONLY the generated test code.\n"
        "- Place the test code within appropriate file blocks (e.g., `**File: test_example.py**`).\n"
        "- If multiple test files are generated, include each one.\n"
        "- Ensure tests cover edge cases, common scenarios, and potential error conditions.\n"
        "- Do NOT include explanations, analysis, or commentary outside the file blocks.\n"
        "- If the language is Python, prefer `pytest`.\n"
        "- If the language is JavaScript/TypeScript, prefer `Jest`.\n"
    )

    # 4. Assemble final structured prompt
    prompt = (
        f"{instructions}\n\n"
        f"**Project Structure:**\n{file_tree}\n"
        f"**File Contents:**\n{files_content}"
    )

    return prompt

# --- NEW: Prompt Builder for Generating Code from Prompt ---
def buildgeneratecodeprompt(
    user_prompt: str,
    context_files: Optional[Dict[str, str]] = None, # Optional: Files for context
    language_hint: Optional[str] = None
) -> str:
    """
    Builds a prompt asking the LLM to generate code based on a user's natural language prompt.
    """
    # 1. Context files (if provided)
    files_content = ""
    file_tree = ""
    if context_files:
        file_tree = "".join(f"- {path}\n" for path in sorted(context_files.keys()))
        for path, content in context_files.items():
            lang = languagehintfromfilename(path) or detect_language(content) or "plaintext"
            safe_content = content.replace("```", "``\\`")
            files_content += f"---\n**File: {path}** (Context)\n```{lang}\n{safe_content}\n```\n\n"

    # 2. Language instruction
    lang_instruction = f"Generate the code in `{language_hint}`." if language_hint else "Infer the best programming language based on the prompt, or default to Python if ambiguous."

    # 3. Core instructions
    instructions = (
        "ROLE: Expert Software Engineer\n"
        f"TASK: Generate code based on the user's request: **{user_prompt}**\n\n"
        f"{lang_instruction}\n\n"
        "RESPONSE RULES:\n"
        "- Return ONLY the generated code.\n"
        "- Place the code within appropriate file blocks (e.g., `**File: generated_code.py**`). Use descriptive filenames.\n"
        "- If multiple files are needed (e.g., HTML + JS), include each one in separate blocks.\n"
        "- Generate complete, runnable code. Include necessary imports and basic setup.\n"
        "- Add comments explaining key parts of the logic.\n"
        "- Do NOT include explanations, analysis, or commentary outside the file blocks.\n"
    )

    # 4. Assemble final structured prompt
    prompt = f"{instructions}\n\n"
    if context_files:
        prompt += f"**Context Project Structure:**\n{file_tree}\n"
        prompt += f"**Context File Contents:**\n{files_content}\n\n"
    prompt += "**User Request:**\n" + user_prompt

    return prompt


# -------------------------
# Prompt builders
# -------------------------
def buildmultifiletaskprompt(
    project_files: Dict[str, str],
    task: str,
    *,
    include_file_tree: bool = True,
    prefer_language_hints: bool = True,
    max_file_preview_chars: Optional[int] = None,
) -> str:
    """
    Builds a prompt that represents a multi-file project structure for the LLM,
    complete with a file tree and language-specific code fences.

    Args:
        project_files: mapping path -> content (full content strings).
        task: natural-language instruction for the assistant.
        include_file_tree: whether to include an explicit top-level file tree list.
        prefer_language_hints: whether to use filename-derived language hints for fences.
        max_file_preview_chars: if set, truncate files longer than this many chars (but still
            include the filename and a note).
    """
    # 1. Create a file tree representation for context
    file_tree = ""
    paths = sorted(project_files.keys())
    for path in paths:
        file_tree += f"- {path}\n"

    # 2. Concatenate all file contents with clear separators and language hints
    files_content = ""
    for path in paths:
        raw = project_files[path]
        content = raw if raw is not None else ""
        display_content = content
        truncated_note = ""
        if max_file_preview_chars and len(content) > max_file_preview_chars:
            display_content = content[:max_file_preview_chars] + "\n... (truncated)"
            truncated_note = f"\n(Note: original file truncated to {max_file_preview_chars} characters in this prompt.)"

        # Prefer language detection from provided detect_language; fallback to filename extension
        try:
            lang = None
            if prefer_language_hints:
                try:
                    # detect_language may return language code like 'python', 'javascript', etc.
                    detected = detect_language(display_content)
                    if detected:
                        lang = detected
                except Exception:
                    lang = None
            if not lang:
                lang = languagehintfromfilename(path) or ""
        except Exception:
            lang = languagehintfromfilename(path) or ""

        # sanitize triple backticks inside content by using quadruple backticks fence for the prompt
        safe_content = display_content.replace("```", "``\\`")
        files_content += f"---\n"
        files_content += f"**File: {path}**{truncated_note}\n"
        files_content += f"```{lang}\n{safe_content}\n```\n\n"

    # 3. Assemble the final, detailed prompt
    instructions = (
        "You are an expert AI software engineer. The user has provided a project and wants you to perform "
        f"the following task: **{task}**\n\n"
        "Analyze the entire project context before making any changes. Your response MUST contain ONLY the "
        "complete, corrected code for every file you modify. Use the exact same format I am providing: for each file you "
        "modify, output a file path marker followed by a fenced code block with the language hint.\n\n"
        "If you make changes, include the full contents of the entire file (not a diff). If you create a new file, include it likewise.\n\n"
        "If asked to produce tests, return test files in the same multi-file format. If asked for ephemeral commentary, place it ONLY "
        "outside the file-marked blocks and keep it short.\n\n"
        "DO NOT include any additional narrative, logs, or explanations inside the fenced code blocks.\n\n"
    )

    prompt = instructions
    if include_file_tree:
        prompt += f"**Project Structure:**\n{file_tree}\n"
    prompt += f"**File Contents:**\n{files_content}"
    return prompt


def buildstrictjsonretryprompt(original_instruction: str, last_response: str, *, error_message: Optional[str] = None) -> str:
    """
    Builds a stricter prompt to ask the model to return a JSON object with a 'files' mapping
    or 'code' key. This function is intended to be used on retry when the model's response
    could not be parsed.
    """
    instruction = (
        "You previously responded with output that could not be parsed. This time, respond ONLY in JSON. "
        "Return a single JSON object with one of the following shapes:\n\n"
        "1) { \"files\": { \"path/to/file.ext\": \"<full file contents>\", ... } }\n"
        "or\n"
        "2) { \"code\": \"<full code for a single file>\" }\n\n"
        "No additional text, no code fences, no commentary. String values must be valid JSON strings. "
        "Escape newlines properly. "
    )
    if error_message:
        instruction += f"\nError encountered when parsing your previous response:\n{error_message}\n\n"
    instruction += "\nOriginal instruction:\n" + original_instruction + "\n\n"
    instruction += "Previous response was:\n```\n" + last_response + "\n```\n\n"
    return instruction


def buildcorrectionprompt(file_path: str, code: str, error_message: Optional[str] = None, strict_json: bool = False) -> str:
    """
    Builds a corrective prompt for a single-file code correction.
    If strict_json=True the model is required to return {"code": "..."} as raw JSON.
    """
    lang = languagehintfromfilename(file_path) or detect_language(code) or "text"
    instruction = (
        "You are an expert software engineer. A failing/incorrect file was provided along with an error description. "
        "Provide the complete corrected source for the file. "
        "Return ONLY the corrected code in a fenced code block or as a JSON object depending on instructions.\n\n"
    )

    error_section = f"Error message (if any):\n```\n{error_message}\n```\n\n" if error_message else ""
    code_section = f"File: {file_path}\nLanguage hint: {lang}\n\nCode:\n```\n{code}\n```\n\n"

    if strict_json:
        return (
            "Return a JSON object with key 'code' containing the full corrected source as a string. No other text.\n\n"
            + instruction
            + error_section
            + code_section
        )
    else:
        return instruction + error_section + code_section

from typing import Dict, Optional

def builderrorfixprompt(
    project_files: Dict[str, str],
    error_log: str,
    *,
    task: Optional[str] = None,
    token_saver_enabled: bool = False
) -> str:
    """
    Builds a production-grade, standardized debugging prompt that works across
    all programming languages and multi-file projects.
    
    Features:
    - Universal language handling with safe fallbacks
    - Clear role priming for reliability
    - Structured instructions to ensure predictable, trusted outputs
    - Example-driven for consistency across runs
    """

    # 1. Assemble project structure tree
    file_tree = "".join(f"- {path}\n" for path in sorted(project_files.keys()))

    # 2. Prepare file contents with safe code fences
    files_content = ""
    for path, content in project_files.items():
        lang = languagehintfromfilename(path) or "plaintext"
        safe_content = content.replace("```", "``\\`")
        files_content += f"---\n**File: {path}**\n```{lang}\n{safe_content}\n```\n\n"

    # 3. Add optional user task
    task_instruction = (
        f"The user has also provided a specific instruction: **{task}**. "
        f"Prioritize this while fixing the error.\n"
        if task else ""
    )

    # 4. Core instructions (separated by token saver mode)
    if token_saver_enabled:
        # Compact version — strictly code only
        instructions = (
            "ROLE: Expert Principal Engineer Debugger\n"
            "Your sole task is to FIX the error shown in the terminal log.\n\n"
            f"{task_instruction}"
            "RESPONSE RULES:\n"
            "- Return ONLY the corrected code.\n"
            "- Include the FULL content of every modified file.\n"
            "- Do NOT output explanations, analysis, or commentary.\n"
            "- Do NOT invent new files or functions unless clearly required by the error.\n"
        )
    else:
        # Full version — analysis + plan + implementation
        instructions = (
            "ROLE: Expert Principal Engineer Debugger\n"
            "You are tasked with analyzing and fixing the error shown in the terminal log.\n\n"
            "RESPONSE FORMAT (strictly follow):\n"
            "1. <analysis> block\n"
            "   - Perform a clear, step-by-step reasoning (chain-of-thought style) about the root cause.\n"
            "   - Explain why the error occurred.\n"
            "   - Outline a concrete plan to fix it.\n"
            "2. Corrected Code Section\n"
            "   - Provide the COMPLETE, FIXED code for every file you modify.\n"
            "   - Preserve unmodified code in those files.\n"
            "   - Always use correct language fences (```lang).\n\n"
            f"{task_instruction}"
            "ADDITIONAL RULES:\n"
            "- Do NOT output partial snippets; include full file(s).\n"
            "- Do NOT invent files or functions unless necessary.\n"
            "- Maintain original style, formatting, and comments.\n\n"
            "--- EXAMPLE RESPONSE ---\n"
            "<analysis>\n"
            "**Root Cause**: `TypeError: unsupported operand type(s) for +: 'int' and 'str'`\n"
            "was caused by attempting to add an integer to a string.\n\n"
            "**Plan**: Convert the string to an integer before performing addition.\n"
            "</analysis>\n\n"
            "**File: utils.py**\n"
            "```python\n"
            "def get_offset_id(request):\n"
            "    user_id_str = get_user_id_from_request(request)\n"
            "    # Fix: convert string to integer\n"
            "    user_id_int = int(user_id_str)\n"
            "    return user_id_int + 100\n"
            "```\n"
            "--- END EXAMPLE ---\n\n"
            "Now, apply this exact process to the provided project."
        )

    # 5. Assemble final structured prompt
    context_block = f"**Terminal Output (Error Log):**\n```\n{error_log}\n```\n\n"
    prompt = (
        f"{instructions}\n\n"
        f"**Project Structure:**\n{file_tree}\n"
        f"{context_block}"
        f"**File Contents:**\n{files_content}"
    )

    return prompt



# -------------------------
# Parsing / Response handling
# -------------------------
def parsemultifileresponse(response_text: str) -> Dict[str, str]:
    """
    Parses the LLM's response to extract multiple code files into a dictionary.

    The function recognizes several formats:
     - Markdown style: **File: path** followed by fenced code block ```lang\ncode\n```
     - Simple fenced blocks with comments on top: e.g. "path/to/file.py\n```py\n...```"
     - JSON object with "files": {path: content}
     - JSON with single "code" (returned as {"code": "..."}), caller can map to single file if needed.

    Returns:
        mapping: file_path -> code_contents (all code normalized via ensurecodeformat)
    """
    modified_files: Dict[str, str] = {}

    if not response_text or not isinstance(response_text, str):
        return modified_files

    text = response_text.strip()

    # 1) Try JSON first (most robust)
    parsed = _safe_json_loads(text)
    if isinstance(parsed, dict):
        # prefer "files"
        if "files" in parsed and isinstance(parsed["files"], dict):
            for p, c in parsed["files"].items():
                if not isinstance(p, str):
                    continue
                modified_files[p.strip()] = ensurecodeformat(str(c))
            return modified_files
        # fallback: single code key
        if "code" in parsed and isinstance(parsed["code"], str):
            modified_files["<file>"] = ensurecodeformat(parsed["code"])
            return modified_files

    # 2) Look for the explicit pattern: **File: path**\n```lang\ncode\n```
    pattern = re.compile(r"\*\*File:\s*(.*?)\*\*\s*\n```(?:\s*([\w+-.#]*))?\n([\s\S]*?)\n```", re.MULTILINE)
    for m in pattern.finditer(text):
        path = m.group(1).strip()
        code = m.group(3)
        if path:
            modified_files[path] = ensurecodeformat(code)

    if modified_files:
        return modified_files

    # 3) Look for pattern: ---\n**File: path**\n```lang\ncode\n```
    pattern2 = re.compile(r"---\s*\n\*\*File:\s*(.*?)\*\*\s*\n```(?:\s*([\w+-.#]*))?\n([\s\S]*?)\n```", re.MULTILINE)
    for m in pattern2.finditer(text):
        path = m.group(1).strip()
        code = m.group(3)
        if path:
            modified_files[path] = ensurecodeformat(code)
    if modified_files:
        return modified_files

    # 4) If none of the above matched, extract all fenced code blocks and attempt to infer filenames
    code_blocks = extractfencedcodeblocks(text)
    # Attempt to find preceding line mentioning filename
    lines = text.splitlines()
    for idx, (lang, code) in enumerate(code_blocks):
        # Try to find the block in the original text to get the region preceding it
        escaped = "```" + (lang or "")
        # approximate: find the code snippet occurrence
        # fallback to using <file-N>
        file_hint = f"<file_{idx}>"
        # try to find path from a nearby line with common markers
        # Search for a line like "File: path", "**File: path**", or "path/to/file.py"
        # We'll use regex to find the nearest filename-like token before this block
        # Find the position of the block text in overall text
        block_pat = re.escape("```" + (lang or "")) + r"\n" + re.escape(code.strip())
        mpos = re.search(block_pat, text)
        if mpos:
            start_pos = max(0, mpos.start() - 200)  # look 200 chars back
            context = text[start_pos : mpos.start()]
            # search for File: pattern
            fm = re.search(r"(?:\*\*File:\s*|File:\s*)([^\n*`]+)", context, re.IGNORECASE)
            if fm:
                file_hint = fm.group(1).strip().strip("*").strip()
            else:
                # find a bare filename-like token
                fm2 = re.search(r"([A-Za-z0-9_\-./\\]+?\.(?:py|js|ts|java|go|rs|cpp|c|html|css|json|yaml|yml|md))", context)
                if fm2:
                    file_hint = fm2.group(1).strip()
        modified_files[file_hint] = ensurecodeformat(code)

    if modified_files:
        return modified_files

    # 5) As a last resort, if the whole response looks like code (no fences), treat it as single file
    # Heuristic: if text contains 'def ' or 'class ' or '{' or 'import ' pick it as code
    code_like = False
    if any(keyword in text for keyword in ["def ", "class ", "import ", "{", ";", "function ", "package ", "pub "]):
        code_like = True

    if code_like:
        modified_files["<file>"] = ensurecodeformat(text)
        return modified_files

    # If nothing matched, raise or return empty dict
    return modified_files


# -------------------------
# Utility: format output into multi-file string
# -------------------------
def format_files_as_multifile_response(files: Dict[str, str], *, language_hints: bool = True) -> str:
    """
    Format a mapping of files -> contents into the multi-file output format that the
    LLM expects/uses: markers and fenced code blocks.

    Example:
        **File: path/to/file.py**
        ```python
        <contents>
        ```
    """
    out = []
    for path in sorted(files.keys()):
        content = ensurecodeformat(files[path])
        lang = None
        if language_hints:
            lang = languagehintfromfilename(path) or detect_language(content) or ""
        # protect against triple backtick in content
        safe_content = content.replace("```", "``\\`")
        out.append(f"**File: {path}**\n```{lang}\n{safe_content}\n```")
    return "\n\n".join(out)


# -------------------------
# Small high-level flows (no provider calls)
# -------------------------
def attemptparsewithretries(
    response_text: str,
    *,
    retry_cfg: Optional[RetryConfig] = None,
    original_instruction: Optional[str] = None,
) -> Dict[str, str]:
    """
    Try to parse an LLM response to multi-file mapping robustly.
    If the output cannot be parsed, produce a 'strict JSON' retry prompt (caller may send to model).
    Returns the parsed file mapping if successful; otherwise returns empty dict.
    """
    retry_cfg = retry_cfg or RetryConfig()
    parsed = parsemultifileresponse(response_text)
    if parsed:
        return parsed

    # At this point we failed to parse. Caller should invoke a retry against the model using the prompt below.
    error_message = "Could not parse the model's response into files or code blocks."
    strict_prompt = build_strict_json_retry_prompt(original_instruction or "Task: unknown", response_text, error_message=error_message)
    # Do NOT call model here. We return the strict prompt as guidance for caller to use on retry.
    logger.debug("Parsing failed. Generated strict retry prompt for caller.")
    return {"_strict_prompt": strict_prompt}

#Chain-of-Verification" (CoVe) layer

def buildverificationplanningprompt(
    original_error_log: str,
    original_files: Dict[str, str],
    first_pass_analysis: str
) -> str:
    """
    Builds a prompt for the CoVe "Planning" step.
    Asks the LLM to critique its own first-pass analysis and plan verification steps.
    """
    
    # 1. Assemble project structure tree
    file_tree = "".join(f"- {path}\n" for path in sorted(original_files.keys()))

    # 2. Prepare file contents
    files_content = ""
    for path, content in original_files.items():
        lang = languagehintfromfilename(path) or "plaintext"
        safe_content = content.replace("```", "``\\`")
        files_content += f"---\n**File: {path}**\n```{lang}\n{safe_content}\n```\n\n"

    # 3. Assemble the prompt
    instructions = (
        "ROLE: Expert Principal Engineer (Verification & Audit)\n"
        "TASK: You are auditing a solution proposed by a junior engineer. Your *only* job is to analyze their solution and list potential flaws or verification steps. You must NOT generate a new code fix.\n\n"
        "RESPONSE FORMAT (strictly follow):\n"
        "1. <analysis> block\n"
        "   - Review the 'Original Problem' and the 'Proposed Solution Analysis'.\n"
        "   - Critically evaluate the solution. Does it *fully* solve the error? Does it introduce new bugs? Is the reasoning sound?\n"
        "   - List 3-5 specific verification questions to check if the solution is correct.\n"
        "2. Do NOT include any code blocks.\n\n"
        "--- EXAMPLE RESPONSE ---\n"
        "<analysis>\n"
        "The proposed solution correctly identifies the `TypeError`, but the plan to cast to `int` might fail if the variable is `None`.\n\n"
        "Verification Questions:\n"
        "1. Does the proposed solution handle cases where `<<VAR_a1b2c3>>` is `None` or an empty string?\n"
        "2. Does the fix correctly import any new libraries it uses?\n"
        "3. Does the fix address the *root cause* of the `TypeError` or just the symptom?\n"
        "</analysis>\n"
        "--- END EXAMPLE ---"
    )

    prompt = (
        f"{instructions}\n\n"
        f"**Original Problem:**\n```\n{original_error_log}\n```\n\n"
        f"**Project Structure:**\n{file_tree}\n"
        f"**File Contents:**\n{files_content}\n\n"
        f"**Proposed Solution Analysis (from Junior Engineer):**\n<analysis>\n{first_pass_analysis}\n</analysis>"
    )
    return prompt


def buildfinalverifiedfixprompt(
    original_error_log: str,
    original_files: Dict[str, str],
    first_pass_analysis: str,
    verification_analysis: str
) -> str:
    """
    Builds a prompt for the CoVe "Final Fix" step.
    Gives the LLM all context: problem, V1 fix analysis, and V2 critique.
    """
    
    # 1. Assemble project structure tree
    file_tree = "".join(f"- {path}\n" for path in sorted(original_files.keys()))

    # 2. Prepare file contents
    files_content = ""
    for path, content in original_files.items():
        lang = languagehintfromfilename(path) or "plaintext"
        safe_content = content.replace("```", "``\\`")
        files_content += f"---\n**File: {path}**\n```{lang}\n{safe_content}\n```\n\n"

    # 3. Assemble the prompt
    instructions = (
        "ROLE: Expert Principal Engineer (Final Implementation)\n"
        "TASK: You have received a junior engineer's solution and a senior engineer's critique. Your job is to synthesize all this information into a final, production-ready fix.\n\n"
        "CONTEXT:\n"
        "1. **Original Problem:** A user's code is failing with an error.\n"
        "2. **First Analysis (V1):** Your first attempt at analyzing the problem.\n"
        "3. **Verification Analysis (V2):** Your critical review of your own V1 analysis, which identifies potential flaws.\n\n"
        "RESPONSE FORMAT (strictly follow):\n"
        "1. <analysis> block\n"
        "   - Briefly explain the final, correct fix.\n"
        "   - Explicitly state how this final fix addresses the flaws identified in the 'Verification Analysis (V2)'.\n"
        "2. Corrected Code Section\n"
        "   - Provide the COMPLETE, FINAL, and FIXED code for every file you modify.\n"
        "   - This is your last chance. Ensure the code is correct.\n"
    )
    
    prompt = (
        f"{instructions}\n\n"
        f"**Original Problem:**\n```\n{original_error_log}\n```\n\n"
        f"**Project Structure:**\n{file_tree}\n"
        f"**File Contents:**\n{files_content}\n\n"
        "--- ANALYSIS V1 (Your first attempt) ---\n"
        f"<analysis>\n{first_pass_analysis}\n</analysis>\n\n"
        "--- VERIFICATION ANALYSIS V2 (Your critique of V1) ---\n"
        f"<analysis>\n{verification_analysis}\n</analysis>\n\n"
        "--- FINAL IMPLEMENTATION ---\n"
        "Now, generate the final, verified <analysis> and code blocks."
    )
    return prompt


# -------------------------
# Exported helpers / API
# -------------------------
__all__ = [
    "build_multi_file_task_prompt",
    "parsemultifileresponse",
    "format_files_as_multifile_response",
    "attemptparsewithretries",
    "ensurecodeformat",
    "extractfencedcodeblocks",
    "languagehintfromfilename",
    "build_correction_prompt",
    "build_strict_json_retry_prompt",
    "build_error_fix_prompt", 
    "retry_with_backoff",
    "RetryConfig",
    "build_generate_tests_prompt",
    "build_generate_code_prompt",
    "build_verification_planning_prompt",
    "build_final_verified_fix_prompt"
]



