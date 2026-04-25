from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_healthz(client) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.5.0"


@pytest.mark.asyncio
async def test_discovery(client) -> None:
    r = await client.get("/.well-known/auth")
    assert r.status_code == 200
    body = r.json()
    assert body["service"]
    assert body["jwt_algorithm"] == "HS256"
    assert "oauth_token" in body["endpoints"]
    role_names = {role["name"] for role in body["available_roles"]}
    assert {"student", "promotor", "lead", "candidato", "coordenador"} <= role_names
