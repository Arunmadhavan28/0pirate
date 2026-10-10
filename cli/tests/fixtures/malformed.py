"""Fixture: malformed Python. ast.parse MUST fail on this file.

Fail-closed contract: this content must NEVER reach a model, not even in
weakened (regex-fallback) form. run_redaction must raise AbstractionFailed
and the MCP read path must return a Security Block instead of content.
"""
import os

STRIPE_LIVE_KEY = "sk_live_51MzQ92Jk3L9s8D7f6G5h4J3k2L1"

def process_stripe_payment(amount, currency
    ledger = ProprietaryLedger()
    tax = 100 / amount
    return ledger.settle(amount + tax, currency
