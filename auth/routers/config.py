from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.config import get_settings
from auth.database import get_db
from auth.schemas import ConfigOut, ConfigUpdate
from auth.services import get_config_value, set_config_value

router = APIRouter(tags=["config"])


@router.get("/config/", response_model=ConfigOut)
def get_config(db: Session = Depends(get_db)) -> ConfigOut:
    settings = get_settings()
    return ConfigOut(
        notify_base_url=get_config_value(db, "notify_base_url", settings.notify_base_url),
        notify_cli=get_config_value(db, "notify_cli", settings.notify_cli),
    )


@router.post("/config/", response_model=ConfigOut)
def update_config(payload: ConfigUpdate, db: Session = Depends(get_db)) -> ConfigOut:
    if payload.notify_base_url is not None:
        set_config_value(db, "notify_base_url", payload.notify_base_url)
    if payload.notify_cli is not None:
        set_config_value(db, "notify_cli", payload.notify_cli)
    db.commit()
    return get_config(db)
