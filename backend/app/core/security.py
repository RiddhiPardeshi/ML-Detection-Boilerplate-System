import base64
import hashlib
import hmac
import os
import secrets
import time
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()
SECRET_KEY = os.getenv("SECRET_KEY", "generic-ml-secret-key-2026-production-platform")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_session_token(user_id: int) -> str:
    """Generate a secure, signed session token for a user ID."""
    timestamp = int(time.time())
    nonce = secrets.token_hex(8)
    payload = f"{user_id}:{timestamp}:{nonce}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token_data = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(token_data.encode()).decode()


def decode_session_token(token: str) -> int | None:
    """Decode and verify a signed session token. Returns user_id if valid."""
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        parts = raw.split(":")
        if len(parts) != 4:
            return None
        user_id_str, timestamp_str, nonce, sig = parts
        payload = f"{user_id_str}:{timestamp_str}:{nonce}"
        expected_sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        # 7 days expiration
        if int(time.time()) - int(timestamp_str) > 7 * 86400:
            return None
        return int(user_id_str)
    except Exception:
        return None
