from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from secrets import randbelow, token_hex, token_urlsafe
from typing import Any

import jwt
from jwt import InvalidTokenError

from auth_service.core.config import get_settings


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------
def generate_otp(length: int | None = None) -> str:
    n = length or get_settings().otp_length
    upper = 10**n
    return f"{randbelow(upper):0{n}d}"


def hash_otp(otp: str) -> str:
    salt = token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", otp.encode(), salt.encode(), 120_000).hex()
    return f"{salt}:{digest}"


def verify_otp(otp: str, otp_hash: str) -> bool:
    try:
        salt, expected = otp_hash.split(":", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", otp.encode(), salt.encode(), 120_000).hex()
    return hmac.compare_digest(digest, expected)


# ---------------------------------------------------------------------------
# JWT (PyJWT)
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _encode(payload: dict[str, Any]) -> str:
    settings = get_settings()
    secret = settings.resolve_jwt_secret()
    return jwt.encode(
        payload,
        secret,
        algorithm=settings.jwt_algorithm,
        headers={"kid": settings.jwt_key_id},
    )


def _decode(token: str) -> dict[str, Any]:
    settings = get_settings()
    secret = settings.resolve_jwt_secret()
    return jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])


def create_access_token(external_id: str, roles: list[str]) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "iss": settings.app_name,
        "sub": external_id,
        "roles": roles,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
    }
    return _encode(payload)


def create_refresh_token(external_id: str, roles: list[str]) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "iss": settings.app_name,
        "sub": external_id,
        "roles": roles,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.refresh_token_days)).timestamp()),
    }
    return _encode(payload)


def create_client_token(client_id: str, scopes: list[str], ttl_minutes: int = 60) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "iss": settings.app_name,
        "sub": client_id,
        "scopes": scopes,
        "type": "client",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    return _encode(payload)


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = _decode(token)
    except InvalidTokenError as exc:
        raise ValueError(f"token invalido: {exc}") from exc
    if payload.get("type") != expected_type:
        raise ValueError(f"token type invalido (esperado {expected_type})")
    if not payload.get("sub"):
        raise ValueError("token sem sub")
    return payload


# ---------------------------------------------------------------------------
# Client secret hashing
# ---------------------------------------------------------------------------
def generate_client_secret() -> str:
    return token_urlsafe(32)


def hash_client_secret(secret: str) -> str:
    salt = token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), 200_000).hex()
    return f"{salt}:{digest}"


def verify_client_secret(secret: str, hashed: str) -> bool:
    try:
        salt, expected = hashed.split(":", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), 200_000).hex()
    return hmac.compare_digest(digest, expected)
