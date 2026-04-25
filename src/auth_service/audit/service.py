"""Servico de audit log — persiste eventos sensiveis no DB."""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.audit.models import AuditEvent
from auth_service.core.logging import request_id_ctx

_log = logging.getLogger("auth.audit")


async def record(
    db: AsyncSession,
    *,
    action: str,
    actor_type: str = "system",
    actor_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Persiste um evento de auditoria. Falhas sao logadas mas nao quebram o fluxo."""
    try:
        db.add(
            AuditEvent(
                action=action,
                actor_type=actor_type,
                actor_id=actor_id,
                target_type=target_type,
                target_id=target_id,
                metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
                request_id=request_id_ctx.get(),
                ip=ip,
            )
        )
        await db.flush()
    except Exception:
        _log.exception("audit.record failed", extra={"action": action, "actor_id": actor_id})


async def query(
    db: AsyncSession,
    *,
    actor_id: str | None = None,
    action: str | None = None,
    target_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditEvent]:
    stmt = select(AuditEvent).order_by(AuditEvent.ts.desc())
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if target_id:
        stmt = stmt.where(AuditEvent.target_id == target_id)
    stmt = stmt.limit(limit).offset(offset)
    return list((await db.scalars(stmt)).all())


async def purge_older_than(db: AsyncSession, days: int) -> int:
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)
    result = await db.execute(delete(AuditEvent).where(AuditEvent.ts < cutoff))
    return result.rowcount or 0
