from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response, status

from auth_service.clients import service as clients_service
from auth_service.clients.schemas import (
    ClientCreate,
    ClientCreateOut,
    ClientListOut,
    TokenRequest,
    TokenResponse,
)
from auth_service.core.config import get_settings
from auth_service.core.deps import DbSession, require_scopes
from auth_service.core.rate_limit import limiter
from auth_service.core.security import create_client_token

_settings = get_settings()
_log = logging.getLogger("auth.oauth")
router = APIRouter(tags=["oauth"])


@router.post(
    "/oauth/token",
    response_model=TokenResponse,
    responses={401: {"description": "client invalido"}},
)
@limiter.limit(_settings.ratelimit_oauth)
async def issue_token(
    request: Request, response: Response, payload: TokenRequest, db: DbSession
) -> TokenResponse:
    client, granted = await clients_service.authenticate_client(
        db, payload.client_id, payload.client_secret, payload.scope
    )
    ttl_minutes = 60
    token = create_client_token(client.client_id, granted, ttl_minutes=ttl_minutes)
    _log.info("oauth.token_issued", extra={"client_id": client.client_id, "scopes": granted})
    return TokenResponse(
        access_token=token,
        expires_in=ttl_minutes * 60,
        scope=" ".join(granted),
    )


@router.get(
    "/oauth/clients/",
    response_model=ClientListOut,
    dependencies=[Depends(require_scopes("admin"))],
)
async def list_clients(db: DbSession) -> ClientListOut:
    return ClientListOut(clients=await clients_service.list_clients(db))


@router.post(
    "/oauth/clients/",
    response_model=ClientCreateOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scopes("admin"))],
    responses={409: {"description": "client_id ja existe"}},
)
async def create_client(payload: ClientCreate, db: DbSession) -> ClientCreateOut:
    return await clients_service.create_client(db, payload)
