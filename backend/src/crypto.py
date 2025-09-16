from __future__ import annotations
from cryptography.fernet import Fernet
import os, json, base64, pathlib

KEY_PATH = pathlib.Path(".vault")
KEY_FILE = KEY_PATH / "fernet.key"

def _ensure_key():
    KEY_PATH.mkdir(exist_ok=True)
    if not KEY_FILE.exists():
        KEY_FILE.write_bytes(Fernet.generate_key())

def get_fernet() -> Fernet:
    _ensure_key()
    return Fernet(KEY_FILE.read_bytes())

def encrypt_json(obj: dict) -> bytes:
    f = get_fernet()
    plain = json.dumps(obj).encode("utf-8")
    return f.encrypt(plain)

def decrypt_json(token: bytes) -> dict:
    f = get_fernet()
    plain = f.decrypt(token)
    return json.loads(plain.decode("utf-8"))
