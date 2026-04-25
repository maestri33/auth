from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.core.config import get_settings
from auth_service.core.docs import NOTIFY_DIR, read_markdown
from auth_service.core.exceptions import Unauthorized
from auth_service.core.security import generate_otp, hash_otp, verify_otp
from auth_service.users.models import OtpChallenge


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


async def create_otp(db: AsyncSession, external_id: str) -> str:
    settings = get_settings()
    otp = generate_otp()
    db.add(
        OtpChallenge(
            external_id=external_id,
            otp_hash=hash_otp(otp),
            expires_at=_utcnow() + timedelta(minutes=settings.otp_ttl_minutes),
        )
    )
    return otp


async def consume_otp(db: AsyncSession, external_id: str, otp: str) -> None:
    """Atômico: seleciona o desafio mais recente válido e marca consumed_at via UPDATE WHERE consumed_at IS NULL.
    Se o UPDATE não afetar nenhuma linha (race), falha como invalid."""
    now = _utcnow()
    challenge = await db.scalar(
        select(OtpChallenge)
        .where(
            OtpChallenge.external_id == external_id,
            OtpChallenge.consumed_at.is_(None),
            OtpChallenge.expires_at > now,
        )
        .order_by(OtpChallenge.created_at.desc())
    )
    if not challenge or not verify_otp(otp, challenge.otp_hash):
        raise Unauthorized("otp invalido ou expirado")
    result = await db.execute(
        update(OtpChallenge)
        .where(OtpChallenge.id == challenge.id, OtpChallenge.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    if result.rowcount == 0:
        raise Unauthorized("otp invalido ou expirado")


def build_otp_message(otp: str) -> str:
    template = read_markdown(NOTIFY_DIR, "otp.md")
    return template.replace("{{ otp }}", otp)
