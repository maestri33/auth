from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from auth_service.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class RefreshToken(Base):
    """Whitelist de refresh tokens emitidos. Permite rotacao + revogacao."""

    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    external_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.external_id"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
