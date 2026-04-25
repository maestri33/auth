from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from auth_service.auth.router import router as auth_router
from auth_service.clients.router import router as clients_router
from auth_service.config_app.router import router as config_router
from auth_service.core.config import get_settings
from auth_service.core.database import SessionLocal, init_db
from auth_service.core.rate_limit import limiter
from auth_service.roles.router import router as roles_router
from auth_service.roles.service import seed_defaults
from auth_service.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bootstrap do segredo JWT (gera/persiste se necessário)
    settings = get_settings()
    settings.resolve_jwt_secret()

    await init_db()
    async with SessionLocal() as db:
        await seed_defaults(db)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Auth",
        version="0.3.0",
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
        ],
    )

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

    app.include_router(config_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(roles_router)
    app.include_router(clients_router)

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict:
        return {"status": "ok", "service": settings.app_name, "version": "0.3.0"}

    return app


app = create_app()
