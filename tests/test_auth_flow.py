from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from auth_service.notify.client import NotifyRecipient


@pytest.fixture
def fake_notify():
    """Patch global do NotifyClient para não bater no Notify real."""
    with patch("auth_service.notify.client.NotifyClient.check_recipient", new_callable=AsyncMock) as check, \
         patch("auth_service.notify.client.NotifyClient.create_recipient", new_callable=AsyncMock) as create, \
         patch("auth_service.notify.client.NotifyClient.send_notification", new_callable=AsyncMock) as send:
        check.return_value = NotifyRecipient(exists=False, whatsapp_valid=True)
        yield {"check": check, "create": create, "send": send}


@pytest.mark.asyncio
async def test_register_flow_invalid_role(client, fake_notify) -> None:
    r = await client.post("/register/", json={"phone": "5511999999999", "role": "student"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_register_login_refresh(client, fake_notify) -> None:
    phone = "5511988887777"

    r = await client.post("/register/", json={"phone": phone, "role": "lead"})
    assert r.status_code == 201, r.text
    external_id = r.json()["external_id"]

    # OTP — capturamos o argumento do send_notification
    r = await client.post("/otp/request", json={"phone": phone})
    assert r.status_code == 200, r.text

    # Resgata o OTP gerado a partir da chamada mockada
    args, _kwargs = fake_notify["send"].call_args
    sent_message = args[1]
    # otp.md tem placeholder {{ otp }}, então a mensagem contém os 6 dígitos
    import re
    match = re.search(r"\b(\d{6})\b", sent_message)
    assert match, f"OTP nao encontrado em mensagem: {sent_message}"
    otp = match.group(1)

    r = await client.post("/login/", json={"external_id": external_id, "otp": otp})
    assert r.status_code == 200, r.text
    tokens = r.json()
    assert tokens["roles"] == ["lead"]
    refresh = tokens["refresh_token"]

    # Reuso do mesmo OTP deve falhar (consume atomico)
    r = await client.post("/login/", json={"external_id": external_id, "otp": otp})
    assert r.status_code == 401

    # Refresh
    r = await client.post("/refresh/", json={"refresh_token": refresh})
    assert r.status_code == 200, r.text
    assert r.json()["external_id"] == external_id

    # Access token nao serve como refresh
    access = tokens["access_token"]
    r = await client.post("/refresh/", json={"refresh_token": access})
    assert r.status_code == 401
