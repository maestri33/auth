import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from secrets import randbelow, token_hex


from auth.config import get_settings


def generate_otp() -> str:
    return f"{randbelow(1_000_000):06d}"


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


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(message: str, secret: str) -> str:
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return _b64url_encode(signature)


def create_token(external_id: str, roles: list[str], expires_delta: timedelta, token_type: str) -> str:
    settings = get_settings()
    expire = datetime.utcnow() + expires_delta
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    payload = {"sub": external_id, "roles": roles, "type": token_type, "exp": int(expire.timestamp())}
    header_part = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_part = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_part}.{payload_part}"
    return f"{signing_input}.{_sign(signing_input, settings.jwt_secret_key)}"


def create_access_token(external_id: str, roles: list[str]) -> str:
    settings = get_settings()
    return create_token(external_id, roles, timedelta(minutes=settings.access_token_minutes), "access")


def create_refresh_token(external_id: str, roles: list[str]) -> str:
    settings = get_settings()
    return create_token(external_id, roles, timedelta(days=settings.refresh_token_days), "refresh")


def decode_refresh_token(token: str) -> str:
    settings = get_settings()
    try:
        header_part, payload_part, signature = token.split(".")
        signing_input = f"{header_part}.{payload_part}"
        if not hmac.compare_digest(signature, _sign(signing_input, settings.jwt_secret_key)):
            raise ValueError("assinatura invalida")
        payload = json.loads(_b64url_decode(payload_part))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("refresh_token invalido") from exc
    if int(payload.get("exp", 0)) < int(datetime.utcnow().timestamp()):
        raise ValueError("refresh_token expirado")
    if payload.get("type") != "refresh" or not payload.get("sub"):
        raise ValueError("refresh_token invalido")
    return str(payload["sub"])
