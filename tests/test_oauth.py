from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_oauth_create_requires_admin(client) -> None:
    r = await client.post(
        "/oauth/clients/", json={"client_id": "app-x", "name": "App X", "scopes": ["admin"]}
    )
    assert r.status_code == 401


async def _bootstrap_admin_client(client) -> tuple[str, str]:
    """Cria um client admin direto via DB para testar o resto. Em prod, isso vira CLI/seed."""
    from auth_service.clients.models import OAuthClient
    from auth_service.core.database import SessionLocal
    from auth_service.core.security import generate_client_secret, hash_client_secret

    secret = generate_client_secret()
    async with SessionLocal() as db:
        db.add(
            OAuthClient(
                client_id="bootstrap",
                client_secret_hash=hash_client_secret(secret),
                name="bootstrap",
                scopes="admin",
            )
        )
        await db.commit()
    return "bootstrap", secret


@pytest.mark.asyncio
async def test_oauth_token_and_admin_flow(client) -> None:
    cid, csecret = await _bootstrap_admin_client(client)

    # token
    r = await client.post(
        "/oauth/token",
        json={
            "grant_type": "client_credentials",
            "client_id": cid,
            "client_secret": csecret,
            "scope": "admin",
        },
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    assert r.json()["scope"] == "admin"

    headers = {"Authorization": f"Bearer {token}"}

    # criar role nova
    r = await client.post(
        "/roles/",
        json={"name": "ops", "description": "operadores"},
        headers=headers,
    )
    assert r.status_code == 201, r.text

    # listar clients
    r = await client.get("/oauth/clients/", headers=headers)
    assert r.status_code == 200
    assert any(c["client_id"] == cid for c in r.json()["clients"])


@pytest.mark.asyncio
async def test_oauth_invalid_secret(client) -> None:
    cid, _ = await _bootstrap_admin_client(client)
    r = await client.post(
        "/oauth/token",
        json={"grant_type": "client_credentials", "client_id": cid, "client_secret": "wrong"},
    )
    assert r.status_code == 401
