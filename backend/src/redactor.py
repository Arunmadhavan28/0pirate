from __future__ import annotations
import regex as re
from typing import Tuple, Dict

SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9]{10,}",            # generic OpenAI-like
    r"AIza[0-9A-Za-z_\-]{20,}",        # Google API-like
    r"Bearer\s+[A-Za-z0-9\-\._]{10,}", # bearer tokens
    r"(?i)password\s*=\s*['\"][^'\"]+['\"]",
    r"(?i)secret[_\-]?key\s*=\s*['\"][^'\"]+['\"]",
    r"(?i)api[_\-]?key\s*=\s*['\"][^'\"]+['\"]",
]

def redact(text: str) -> Tuple[str, Dict[str, str]]:
    mapping = {}
    idx = 1

    def repl(m):
        nonlocal idx
        val = m.group(0)
        placeholder = f"<SECRET_{idx}>"
        mapping[placeholder] = val
        idx += 1
        return placeholder

    combined = re.compile("|".join(f"({p})" for p in SECRET_PATTERNS))
    sanitized = combined.sub(repl, text)
    return sanitized, mapping

def restore(text: str, mapping: Dict[str, str]) -> str:
    for ph, real in mapping.items():
        text = text.replace(ph, real)
    return text
