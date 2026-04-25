from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from auth_service.notify.client import NotifyRecipient


@pytest.fixture
def fake_notify():
    """Patch global do NotifyClient para não bater no Notify real."""
    with patch("auth_service.notify.client.NotifyClient.check_recipient", new_callable=AsyncMock) as check, \
         patch("auth_service.notify.client.NotifyClient.create_recipient", new_callable=AsyncMock) as create, \
         patch("auth_service.notify.client.NotifyClient.delete_recipient", new_callable=AsyncMock) as delete, \
         patch("auth_service.notify.client.NotifyClient.send_notification", new_callable=AsyncMock) as send:
        check.return_value = NotifyRecipient(exists=False)
        create.return_value = NotifyRecipient(exists=True, id="rid-1", whatsapp_valid=True)
        yield {"check": check, "create": create, "delete": delete, "send": send}


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


@pytest.mark.asyncio
async def test_register_blocks_when_already_in_notify(client, fake_notify) -> None:
    fake_notify["check"].return_value = NotifyRecipient(
        exists=True, id="rid-existing", external_id="x", whatsapp_valid=True
    )
    r = await client.post("/register/", json={"phone": "5511966665555", "role": "lead"})
    assert r.status_code == 409
    assert "Notify" in r.json()["detail"]
    fake_notify["create"].assert_not_called()


@pytest.mark.asyncio
async def test_register_blocks_when_no_whatsapp(client, fake_notify) -> None:
    fake_notify["check"].return_value = NotifyRecipient(exists=False)
    fake_notify["create"].return_value = NotifyRecipient(
        exists=True, id="rid-2", whatsapp_valid=False
    )
    r = await client.post("/register/", json={"phone": "5511944443333", "role": "lead"})
    assert r.status_code == 400
    assert "WhatsApp" in r.json()["detail"]
    # Recipient orfao deve ser deletado no rollback
    fake_notify["delete"].assert_awaited_once_with("rid-2")
