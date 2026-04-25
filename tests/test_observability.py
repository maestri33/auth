"""Testes dos itens "amarelos": logging+request_id, healthz/ready, IdRateLimiter."""
from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, patch

import pytest

from auth_service.core.logging import JSONFormatter, configure_logging, request_id_ctx
from auth_service.core.rate_limit import IdRateLimiter
from auth_service.notify.client import NotifyRecipient


# ---------------------------------------------------------------------------
# Logging estruturado
# ---------------------------------------------------------------------------
def test_json_formatter_includes_request_id_and_extras() -> None:
    fmt = JSONFormatter()
    record = logging.LogRecord(
        name="x", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    record.external_id = "abc-123"
    request_id_ctx.set("rid-xyz")
    out = fmt.format(record)
    data = json.loads(out)
    assert data["msg"] == "hello"
    assert data["level"] == "INFO"
    assert data["request_id"] == "rid-xyz"
    assert data["external_id"] == "abc-123"
    assert data["logger"] == "x"


def test_configure_logging_idempotent() -> None:
    configure_logging("INFO")
    configure_logging("DEBUG")
    root = logging.getLogger()
    assert len(root.handlers) == 1


@pytest.mark.asyncio
async def test_request_id_in_response_header(client) -> None:
    r = await client.get("/healthz")
    assert "x-request-id" in r.headers
    assert len(r.headers["x-request-id"]) >= 8


@pytest.mark.asyncio
async def test_request_id_propagated_from_client(client) -> None:
    r = await client.get("/healthz", headers={"X-Request-Id": "trace-abc-1"})
    assert r.headers["x-request-id"] == "trace-abc-1"


# ---------------------------------------------------------------------------
# Healthz / ready
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_healthz_ready_ok(client) -> None:
    """Notify mockado retornando ok — readiness deve passar."""
    with patch(
        "auth_service.main._check_notify",
        new_callable=AsyncMock,
        return_value={"status": "ok", "url": "http://mock", "http_status": 200},
    ):
        r = await client.get("/healthz/ready")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["components"]["database"]["status"] == "ok"
    assert body["components"]["notify"]["status"] == "ok"


@pytest.mark.asyncio
async def test_healthz_ready_notify_down_returns_503(client) -> None:
    with patch(
        "auth_service.main._check_notify",
        new_callable=AsyncMock,
        return_value={"status": "fail", "url": "http://mock", "error": "connection refused"},
    ):
        r = await client.get("/healthz/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["components"]["notify"]["status"] == "fail"
    assert body["components"]["database"]["status"] == "ok"


# ---------------------------------------------------------------------------
# IdRateLimiter
# ---------------------------------------------------------------------------
def test_id_rate_limiter_allows_under_limit_blocks_after() -> None:
    rl = IdRateLimiter("3/minute")
    assert rl.check("alice") is True
    assert rl.check("alice") is True
    assert rl.check("alice") is True
    assert rl.check("alice") is False  # 4o estoura
    assert rl.check("bob") is True  # outra chave nao impacta


def test_id_rate_limiter_reset() -> None:
    rl = IdRateLimiter("1/minute")
    assert rl.check("k") is True
    assert rl.check("k") is False
    rl.reset("k")
    assert rl.check("k") is True


# ---------------------------------------------------------------------------
# Rate limit por external_id em /otp/request
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_notify_for_otp():
    with patch("auth_service.notify.client.NotifyClient.check_recipient", new_callable=AsyncMock) as ch, \
         patch("auth_service.notify.client.NotifyClient.create_recipient", new_callable=AsyncMock) as cr, \
         patch("auth_service.notify.client.NotifyClient.send_notification", new_callable=AsyncMock) as sn:
        ch.return_value = NotifyRecipient(exists=False)
        cr.return_value = NotifyRecipient(exists=True, id="r-1", whatsapp_valid=True)
        yield {"check": ch, "create": cr, "send": sn}


@pytest.mark.asyncio
async def test_otp_request_rate_limit_per_external_id(client, fake_notify_for_otp, monkeypatch) -> None:
    # Forca limite baixo — usar IdRateLimiter direto no router
    from auth_service.auth import router as auth_router_mod

    auth_router_mod._otp_id_limiter = IdRateLimiter("2/minute")

    r = await client.post("/register/", json={"phone": "5511955554444", "role": "lead"})
    assert r.status_code == 201, r.text
    ext = r.json()["external_id"]

    # 1 e 2 OK
    for _ in range(2):
        r = await client.post("/otp/request", json={"external_id": ext})
        assert r.status_code == 200, r.text
    # 3 deve estourar (429)
    r = await client.post("/otp/request", json={"external_id": ext})
    assert r.status_code == 429
    assert "muitas tentativas" in r.json()["detail"]
