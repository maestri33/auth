from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    env: Literal["dev", "prod", "test"] = "dev"
    app_name: str = "auth"
    database_url: str = "sqlite+aiosqlite:///./auth.db"

    jwt_secret: str = ""
    jwt_secret_file: str = ""
    state_dir: str = "./.state"
    jwt_algorithm: str = "HS256"
    jwt_key_id: str = "v1"
    access_token_minutes: int = 60
    refresh_token_days: int = 7

    otp_ttl_minutes: int = 15
    otp_length: int = Field(default=6, ge=4, le=10)

    notify_base_url: str = "http://10.10.10.119:8000"
    notify_cli: str = "notify"
    notify_timeout_seconds: float = 10.0

    ratelimit_otp: str = "5/minute"
    ratelimit_login: str = "10/minute"
    ratelimit_oauth: str = "30/minute"

    def resolve_jwt_secret(self) -> str:
        if self.jwt_secret and self.jwt_secret != _DEFAULT_SECRET:
            return self.jwt_secret
        if self.jwt_secret_file:
            path = Path(self.jwt_secret_file)
            if path.exists():
                return path.read_text(encoding="utf-8").strip()
        state = Path(self.state_dir)
        state.mkdir(parents=True, exist_ok=True)
        secret_file = state / "jwt_secret"
        if secret_file.exists():
            return secret_file.read_text(encoding="utf-8").strip()
        if self.env == "prod":
            raise RuntimeError(
                "AUTH_JWT_SECRET ausente em prod. Defina AUTH_JWT_SECRET, AUTH_JWT_SECRET_FILE, "
                f"ou pre-popule {self.state_dir}/jwt_secret."
            )
        generated = secrets.token_urlsafe(64)
        secret_file.write_text(generated + "\n", encoding="utf-8")
        secret_file.chmod(0o600)
        return generated


@lru_cache
def get_settings() -> Settings:
    return Settings()
