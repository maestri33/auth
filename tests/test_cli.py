from __future__ import annotations

import pytest
from typer.testing import CliRunner

from auth_service.cli import app
from auth_service.core.database import Base, SessionLocal, engine
from auth_service.roles.service import seed_defaults

runner = CliRunner()


@pytest.fixture
async def fresh_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        await seed_defaults(db)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_help_root() -> None:
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    out = r.stdout
    for sub in ("clients", "users", "roles", "token", "otp", "db", "server", "config", "info", "health"):
        assert sub in out


def test_info(fresh_db) -> None:
    r = runner.invoke(app, ["info"])
    assert r.exit_code == 0
    assert "database_url" in r.stdout
    assert "jwt_algorithm" in r.stdout


def test_roles_list_seeded(fresh_db) -> None:
    r = runner.invoke(app, ["roles", "list"])
    assert r.exit_code == 0, r.stdout
    out = r.stdout
    for name in ("student", "promotor", "lead", "candidato", "coordenador"):
        assert name in out


def test_clients_full_lifecycle(fresh_db) -> None:
    # create
    r = runner.invoke(app, ["clients", "create", "app-x", "--name", "App X", "--scope", "admin"])
    assert r.exit_code == 0, r.stdout + r.stderr
    assert "client_secret" in r.stdout

    # list
    r = runner.invoke(app, ["clients", "list"])
    assert r.exit_code == 0
    assert "app-x" in r.stdout
    assert "admin" in r.stdout

    # rotate
    r = runner.invoke(app, ["clients", "rotate", "app-x"])
    assert r.exit_code == 0
    assert "client_secret" in r.stdout

    # delete (com confirmacao via stdin)
    r = runner.invoke(app, ["clients", "delete", "app-x"], input="y\n")
    assert r.exit_code == 0
    assert "deletado" in r.stdout

    # nao existe mais
    r = runner.invoke(app, ["clients", "delete", "app-x", "--yes"])
    assert r.exit_code == 2


def test_users_grant_revoke(fresh_db) -> None:
    # registra usuario via servico (atalho — bypassa Notify)
    import asyncio

    from auth_service.users.models import User
    from auth_service.users.service import set_user_role

    async def setup_user() -> str:
        async with SessionLocal() as db:
            ext = "11111111-1111-1111-1111-111111111111"
            db.add(User(external_id=ext, phone="5511900000001"))
            await db.flush()
            await set_user_role(db, ext, "lead", enabled=True)
            await db.commit()
            return ext

    ext = asyncio.run(setup_user())

    r = runner.invoke(app, ["users", "get", ext])
    assert r.exit_code == 0
    assert "lead" in r.stdout

    # transitar lead -> student via grant student e revoke lead
    r = runner.invoke(app, ["users", "revoke", ext, "lead"])
    assert r.exit_code == 0

    r = runner.invoke(app, ["users", "grant", ext, "student"])
    assert r.exit_code == 0
    assert "student" in r.stdout


def test_token_decode_invalid() -> None:
    r = runner.invoke(app, ["token", "decode", "not-a-jwt"])
    assert r.exit_code == 1
    assert "invalido" in r.stderr or "invalido" in r.stdout
