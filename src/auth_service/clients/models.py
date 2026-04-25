from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from auth_service.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class OAuthClient(Base):
    """OAuth2 M2M client (RFC 6749 client_credentials)."""

    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    client_secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="")  # space-separated
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    @property
    def scope_list(self) -> list[str]:
        return [s for s in self.scopes.split(" ") if s]
