"""Testes que batem no Notify real em AUTH_NOTIFY_BASE_URL.

Ative com: pytest -m notify_live
"""
from __future__ import annotations

import os

import httpx
import pytest

from auth_service.notify.client import NotifyClient

pytestmark = pytest.mark.notify_live


@pytest.fixture
def notify() -> NotifyClient:
    base = os.environ.get("AUTH_NOTIFY_BASE_URL", "http://10.10.10.119:8000")
    return NotifyClient(base_url=base, cli="", timeout=10.0)


@pytest.mark.asyncio
async def test_notify_alive(notify: NotifyClient) -> None:
    """Sanity check: o serviço Notify responde."""
    async with httpx.AsyncClient(timeout=5.0) as c:
        try:
            r = await c.get(f"{notify.base_url}/docs")
        except httpx.HTTPError as exc:
            pytest.skip(f"Notify offline: {exc}")
    assert r.status_code in (200, 301, 302, 307, 308)


@pytest.mark.asyncio
async def test_notify_check_unknown_recipient(notify: NotifyClient) -> None:
    try:
        result = await notify.check_recipient("5500000000000")
    except httpx.HTTPError as exc:
        pytest.skip(f"Notify check indisponivel: {exc}")
    # Apenas valida shape, não o resultado em si.
    assert isinstance(result.exists, bool)
