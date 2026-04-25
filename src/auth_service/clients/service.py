from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.clients.models import OAuthClient
from auth_service.clients.schemas import ClientCreate, ClientCreateOut, ClientOut
from auth_service.core.exceptions import Conflict, Unauthorized
from auth_service.core.security import (
    generate_client_secret,
    hash_client_secret,
    verify_client_secret,
)


async def create_client(db: AsyncSession, payload: ClientCreate) -> ClientCreateOut:
    if await db.get(OAuthClient, payload.client_id):
        raise Conflict("client_id ja existe")
    secret = generate_client_secret()
    db.add(
        OAuthClient(
            client_id=payload.client_id,
            client_secret_hash=hash_client_secret(secret),
            name=payload.name,
            scopes=" ".join(sorted(set(payload.scopes))),
        )
    )
    await db.commit()
    return ClientCreateOut(
        client_id=payload.client_id,
        client_secret=secret,
        name=payload.name,
        scopes=sorted(set(payload.scopes)),
    )


async def list_clients(db: AsyncSession) -> list[ClientOut]:
    rows = (await db.scalars(select(OAuthClient).order_by(OAuthClient.client_id))).all()
    return [
        ClientOut(client_id=r.client_id, name=r.name, scopes=r.scope_list, is_active=r.is_active)
        for r in rows
    ]


async def authenticate_client(
    db: AsyncSession, client_id: str, client_secret: str, scope: str | None
) -> tuple[OAuthClient, list[str]]:
    client = await db.get(OAuthClient, client_id)
    if not client or not client.is_active:
        raise Unauthorized("client invalido")
    if not verify_client_secret(client_secret, client.client_secret_hash):
        raise Unauthorized("client invalido")
    granted = client.scope_list
    if scope:
        requested = [s for s in scope.split(" ") if s]
        not_allowed = [s for s in requested if s not in granted]
        if not_allowed:
            raise Unauthorized(f"escopo nao permitido: {', '.join(not_allowed)}")
        granted = requested
    return client, granted
