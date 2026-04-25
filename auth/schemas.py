from pydantic import BaseModel, Field


class ConfigUpdate(BaseModel):
    notify_base_url: str | None = None
    notify_cli: str | None = None


class ConfigOut(BaseModel):
    notify_base_url: str
    notify_cli: str


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


class DiscoveryResponse(BaseModel):
    service: str
    version: str
    jwt_algorithm: str
    jwt_token_format: str
    available_roles: list[dict]
    endpoints: dict[str, str]


class LoginRequest(BaseModel):
    external_id: str
    otp: str = Field(..., min_length=6, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    external_id: str
    roles: list[str]


class RefreshRequest(BaseModel):
    refresh_token: str


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    is_staff: bool = False
    is_transitory: bool = False
    transitions_to: str | None = None
    requires_role: str | None = None
    incompatible_roles: list[str] = Field(default_factory=list)
    description: str | None = None


class RoleOut(RoleCreate):
    pass


class UserRolesOut(BaseModel):
    external_id: str
    roles: list[str]


class RolePatch(BaseModel):
    role: str
    enabled: bool = True


class TransitionRequest(BaseModel):
    role: str  # role transitoria de origem (ex: "lead", "candidato")
