from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ConfigUpdate(BaseModel):
    notify_base_url: str | None = None
    notify_cli: str | None = None


class ConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notify_base_url: str
    notify_cli: str
