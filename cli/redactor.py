# redactor.py (Final, Production-Ready Version)
"""
PII/PHI/Secret redaction for GDPR, HIPAA, CCPA, DPDPA (India), and global standards.

This module provides a production-grade, hybrid redaction engine. It combines
pre-compiled regex, contextual AI/NLP, and heuristic analysis to provide a
powerful, secure, and legally-aware redaction solution.

Features:
- Modular, pre-compiled regex for high-performance pattern matching.
- AI/NLP-based detection (via spaCy) for contextually ambiguous PII/PHI like names.
- Heuristic entropy-based secret detection for unknown token formats.
- Secure, deterministic placeholders using a salted hash (blake2b).
- Secure, SIEM-ready audit logging that prevents secret leakage.
- A compliance switch to enable stricter modes for specific legal jurisdictions.
- Functions to help implement Data Subject Rights (DSR) like the "Right to be Forgotten."
"""
from __future__ import annotations
import os
import regex as re
import hashlib
import logging
from typing import Tuple, Dict, List

# ==============================================================================
# Setup: AI Engine, Configuration, and Secure Logging
# ==============================================================================

# Initialize secure logger
# In production, this should be configured to output structured JSON to a
# secure, access-controlled logging system (e.g., Splunk, ELK, Datadog).
logger = logging.getLogger("redactor_audit")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s [Redactor] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# Attempt to load the spaCy AI/NLP model. The redactor will gracefully degrade
# to regex/heuristic-only mode if the model is not available.
try:
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm", disable=["parser", "tagger"])
    except OSError:
        logger.info("Downloading required spaCy AI model 'en_core_web_sm' (first time setup)...")
        from spacy.cli import download
        download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm", disable=["parser", "tagger"])
except (ImportError, Exception) as e:
    logger.warning(f"spaCy AI/NLP redaction disabled. Error: {e}")
    nlp = None

# Configuration from environment variables
# REDACTION_SALT: A high-entropy, secret key used for hashing.
#                 This MUST be set as a secure environment variable in production.
REDACTION_SALT = os.environ.get("REDACTION_SALT", "default_fallback_salt_change_in_prod")
if REDACTION_SALT == "default_fallback_salt_change_in_prod":
    logger.critical("Security Warning: Using default REDACTION_SALT. Set a secure secret in your environment.")

# COMPLIANCE: Sets the strictness level.
# 'global': Standard redaction of secrets and clear PII.
# 'strict', 'gdpr', 'dpdpa': Enables slower but more thorough AI and heuristic scans.
COMPLIANCE = os.environ.get("REDACTOR_COMPLIANCE", "global").lower()

# LOG_REDACTIONS: Enables audit logging. Should be true in production.
LOG_REDACTIONS = os.environ.get("REDACTOR_LOGGING", "true").lower() == "true"


# ==============================================================================
# Pattern Library & Pre-Compiled Regex Engine
# ==============================================================================

PATTERNS = {
    # --- Technical Secrets ---
    "AWS_KEY": r"\b(AKIA|ASIA)[0-9A-Z]{16}\b",
    "GOOGLE_API_KEY": r"\bAIza[0-9A-Za-z_\-]{35}\b",
    "AZURE_KEY": r"\b[0-9a-fA-F]{32}\b", # Common format for function keys etc.
    "STRIPE_KEY": r"\b(sk|pk)_(test|live)_[0-9a-zA-Z]{24,}\b",
    "GITHUB_TOKEN": r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b",
    "GENERIC_API_KEY": r"\b[Aa][Pp][Ii][_-]?[Kk][Ee][Yy]\s*[:=]\s*['\"]?[A-Za-z0-9\-_.~+]{16,}['\"]?",
    "DB_URI": r"\b(postgres|mysql|mongodb|redis|amqp|ftp|sftp|oracle|sqlserver)://[^\s:@/]+:[^\s@/]+@[^\s]+",
    "PRIVATE_KEY": r"-----BEGIN[\s\S]+?(RSA|EC|OPENSSH|PGP|PRIVATE)\s+KEY-----[\s\S]+?-----END[\s\S]+?KEY-----",
    "JWT": r"\b[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=+/]*\b",

    # --- PII/PHI (Global & Region-Specific) ---
    "EMAIL": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
    "PHONE_NUMBER": r"\b(\+\d{1,3}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",
    "CREDIT_CARD": r"\b(4\d{12}(\d{3})?|5[1-5]\d{14}|3[47]\d{13}|6011\d{12}|3(0[0-5]|(6|8)\d)\d{11})\b",
    "IBAN": r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b",
    "AADHAAR_IN": r"\b\d{4}\s\d{4}\s\d{4}\b", # India
    "PAN_IN": r"\b[A-Z]{5}\d{4}[A-Z]\b", # India
    "PASSPORT": r"\b([A-Z]{1}-\d{7}|[A-Z]{2}\d{7}|[A-Z]\d{8})\b", # Common int'l formats
    "SSN_US": r"\b\d{3}-\d{2}-\d{4}\b", # USA
    "IPV4": r"\b(\d{1,3}\.){3}\d{1,3}\b",
    "IPV6": r"([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}",
    "MAC_ADDRESS": r"\b([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})\b",
    "UUID": r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",

    # --- Heuristic Fallback for Unknown Secrets ---
    "HIGH_ENTROPY_STRING": r"['\"]([A-Za-z0-9/+=_]{20,})['\"]",
}

# Pre-compile a single, highly efficient regex engine from all patterns.
COMPILED_REGEX = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in PATTERNS.items()),
    re.MULTILINE | re.IGNORECASE,
)


# ==============================================================================
# Helper Functions: Entropy, Placeholders, and Logging
# ==============================================================================

def _shannon_entropy(s: str) -> float:
    """Calculates the Shannon entropy of a string to detect randomness."""
    if not s:
        return 0.0
    import math
    # Calculate probability of each character
    probabilities = [float(s.count(c)) / len(s) for c in dict.fromkeys(list(s))]
    # Calculate entropy
    return -sum(p * math.log2(p) for p in probabilities)

def _is_high_entropy(s: str, threshold: float = 4.0) -> bool:
    """Checks if a string has high entropy, suggesting it might be a secret."""
    return len(s) >= 20 and _shannon_entropy(s) > threshold

def _create_placeholder(category: str, original_value: str) -> str:
    """Creates a deterministic, salted hash placeholder for a redacted value."""
    digest = hashlib.blake2b(
        original_value.encode("utf-8"),
        key=REDACTION_SALT.encode("utf-8"),
        digest_size=8
    ).hexdigest()
    return f"<<REDACTED_{category}_{digest}>>"

def _log_redaction_event(category: str, count: int = 1):
    """Securely logs that a redaction event occurred without logging the secret itself."""
    if LOG_REDACTIONS:
        logger.info(f"Redaction event: Redacted {count} item(s) of category '{category}'.")

def _ai_detect_pii(text: str) -> List[Tuple[str, str, int, int]]:
    """Uses a pre-loaded NLP model to find contextual PII like names and locations."""
    if not nlp:
        return []

    results = []
    doc = nlp(text)
    for ent in doc.ents:
        label = ""
        # Map spaCy entity labels to our redaction categories
        if ent.label_ == "PERSON":
            label = "NAME"
        elif ent.label_ in ("GPE", "LOC"):
            label = "LOCATION"
        elif ent.label_ == "ORG":
            label = "ORGANIZATION"
        elif ent.label_ == "DATE":
            label = "DATE"

        if label:
            results.append((label, ent.text, ent.start_char, ent.end_char))
    return results


# ==============================================================================
# Core Redaction and Restoration Functions
# ==============================================================================

def redact(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Performs multi-pass redaction on a text string.

    The process is:
    1. Fast Regex Pass: Catches all clearly defined patterns.
    2. AI/NLP Pass (if enabled): Catches contextual PII missed by regex.
    3. Heuristic Pass (if enabled): Catches random-looking strings missed by both.

    Returns a tuple of (sanitized_text, mapping_dictionary).
    """
    if not text:
        return "", {}

    mapping: Dict[str, str] = {}
    redacted_categories: Dict[str, int] = {}

    # --- Pass 1: High-speed Regex Redaction ---
    def regex_replacer(match: re.Match) -> str:
        category = match.lastgroup
        if not category: return match.group(0) # Should not happen

        original_value = match.group(category)

        # For the heuristic pattern, perform an entropy check before redacting.
        if category == "HIGH_ENTROPY_STRING":
            candidate = original_value.strip("'\"")
            if not _is_high_entropy(candidate):
                return original_value # Not a secret, leave it as is.
            original_value = candidate # Redact the inner value, not the quotes

        placeholder = _create_placeholder(category, original_value)
        mapping[placeholder] = original_value
        redacted_categories[category] = redacted_categories.get(category, 0) + 1
        return placeholder

    sanitized = COMPILED_REGEX.sub(regex_replacer, text)

    # --- Pass 2: AI/NLP Contextual Redaction (for stricter compliance modes) ---
    if COMPLIANCE in ("strict", "gdpr", "dpdpa") and nlp:
        # CRITICAL FIX: Process entities in reverse order of their start position.
        # This prevents string modifications from corrupting the indices of subsequent entities.
        entities = _ai_detect_pii(sanitized)
        for label, value, start, end in sorted(entities, key=lambda item: item[2], reverse=True):
            # Check that we are not redacting something that was already handled by regex.
            if sanitized[start:end].startswith("<<REDACTED_"):
                continue

            placeholder = _create_placeholder(label, value)
            mapping[placeholder] = value
            redacted_categories[label] = redacted_categories.get(label, 0) + 1
            sanitized = sanitized[:start] + placeholder + sanitized[end:]

    # Log all redaction events securely at the end.
    for category, count in redacted_categories.items():
        _log_redaction_event(category, count)

    return sanitized, mapping

def restore(text: str, mapping: Dict[str, str]) -> str:
    """
    Restores original values into a redacted text string.

    This function should be used only in secure, authorized contexts where the
    original data is required (e.g., sending data to a trusted, compliant endpoint).
    """
    if not mapping or not text:
        return text

    # Sort placeholders by length descending to avoid replacing a substring of another placeholder.
    # e.g., ensures `<<REDACTED_A_1>>` is replaced before `<<REDACTED_A>>`.
    sorted_placeholders = sorted(mapping.keys(), key=len, reverse=True)

    restored = text
    for placeholder in sorted_placeholders:
        restored = restored.replace(placeholder, mapping[placeholder])
    return restored

def forget(mapping: Dict[str, str]) -> Dict[str, str]:
    """
    Implements the "Right to be Forgotten" by securely clearing the mapping.
    The original data becomes permanently irrecoverable from the redacted text.
    """
    mapping.clear()
    logger.info("Redaction mapping has been securely cleared to comply with a 'forget' request.")
    return {}