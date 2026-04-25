from functools import lru_cache
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "auth"
    database_url: str = "sqlite:///./auth.db"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 24 * 60
    refresh_token_days: int = 7
    otp_ttl_minutes: int = 15
    notify_base_url: str = "http://10.10.10.119:8000"
    notify_cli: str = "notify"
    notify_timeout_seconds: float = 10.0


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("AUTH_APP_NAME", "auth"),
        database_url=os.getenv("AUTH_DATABASE_URL", "sqlite:///./auth.db"),
        jwt_secret_key=os.getenv("AUTH_JWT_SECRET_KEY", "change-me-in-production"),
        jwt_algorithm=os.getenv("AUTH_JWT_ALGORITHM", "HS256"),
        access_token_minutes=int(os.getenv("AUTH_ACCESS_TOKEN_MINUTES", str(24 * 60))),
        refresh_token_days=int(os.getenv("AUTH_REFRESH_TOKEN_DAYS", "7")),
        otp_ttl_minutes=int(os.getenv("AUTH_OTP_TTL_MINUTES", "15")),
        notify_base_url=os.getenv("AUTH_NOTIFY_BASE_URL", "http://10.10.10.119:8000"),
        notify_cli=os.getenv("AUTH_NOTIFY_CLI", "notify"),
        notify_timeout_seconds=float(os.getenv("AUTH_NOTIFY_TIMEOUT_SECONDS", "10.0")),
    )
