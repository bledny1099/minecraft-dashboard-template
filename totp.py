"""RFC 6238 TOTP (Time-based One-Time Password) implementation in pure Python stdlib.
Compatible with Google Authenticator, 1Password, Authy, Apple Passwords, etc.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
import urllib.parse


def generate_secret() -> str:
    """Generates a random 32-character Base32 secret (160 bits of entropy)."""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("ascii").replace("=", "")


def get_totp_code(secret: str, time_step: int = 30, for_time: float | None = None) -> str:
    """Calculates the current 6-digit TOTP code for a given Base32 secret."""
    secret_clean = secret.strip().replace(" ", "").upper()
    pad_len = (8 - len(secret_clean) % 8) % 8
    key = base64.b32decode(secret_clean + ("=" * pad_len))
    t = int((time.time() if for_time is None else for_time) // time_step)
    counter = struct.pack(">Q", t)
    h = hmac.new(key, counter, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code_int = (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code_int:06d}"


def verify_totp(secret: str, code: str, window: int = 1, time_step: int = 30) -> bool:
    """Verifies a 6-digit TOTP code allowing +/- window time steps for clock drift."""
    if not secret or not code:
        return False
    code_str = "".join(ch for ch in str(code).strip() if ch.isdigit())
    if len(code_str) != 6:
        return False
    now = time.time()
    for offset in range(-window, window + 1):
        expected = get_totp_code(secret, time_step, now + offset * time_step)
        if hmac.compare_digest(expected, code_str):
            return True
    return False


def get_totp_uri(username: str, secret: str, issuer: str = "Minecraft Dashboard") -> str:
    """Builds the standard otpauth:// URL for authenticator apps."""
    label = f"{issuer}:{username}"
    params = {
        "secret": secret.strip().replace(" ", "").upper(),
        "issuer": issuer,
        "algorithm": "SHA1",
        "digits": 6,
        "period": 30,
    }
    return f"otpauth://totp/{urllib.parse.quote(label)}?{urllib.parse.urlencode(params)}"
