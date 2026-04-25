"""Middlewares: request_id e logging de requisicao."""
from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from auth_service.core.logging import request_id_ctx

_log = logging.getLogger("auth.request")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid4().hex[:16]
        token = request_id_ctx.set(rid)
        start = time.monotonic()
        try:
            response = await call_next(request)
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            response.headers["x-request-id"] = rid
            _log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "client": request.client.host if request.client else None,
                },
            )
            return response
        except Exception:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            _log.exception(
                "request crashed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "client": request.client.host if request.client else None,
                },
            )
            raise
        finally:
            request_id_ctx.reset(token)
