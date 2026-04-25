from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

import httpx

_CLI_RE = re.compile(r"^[a-zA-Z0-9_./\-]+$")


@dataclass(frozen=True)
class NotifyRecipient:
    exists: bool
    external_id: str | None = None
    whatsapp_valid: bool | None = None


class NotifyClient:
    def __init__(self, base_url: str, cli: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.cli = cli
        self.timeout = timeout

    async def check_recipient(self, number: str) -> NotifyRecipient:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/recipients/check", params={"q": number}
            )
            response.raise_for_status()
            data = response.json()
        exists = bool(data.get("found") or data.get("external_id"))
        return NotifyRecipient(
            exists=exists,
            external_id=data.get("external_id"),
            whatsapp_valid=data.get("whatsapp_valid"),
        )

    async def create_recipient(self, external_id: str, number: str) -> None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/recipients",
                json={"external_id": external_id, "phone": number},
            )
            response.raise_for_status()

    async def send_notification(self, external_id: str, message: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/notifications",
                    json={"external_id": external_id, "content": message},
                )
                response.raise_for_status()
                return
        except httpx.HTTPError:
            if not self.cli:
                raise
        if not _CLI_RE.match(self.cli):
            raise RuntimeError("notify CLI invalido")
        proc = await asyncio.create_subprocess_exec(
            self.cli,
            "send",
            "--external-id",
            external_id,
            "--message",
            message,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"notify CLI failed: {stderr.decode().strip()}")


async def notify_client_from_db(db, settings) -> NotifyClient:
    """Resolve config persistida no DB com fallback para settings."""
    from auth_service.config_app import service as config_service

    base_url = await config_service.get_value(db, "notify_base_url", settings.notify_base_url)
    cli = await config_service.get_value(db, "notify_cli", settings.notify_cli)
    return NotifyClient(base_url, cli, settings.notify_timeout_seconds)
