from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from auth_service.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class AuditEvent(Base):
    """Eventos sensiveis para auditoria. Imutavel apos persistido."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)  # user | client | system
    actor_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
