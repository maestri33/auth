from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    actor_type: str
    actor_id: str | None
    action: str
    target_type: str | None
    target_id: str | None
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_json")
    request_id: str | None
    ip: str | None

    @field_validator("metadata", mode="before")
    @classmethod
    def _parse_meta(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                return {"raw": v}
        return v


class AuditListOut(BaseModel):
    events: list[AuditEventOut]
    limit: int
    offset: int
