from __future__ import annotations
import pathlib, json
from .crypto import encrypt_json, decrypt_json

VAULT_PATH = pathlib.Path(".vault")
SECRETS_FILE = VAULT_PATH / "secrets.bin"

def save_mapping(mapping: dict):
    VAULT_PATH.mkdir(exist_ok=True)
    SECRETS_FILE.write_bytes(encrypt_json(mapping))

def load_mapping() -> dict:
    if not SECRETS_FILE.exists():
        return {}
    return decrypt_json(SECRETS_FILE.read_bytes())
