from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio


# Garante isolamento por teste antes de qualquer import do app
@pytest.fixture(scope="session", autouse=True)
def _env(tmp_path_factory: pytest.TempPathFactory) -> None:
    state = tmp_path_factory.mktemp("state")
    db_path = state / "test.db"
    os.environ["AUTH_ENV"] = "test"
    os.environ["AUTH_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["AUTH_STATE_DIR"] = str(state)
    os.environ["AUTH_JWT_SECRET"] = secrets.token_urlsafe(32)
    os.environ["AUTH_RATELIMIT_OTP"] = "1000/minute"
    os.environ["AUTH_RATELIMIT_LOGIN"] = "1000/minute"
    os.environ["AUTH_RATELIMIT_OAUTH"] = "1000/minute"
    # Notify base url só usado em testes live
    os.environ.setdefault("AUTH_NOTIFY_BASE_URL", "http://10.10.10.119:8000")


@pytest_asyncio.fixture
async def app():
    # Import tardio para pegar env vars
    from auth_service.core.config import get_settings
    from auth_service.core.database import Base, SessionLocal, engine
    from auth_service.core.rate_limit import limiter
    from auth_service.main import create_app
    from auth_service.roles.service import seed_defaults

    get_settings.cache_clear()
    # Reset slowapi state entre testes (in-memory bucket)
    limiter.reset()
    # Reset IdRateLimiters dos routers
    from auth_service.auth import router as auth_router
    auth_router._otp_id_limiter.reset()
    auth_router._login_id_limiter.reset()

    application = create_app()

    # Schema fresh por sessão de teste
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        await seed_defaults(db)

    yield application

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator:
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
