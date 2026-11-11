from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import JWT_SECRET_KEY

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 30
REFRESH_TOKEN_DAYS = 7

_hasher = PasswordHash.recommended()  # argon2


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password, password_hash)
    except Exception:
        return False


def _token(user_id: int, role: str, kind: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "role": role, "type": kind, "iat": now, "exp": now + lifetime},
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def create_access_token(user_id: int, role: str) -> str:
    return _token(user_id, role, "access", timedelta(minutes=ACCESS_TOKEN_MINUTES))


def create_refresh_token(user_id: int, role: str) -> str:
    return _token(user_id, role, "refresh", timedelta(days=REFRESH_TOKEN_DAYS))


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["sub", "iat", "exp", "type", "role"]},
    )
    if payload["type"] != expected_type:
        raise jwt.InvalidTokenError(f"{expected_type} token required")
    return payload
