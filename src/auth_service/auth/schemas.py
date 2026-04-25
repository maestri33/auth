from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    phone: str = Field(..., min_length=8, max_length=32)
    role: str = Field(..., min_length=1, max_length=80)


class RegisterResponse(BaseModel):
    status: str
    message: str
    external_id: str
    role: str


class OtpRequest(BaseModel):
    external_id: str | None = None
    phone: str | None = None


class OtpResponse(BaseModel):
    status: str
    message: str
    external_id: str


class CheckRequest(BaseModel):
    phone: str = Field(..., min_length=8, max_length=32)


class CheckResponse(BaseModel):
    found_in_notify: bool
    found_locally: bool
    notify_external_id: str | None = None
    local_external_id: str | None = None
    whatsapp_valid: bool | None = None


class LoginRequest(BaseModel):
    external_id: str
    otp: str = Field(..., min_length=4, max_length=10)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    external_id: str
    roles: list[str]


class RefreshRequest(BaseModel):
    refresh_token: str


class DiscoveryResponse(BaseModel):
    service: str
    version: str
    jwt_algorithm: str
    jwt_token_format: str
    available_roles: list[dict]
    endpoints: dict[str, str]
