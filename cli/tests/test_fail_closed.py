"""Fail-closed redaction tests.

Contract under test: a parser failure must BLOCK the model-facing read
instead of silently serving a weaker abstraction, and fallback paths
(malformed syntax, unsupported languages) must not leak identifiers.

Run from cli/:  python -m pytest tests -q
"""
import asyncio
from pathlib import Path

import pytest

from abstractor import (
    AbstractionFailed,
    assert_no_identifier_leak,
    restore_from_mapping,
)
from engine import run_redaction
from main import restore_code

FIXTURES = Path(__file__).parent / "fixtures"

SECRET = "sk_live_51MzQ92Jk3L9s8D7f6G5h4J3k2L1"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- Parser failure blocks -------------------------------------------------

def test_malformed_python_raises_instead_of_weak_fallback():
    """Malformed Python must raise, never return weakened content."""
    with pytest.raises(AbstractionFailed):
        run_redaction({"malformed.py": read_fixture("malformed.py")})


def test_malformed_python_mcp_read_returns_block_without_content():
    """The model-facing MCP read returns a Security Block, not content."""
    import mcp_server

    text = asyncio.run(
        mcp_server.server.call_tool(
            "read_secure_file",
            {"file_path": str(FIXTURES / "malformed.py")},
        )
    ).content[0].text

    assert "Security Block" in text
    assert "NOT sent to the model" in text
    # The block message itself must not carry identifiers or secrets.
    for leaked in ("process_stripe_payment", "ProprietaryLedger", "settle", SECRET):
        assert leaked not in text
    # No mapping table may be established for a blocked file.
    key = str((FIXTURES / "malformed.py").resolve())
    assert key not in mcp_server.MAPPING_STORE


# --- Fallback paths hide everything ----------------------------------------

def test_unknown_language_fallback_hides_all_identifiers():
    """Unsupported language: fallback runs, but nothing custom survives."""
    content = read_fixture("mystery.xyz")
    data = run_redaction({"mystery.xyz": content})
    abstracted = data["abstracted_files"]["mystery.xyz"]

    for leaked in (
        "process_stripe_payment",
        "ProprietaryLedger",
        "settle",
        "ledger",
        "api_key",
        "currency",
        "amount",
        "tax",
        SECRET,
    ):
        assert leaked not in abstracted, f"identifier leaked: {leaked}"


def test_javascript_fallback_hides_identifiers_keeps_structure():
    """JS takes the regex path: identifiers hidden, keywords preserved."""
    data = run_redaction({"widget.js": read_fixture("widget.js")})
    abstracted = data["abstracted_files"]["widget.js"]

    for leaked in (
        "processStripePayment",
        "ProprietaryLedger",
        "settle",
        "ledger",
        "apiKey",
        "currency",
        "amount",
        "tax",
        "total",
        SECRET,
    ):
        assert leaked not in abstracted, f"identifier leaked: {leaked}"
    # Reserved words survive so the model still sees code structure.
    assert "function" in abstracted
    assert "return" in abstracted


def test_fallback_output_restores_exactly():
    """Fallback placeholders must round-trip back to the original file."""
    for name in ("mystery.xyz", "widget.js"):
        content = read_fixture(name)
        data = run_redaction({name: content})
        restored = restore_code(
            data["abstracted_files"][name],
            data["secret_maps"][name],
            data["abstraction_maps"][name],
        )
        assert restored == content, f"round-trip mismatch for {name}"


# --- Control: supported path still flows ------------------------------------

def test_valid_python_still_flows_with_secrets_hidden():
    """Guard against over-blocking: clean Python must still be served."""
    content = (
        'import os\n'
        f'API_TOKEN = "{SECRET}"\n'
        "def process_stripe_payment(amount):\n"
        "    return amount + 1\n"
    )
    data = run_redaction({"ok.py": content})
    abstracted = data["abstracted_files"]["ok.py"]

    assert SECRET not in abstracted
    assert "process_stripe_payment" not in abstracted
    assert "def" in abstracted  # structure preserved


# --- Leak gate unit tests ----------------------------------------------------

def test_verify_gate_catches_unmapped_identifier_in_strict_mode():
    """Strict mode (fallback paths): any unabstracted identifier blocks."""
    with pytest.raises(AbstractionFailed):
        assert_no_identifier_leak(
            original="total = amount + tax",
            abstracted="total = amount + tax",
            abstraction_map={},
            language="unknown",
            strict=True,
        )


def test_verify_gate_catches_surviving_mapped_identifier():
    """Mapped-but-visible identifiers block in every mode."""
    with pytest.raises(AbstractionFailed):
        assert_no_identifier_leak(
            original="total = amount + tax",
            abstracted="<<VAR_a>> = amount + tax",
            abstraction_map={"total": "<<VAR_a>>", "amount": "<<VAR_b>>"},
            language="unknown",
            strict=True,
        )


def test_restore_from_mapping_reverses_ident_placeholders():
    assert restore_from_mapping("<<IDENT_a>> + <<IDENT_b>>", {"x": "<<IDENT_a>>"}) == \
        "x + <<IDENT_b>>"
