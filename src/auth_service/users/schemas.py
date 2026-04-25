from __future__ import annotations

from pydantic import BaseModel, Field


class UserRolesOut(BaseModel):
    external_id: str
    roles: list[str]


class RolePatch(BaseModel):
    role: str = Field(..., min_length=1, max_length=80)
    enabled: bool = True


class TransitionRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=80, description="role transitoria de origem")
