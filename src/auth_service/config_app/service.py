from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.config_app.models import AppConfig


async def get_value(db: AsyncSession, key: str, fallback: str) -> str:
    item = await db.get(AppConfig, key)
    return item.value if item else fallback


async def set_value(db: AsyncSession, key: str, value: str) -> None:
    item = await db.get(AppConfig, key)
    if item:
        item.value = value
    else:
        db.add(AppConfig(key=key, value=value))
