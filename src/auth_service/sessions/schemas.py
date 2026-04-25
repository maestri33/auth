from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    jti: str
    external_id: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    revoked_reason: str | None
    user_agent: str | None
    ip: str | None


class SessionListOut(BaseModel):
    sessions: list[SessionOut]


class RevokeRequest(BaseModel):
    reason: str = "manual"
