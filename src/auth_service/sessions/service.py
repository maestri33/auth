"""Whitelist de refresh tokens com rotacao e reuse-detection.

Modelo: cada refresh emitido tem um `jti` (UUID) persistido em refresh_tokens.
Decodar um refresh exige (a) assinatura valida, (b) jti em DB, (c) nao revogado, (d) nao expirado.

Reuse-detection: se um refresh ja revogado for apresentado, todas as sessoes do
usuario sao revogadas (cadeia comprometida).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.core.config import get_settings
from auth_service.sessions.models import RefreshToken


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


async def issue(
    db: AsyncSession,
    external_id: str,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
) -> str:
    """Cria um jti, persiste a sessao, retorna o jti."""
    settings = get_settings()
    jti = str(uuid4())
    db.add(
        RefreshToken(
            jti=jti,
            external_id=external_id,
            expires_at=_utcnow() + timedelta(days=settings.refresh_token_days),
            user_agent=(user_agent or None),
            ip=ip,
        )
    )
    await db.flush()
    return jti


async def get(db: AsyncSession, jti: str) -> RefreshToken | None:
    return await db.get(RefreshToken, jti)


async def revoke(db: AsyncSession, jti: str, reason: str = "manual") -> bool:
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.jti == jti, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_utcnow(), revoked_reason=reason)
    )
    return (result.rowcount or 0) > 0


async def revoke_user_sessions(db: AsyncSession, external_id: str, reason: str) -> int:
    """Revoga todas as sessoes ativas de um usuario. Retorna quantas foram revogadas."""
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.external_id == external_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_utcnow(), revoked_reason=reason)
    )
    return result.rowcount or 0


async def list_for_user(
    db: AsyncSession, external_id: str, *, include_revoked: bool = False
) -> list[RefreshToken]:
    stmt = select(RefreshToken).where(RefreshToken.external_id == external_id)
    if not include_revoked:
        stmt = stmt.where(RefreshToken.revoked_at.is_(None))
    stmt = stmt.order_by(RefreshToken.created_at.desc())
    return list((await db.scalars(stmt)).all())


async def purge_expired_or_revoked(db: AsyncSession) -> int:
    now = _utcnow()
    result = await db.execute(
        delete(RefreshToken).where(
            (RefreshToken.expires_at < now) | (RefreshToken.revoked_at.is_not(None))
        )
    )
    return result.rowcount or 0
