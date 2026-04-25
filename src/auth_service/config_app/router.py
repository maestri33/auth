from __future__ import annotations

from fastapi import APIRouter, Depends

from auth_service.config_app import service as config_service
from auth_service.config_app.schemas import ConfigOut, ConfigUpdate
from auth_service.core.config import get_settings
from auth_service.core.deps import DbSession, require_scopes

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/", response_model=ConfigOut)
async def get_config(db: DbSession) -> ConfigOut:
    settings = get_settings()
    return ConfigOut(
        notify_base_url=await config_service.get_value(db, "notify_base_url", settings.notify_base_url),
        notify_cli=await config_service.get_value(db, "notify_cli", settings.notify_cli),
    )


@router.post(
    "/",
    response_model=ConfigOut,
    dependencies=[Depends(require_scopes("admin"))],
)
async def update_config(payload: ConfigUpdate, db: DbSession) -> ConfigOut:
    if payload.notify_base_url is not None:
        await config_service.set_value(db, "notify_base_url", payload.notify_base_url)
    if payload.notify_cli is not None:
        await config_service.set_value(db, "notify_cli", payload.notify_cli)
    await db.commit()
    return await get_config(db)
