from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from auth_service.audit.router import router as audit_router
from auth_service.auth.router import router as auth_router
from auth_service.clients.router import router as clients_router
from auth_service.config_app.router import router as config_router
from auth_service.core.config import get_settings
from auth_service.core.database import SessionLocal, init_db
from auth_service.core.logging import configure_logging
from auth_service.core.middleware import RequestIdMiddleware
from auth_service.core.rate_limit import limiter
from auth_service.roles.router import router as roles_router
from auth_service.roles.service import seed_defaults
from auth_service.sessions.router import router as sessions_router
from auth_service.users.router import router as users_router

_log = logging.getLogger("auth.app")


async def _check_db() -> dict:
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


async def _check_notify(settings) -> dict:
    """Resolve notify_base_url da mesma fonte que o fluxo real (DB > env)."""
    from auth_service.config_app import service as config_service

    try:
        async with SessionLocal() as db:
            url = (
                await config_service.get_value(db, "notify_base_url", settings.notify_base_url)
            ).rstrip("/")
    except Exception:
        url = settings.notify_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=settings.healthcheck_notify_timeout) as client:
            r = await client.get(f"{url}/")
        ok = 200 <= r.status_code < 500
        return {
            "status": "ok" if ok else "fail",
            "url": url,
            "http_status": r.status_code,
        }
    except httpx.HTTPError as exc:
        return {"status": "fail", "url": url, "error": str(exc)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.resolve_jwt_secret()  # bootstrap (gera/persiste se preciso)
    _log.info("starting", extra={"env": settings.env, "version": "0.5.0"})

    await init_db()
    async with SessionLocal() as db:
        await seed_defaults(db)
    yield
    _log.info("stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Auth",
        version="0.5.0",
        description="Servico de autenticacao OTP + JWT + M2M OAuth2 (client_credentials).",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_tags=[
            {"name": "auth", "description": "Fluxo de usuario: check, register, OTP, login, refresh, discovery"},
            {"name": "oauth", "description": "M2M OAuth2 client_credentials e gestao de clients"},
            {"name": "users", "description": "Roles e transicoes de usuarios"},
            {"name": "roles", "description": "Gestao de roles do sistema"},
            {"name": "config", "description": "Configuracao do servico"},
            {"name": "sessions", "description": "Gestao de sessoes (refresh tokens whitelist)"},
            {"name": "audit", "description": "Audit log de eventos sensiveis"},
            {"name": "health", "description": "Liveness e readiness probes"},
        ],
    )

    # Middlewares (ordem importa — RequestId fica externo pra cobrir todos)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    app.include_router(config_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(roles_router)
    app.include_router(clients_router)
    app.include_router(sessions_router)
    app.include_router(audit_router)

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict:
        """Liveness — responde se o processo esta vivo."""
        return {"status": "ok", "service": settings.app_name, "version": "0.5.0"}

    @app.get("/healthz/ready", tags=["health"])
    async def healthz_ready() -> JSONResponse:
        """Readiness — verifica DB e Notify. Retorna 503 se algum component degradado."""
        components: dict[str, dict] = {
            "database": await _check_db(),
            "notify": await _check_notify(settings),
        }
        overall_ok = all(c["status"] == "ok" for c in components.values())
        body = {"status": "ok" if overall_ok else "degraded", "components": components}
        return JSONResponse(status_code=200 if overall_ok else 503, content=body)

    return app


app = create_app()
