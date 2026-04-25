from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    is_staff: bool = False
    is_transitory: bool = False
    transitions_to: str | None = None
    requires_role: str | None = None
    incompatible_roles: list[str] = Field(default_factory=list)
    description: str | None = None


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    is_staff: bool
    is_transitory: bool
    transitions_to: str | None = None
    requires_role: str | None = None
    incompatible_roles: list[str] = Field(default_factory=list)
    description: str | None = None


class RoleListOut(BaseModel):
    roles: list[RoleOut]
