from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClientCreate(BaseModel):
    client_id: str = Field(..., min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.\-]+$")
    name: str = Field(..., min_length=1, max_length=160)
    scopes: list[str] = Field(default_factory=list)


class ClientCreateOut(BaseModel):
    client_id: str
    client_secret: str  # plaintext, mostrado uma unica vez
    name: str
    scopes: list[str]


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: str
    name: str
    scopes: list[str]
    is_active: bool


class ClientListOut(BaseModel):
    clients: list[ClientOut]


class TokenRequest(BaseModel):
    grant_type: str = Field(..., pattern=r"^client_credentials$")
    client_id: str
    client_secret: str
    scope: str | None = None  # space-separated; subset dos escopos do client


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str
