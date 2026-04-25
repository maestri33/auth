"""Testes de refresh token rotation, revoke, e reuse-detection."""
from __future__ import annotations

import re
from unittest.mock import AsyncMock, patch

import pytest

from auth_service.notify.client import NotifyRecipient


@pytest.fixture
def fake_notify():
    with patch("auth_service.notify.client.NotifyClient.check_recipient", new_callable=AsyncMock) as ch, \
         patch("auth_service.notify.client.NotifyClient.create_recipient", new_callable=AsyncMock) as cr, \
         patch("auth_service.notify.client.NotifyClient.send_notification", new_callable=AsyncMock) as sn:
        ch.return_value = NotifyRecipient(exists=False)
        cr.return_value = NotifyRecipient(exists=True, id="r-1", whatsapp_valid=True)
        yield {"check": ch, "create": cr, "send": sn}


async def _register_and_login(client, fake_notify, phone: str) -> tuple[str, dict]:
    """Helper: registra phone, dispara OTP, faz login. Retorna (external_id, tokens)."""
    r = await client.post("/register/", json={"phone": phone, "role": "lead"})
    assert r.status_code == 201, r.text
    ext = r.json()["external_id"]

    r = await client.post("/otp/request", json={"external_id": ext})
    assert r.status_code == 200, r.text

    sent = fake_notify["send"].call_args[0][1]
    otp = re.search(r"\b(\d{6})\b", sent).group(1)

    r = await client.post("/login/", json={"external_id": ext, "otp": otp})
    assert r.status_code == 200, r.text
    return ext, r.json()


@pytest.mark.asyncio
async def test_refresh_rotation_old_becomes_invalid(client, fake_notify) -> None:
    """Apos /refresh/, o refresh_token antigo nao serve mais."""
    _ext, tokens = await _register_and_login(client, fake_notify, "5511900001111")
    old_refresh = tokens["refresh_token"]

    # Primeiro refresh: ok, recebe novo par
    r = await client.post("/refresh/", json={"refresh_token": old_refresh})
    assert r.status_code == 200, r.text
    new_refresh = r.json()["refresh_token"]
    assert new_refresh != old_refresh

    # Tentar usar o velho de novo deve falhar (rotacao)
    r = await client.post("/refresh/", json={"refresh_token": old_refresh})
    assert r.status_code == 401
    assert "reuso" in r.json()["detail"] or "reutilizado" in r.json()["detail"]


@pytest.mark.asyncio
async def test_reuse_detection_revokes_all_sessions(client, fake_notify) -> None:
    """Re-uso de refresh ja revogado dispara revogacao em cadeia."""
    _ext, tokens = await _register_and_login(client, fake_notify, "5511900002222")
    old_refresh = tokens["refresh_token"]

    # Refresh: rotaciona e produz novo
    r = await client.post("/refresh/", json={"refresh_token": old_refresh})
    new_refresh = r.json()["refresh_token"]

    # Atacante usa o refresh antigo (ja revogado pela rotacao) — deve disparar reuse-detection
    r = await client.post("/refresh/", json={"refresh_token": old_refresh})
    assert r.status_code == 401
    assert "reutilizado" in r.json()["detail"]

    # Apos reuse-detection, ate o novo refresh foi revogado em cadeia
    r = await client.post("/refresh/", json={"refresh_token": new_refresh})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_admin_can_list_and_revoke_session(client, fake_notify) -> None:
    """Endpoint /sessions/{ext} (admin) lista e revoga."""
    from auth_service.clients.models import OAuthClient
    from auth_service.core.database import SessionLocal
    from auth_service.core.security import generate_client_secret, hash_client_secret

    secret = generate_client_secret()
    async with SessionLocal() as db:
        db.add(
            OAuthClient(
                client_id="admin-cli",
                client_secret_hash=hash_client_secret(secret),
                name="admin",
                scopes="admin",
            )
        )
        await db.commit()

    r = await client.post(
        "/oauth/token",
        json={
            "grant_type": "client_credentials",
            "client_id": "admin-cli",
            "client_secret": secret,
            "scope": "admin",
        },
    )
    admin_token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    ext, tokens = await _register_and_login(client, fake_notify, "5511900003333")

    # Lista sessoes
    r = await client.get(f"/sessions/{ext}", headers=headers)
    assert r.status_code == 200
    sessions = r.json()["sessions"]
    assert len(sessions) == 1
    jti = sessions[0]["jti"]
    assert sessions[0]["revoked_at"] is None

    # Revoga
    r = await client.post(f"/sessions/revoke/{jti}", headers=headers, json={"reason": "test"})
    assert r.status_code == 204

    # Tentar usar o refresh agora falha
    r = await client.post("/refresh/", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_audit_records_login_success(client, fake_notify) -> None:
    """Apos um login bem-sucedido, o audit log deve ter login.success."""
    from sqlalchemy import select

    from auth_service.audit.models import AuditEvent
    from auth_service.core.database import SessionLocal

    ext, _tokens = await _register_and_login(client, fake_notify, "5511900004444")

    async with SessionLocal() as db:
        rows = (
            await db.scalars(
                select(AuditEvent).where(AuditEvent.actor_id == ext).order_by(AuditEvent.id)
            )
        ).all()
    actions = [r.action for r in rows]
    assert "user.registered" in actions
    assert "login.success" in actions


@pytest.mark.asyncio
async def test_audit_endpoint_requires_admin(client) -> None:
    r = await client.get("/audit/events")
    assert r.status_code == 401
