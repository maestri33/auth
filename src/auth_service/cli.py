"""auth-cli — administração e debug do servico Auth.

Instala com `pip install -e .` e use `auth-cli --help`.
"""
from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable
from datetime import UTC
from typing import Annotated, Any, TypeVar

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.clients.models import OAuthClient
from auth_service.clients.schemas import ClientCreate
from auth_service.clients.service import create_client as create_client_svc
from auth_service.config_app.models import AppConfig
from auth_service.core.config import get_settings
from auth_service.core.database import SessionLocal
from auth_service.core.security import (
    decode_token,
    generate_client_secret,
    hash_client_secret,
)
from auth_service.roles.models import Role
from auth_service.roles.schemas import RoleCreate
from auth_service.roles.service import create_role as create_role_svc
from auth_service.roles.service import list_roles as list_roles_svc
from auth_service.users import service as users_service
from auth_service.users.models import OtpChallenge, User

T = TypeVar("T")
console = Console()
err = Console(stderr=True)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _run(coro: Awaitable[T]) -> T:
    return asyncio.run(coro)


async def _session() -> AsyncSession:
    return SessionLocal()


def _die(msg: str, code: int = 1) -> None:
    err.print(f"[bold red]erro:[/] {msg}")
    raise typer.Exit(code=code)


def _ok(msg: str) -> None:
    console.print(f"[green]✓[/] {msg}")


def _kv(data: dict[str, Any]) -> None:
    for k, v in data.items():
        console.print(f"  [cyan]{k}[/]: {v}")


# ---------------------------------------------------------------------------
# app raiz + callback
# ---------------------------------------------------------------------------
app = typer.Typer(
    name="auth-cli",
    help="Administracao do servico Auth (M2M clients, users, roles, tokens, db, server).",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.callback()
def root(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Output detalhado.")] = False,
) -> None:
    """Auth admin CLI. Use [bold]auth-cli <dominio> --help[/] para detalhes."""
    if verbose:
        s = get_settings()
        err.print(
            f"[dim]env={s.env} db={s.database_url} notify={s.notify_base_url} kid={s.jwt_key_id}[/]"
        )


# ===========================================================================
# clients (M2M OAuth2)
# ===========================================================================
clients_app = typer.Typer(help="Gestao de clients OAuth2 (M2M).", no_args_is_help=True)
app.add_typer(clients_app, name="clients")


@clients_app.command("create")
def clients_create(
    client_id: Annotated[str, typer.Argument(help="ID do client (slug).")],
    name: Annotated[str, typer.Option("--name", "-n", help="Nome legivel.")] = "",
    scope: Annotated[
        list[str], typer.Option("--scope", "-s", help="Escopo (repetir para varios).")
    ] = [],
) -> None:
    """Cria um client M2M e imprime [bold]client_secret[/] uma unica vez."""
    nm = name or client_id

    async def _do() -> None:
        async with SessionLocal() as db:
            try:
                out = await create_client_svc(
                    db, ClientCreate(client_id=client_id, name=nm, scopes=scope)
                )
            except Exception as exc:
                _die(str(exc))
        _ok("client criado")
        _kv(
            {
                "client_id": out.client_id,
                "client_secret": out.client_secret,
                "name": out.name,
                "scopes": " ".join(out.scopes) or "(nenhum)",
            }
        )
        err.print("[yellow]anote o client_secret agora — ele nao sera exibido de novo.[/]")

    _run(_do())


@clients_app.command("list")
def clients_list() -> None:
    """Lista todos os clients."""

    async def _do() -> list[OAuthClient]:
        async with SessionLocal() as db:
            return list((await db.scalars(select(OAuthClient).order_by(OAuthClient.client_id))).all())

    rows = _run(_do())
    table = Table(title=f"clients ({len(rows)})")
    table.add_column("client_id", style="cyan")
    table.add_column("name")
    table.add_column("scopes")
    table.add_column("active")
    for c in rows:
        table.add_row(c.client_id, c.name, " ".join(c.scope_list) or "—", "✓" if c.is_active else "✗")
    console.print(table)


@clients_app.command("delete")
def clients_delete(
    client_id: Annotated[str, typer.Argument()],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Pular confirmacao.")] = False,
) -> None:
    """Remove um client."""
    if not yes:
        typer.confirm(f"deletar client {client_id}?", abort=True)

    async def _do() -> None:
        async with SessionLocal() as db:
            c = await db.get(OAuthClient, client_id)
            if not c:
                _die("client nao encontrado", code=2)
            await db.delete(c)
            await db.commit()
        _ok(f"client {client_id} deletado")

    _run(_do())


@clients_app.command("rotate")
def clients_rotate(client_id: Annotated[str, typer.Argument()]) -> None:
    """Gera um novo client_secret para um client existente."""

    async def _do() -> None:
        async with SessionLocal() as db:
            c = await db.get(OAuthClient, client_id)
            if not c:
                _die("client nao encontrado", code=2)
            new_secret = generate_client_secret()
            c.client_secret_hash = hash_client_secret(new_secret)
            await db.commit()
        _ok(f"secret rotacionado para {client_id}")
        _kv({"client_secret": new_secret})
        err.print("[yellow]anote agora.[/]")

    _run(_do())


# ===========================================================================
# users
# ===========================================================================
users_app = typer.Typer(help="Gestao de usuarios e roles atribuidas.", no_args_is_help=True)
app.add_typer(users_app, name="users")


@users_app.command("list")
def users_list(
    limit: Annotated[int, typer.Option("--limit", "-l", min=1, max=1000)] = 50,
) -> None:
    """Lista usuarios."""

    async def _do() -> list[User]:
        async with SessionLocal() as db:
            return list(
                (await db.scalars(select(User).order_by(User.created_at.desc()).limit(limit))).all()
            )

    rows = _run(_do())
    table = Table(title=f"users ({len(rows)})")
    table.add_column("external_id", style="cyan")
    table.add_column("phone")
    table.add_column("active")
    table.add_column("created_at", style="dim")
    for u in rows:
        table.add_row(
            u.external_id, u.phone, "✓" if u.is_active else "✗", u.created_at.isoformat(timespec="seconds")
        )
    console.print(table)


@users_app.command("get")
def users_get(
    ref: Annotated[str, typer.Argument(help="external_id ou phone.")],
) -> None:
    """Mostra um usuario com roles."""

    async def _do() -> tuple[User | None, list[str]]:
        async with SessionLocal() as db:
            user = await db.get(User, ref) or await db.scalar(select(User).where(User.phone == ref))
            if not user:
                return None, []
            roles = await users_service.active_roles(db, user.external_id)
            return user, roles

    user, roles = _run(_do())
    if not user:
        _die("usuario nao encontrado", code=2)
    _kv(
        {
            "external_id": user.external_id,
            "phone": user.phone,
            "active": user.is_active,
            "created_at": user.created_at.isoformat(timespec="seconds"),
            "roles": ", ".join(roles) or "(nenhuma)",
        }
    )


@users_app.command("grant")
def users_grant(
    external_id: Annotated[str, typer.Argument()],
    role: Annotated[str, typer.Argument()],
) -> None:
    """Atribui uma role ao usuario (valida prereq + incompatibilidade)."""

    async def _do() -> list[str]:
        async with SessionLocal() as db:
            await users_service.set_user_role(db, external_id, role, enabled=True)
            await db.commit()
            return await users_service.active_roles(db, external_id)

    try:
        roles = _run(_do())
    except Exception as exc:
        _die(str(exc))
    _ok(f"role {role} ativada — agora: {', '.join(roles)}")


@users_app.command("revoke")
def users_revoke(
    external_id: Annotated[str, typer.Argument()],
    role: Annotated[str, typer.Argument()],
) -> None:
    """Desativa uma role do usuario."""

    async def _do() -> list[str]:
        async with SessionLocal() as db:
            await users_service.set_user_role(db, external_id, role, enabled=False)
            await db.commit()
            return await users_service.active_roles(db, external_id)

    roles = _run(_do())
    _ok(f"role {role} desativada — agora: {', '.join(roles) or '(nenhuma)'}")


@users_app.command("delete")
def users_delete(
    external_id: Annotated[str, typer.Argument()],
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
) -> None:
    """Remove um usuario e seus vinculos (roles + OTPs)."""
    if not yes:
        typer.confirm(f"deletar user {external_id}?", abort=True)

    async def _do() -> None:
        async with SessionLocal() as db:
            user = await db.get(User, external_id)
            if not user:
                _die("usuario nao encontrado", code=2)
            await db.delete(user)
            await db.commit()
        _ok(f"user {external_id} deletado")

    _run(_do())


# ===========================================================================
# roles
# ===========================================================================
roles_app = typer.Typer(help="Gestao de roles do sistema.", no_args_is_help=True)
app.add_typer(roles_app, name="roles")


@roles_app.command("list")
def roles_list() -> None:
    """Lista roles cadastradas."""

    async def _do():
        async with SessionLocal() as db:
            return await list_roles_svc(db)

    rows = _run(_do())
    table = Table(title=f"roles ({len(rows)})")
    table.add_column("name", style="cyan")
    table.add_column("staff")
    table.add_column("transitory")
    table.add_column("→")
    table.add_column("requires")
    table.add_column("incompatible_with")
    for r in rows:
        table.add_row(
            r.name,
            "✓" if r.is_staff else "",
            "✓" if r.is_transitory else "",
            r.transitions_to or "",
            r.requires_role or "",
            ", ".join(r.incompatible_roles) or "",
        )
    console.print(table)


@roles_app.command("create")
def roles_create(
    name: Annotated[str, typer.Argument()],
    staff: Annotated[bool, typer.Option("--staff", help="Role de staff.")] = False,
    transitory: Annotated[bool, typer.Option("--transitory", help="Role transitoria.")] = False,
    transitions_to: Annotated[str, typer.Option("--transitions-to", help="Para roles transitorias.")] = "",
    requires: Annotated[str, typer.Option("--requires", help="Role prerequisita.")] = "",
    incompatible_with: Annotated[
        list[str], typer.Option("--incompatible-with", "-x", help="Repetir para varias.")
    ] = [],
    description: Annotated[str, typer.Option("--description", "-d")] = "",
) -> None:
    """Cria uma nova role."""
    payload = RoleCreate(
        name=name,
        is_staff=staff,
        is_transitory=transitory,
        transitions_to=transitions_to or None,
        requires_role=requires or None,
        incompatible_roles=incompatible_with,
        description=description or None,
    )

    async def _do() -> Role:
        async with SessionLocal() as db:
            return await create_role_svc(db, payload)

    try:
        _run(_do())
    except Exception as exc:
        _die(str(exc))
    _ok(f"role {name} criada")


# ===========================================================================
# token
# ===========================================================================
token_app = typer.Typer(help="Inspecao e debug de tokens JWT.", no_args_is_help=True)
app.add_typer(token_app, name="token")


@token_app.command("decode")
def token_decode(
    token: Annotated[str, typer.Argument()],
    expected_type: Annotated[
        str, typer.Option("--type", help="access | refresh | client (padrao: detecta).")
    ] = "",
) -> None:
    """Decodifica e valida um JWT (assinatura + exp + type opcional)."""
    import jwt as _jwt

    s = get_settings()
    try:
        header = _jwt.get_unverified_header(token)
        if expected_type:
            payload = decode_token(token, expected_type=expected_type)
        else:
            payload = _jwt.decode(token, s.resolve_jwt_secret(), algorithms=[s.jwt_algorithm])
    except Exception as exc:
        _die(f"token invalido: {exc}")

    console.print("[bold]header[/]")
    console.print_json(data=header)
    console.print("[bold]payload[/]")
    console.print_json(data=payload)


# ===========================================================================
# otp
# ===========================================================================
otp_app = typer.Typer(help="OTP challenges (debug).", no_args_is_help=True)
app.add_typer(otp_app, name="otp")


@otp_app.command("purge")
def otp_purge() -> None:
    """Remove desafios consumidos ou expirados."""
    from datetime import datetime

    async def _do() -> int:
        async with SessionLocal() as db:
            result = await db.execute(
                delete(OtpChallenge).where(
                    (OtpChallenge.consumed_at.is_not(None))
                    | (OtpChallenge.expires_at < datetime.now(tz=UTC))
                )
            )
            await db.commit()
            return result.rowcount or 0

    n = _run(_do())
    _ok(f"{n} desafio(s) removido(s)")


# ===========================================================================
# db
# ===========================================================================
db_app = typer.Typer(help="Migracoes Alembic.", no_args_is_help=True)
app.add_typer(db_app, name="db")


def _alembic(args: list[str]) -> int:
    import subprocess

    return subprocess.call([sys.executable, "-m", "alembic", *args])


@db_app.command("upgrade")
def db_upgrade(
    revision: Annotated[str, typer.Argument()] = "head",
) -> None:
    """alembic upgrade <revision>."""
    raise typer.Exit(code=_alembic(["upgrade", revision]))


@db_app.command("current")
def db_current() -> None:
    """alembic current."""
    raise typer.Exit(code=_alembic(["current"]))


@db_app.command("revision")
def db_revision(
    message: Annotated[str, typer.Option("--message", "-m")],
    autogenerate: Annotated[bool, typer.Option("--autogenerate/--no-autogenerate")] = True,
) -> None:
    """alembic revision [--autogenerate] -m <msg>."""
    args = ["revision", "-m", message]
    if autogenerate:
        args.insert(1, "--autogenerate")
    raise typer.Exit(code=_alembic(args))


# ===========================================================================
# config
# ===========================================================================
config_app_cli = typer.Typer(help="Configuracao persistida no DB (notify_base_url, notify_cli).")
app.add_typer(config_app_cli, name="config")


@config_app_cli.command("show")
def config_show() -> None:
    """Mostra config persistida no DB (e fallback para env)."""
    s = get_settings()

    async def _do() -> dict:
        async with SessionLocal() as db:
            rows = (await db.scalars(select(AppConfig))).all()
            persisted = {r.key: r.value for r in rows}
            return persisted

    persisted = _run(_do())
    _kv(
        {
            "notify_base_url (db)": persisted.get("notify_base_url", "(nao set)"),
            "notify_base_url (env)": s.notify_base_url,
            "notify_cli (db)": persisted.get("notify_cli", "(nao set)"),
            "notify_cli (env)": s.notify_cli,
        }
    )


@config_app_cli.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help="notify_base_url | notify_cli")],
    value: Annotated[str, typer.Argument()],
) -> None:
    """Define um valor de config no DB."""
    if key not in {"notify_base_url", "notify_cli"}:
        _die(f"chave invalida: {key}", code=2)

    async def _do() -> None:
        async with SessionLocal() as db:
            item = await db.get(AppConfig, key)
            if item:
                item.value = value
            else:
                db.add(AppConfig(key=key, value=value))
            await db.commit()

    _run(_do())
    _ok(f"{key} = {value}")


# ===========================================================================
# server
# ===========================================================================
server_app = typer.Typer(help="Subir o servico via uvicorn.", no_args_is_help=True)
app.add_typer(server_app, name="server")


@server_app.command("run")
def server_run(
    host: Annotated[str, typer.Option("--host")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p")] = 80,
    reload: Annotated[bool, typer.Option("--reload", help="Auto-reload (dev).")] = False,
    workers: Annotated[int, typer.Option("--workers", "-w", min=1)] = 1,
) -> None:
    """Inicia o servidor (auth_service.main:app)."""
    import uvicorn

    uvicorn.run(
        "auth_service.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


# ===========================================================================
# misc
# ===========================================================================
@app.command("info")
def info() -> None:
    """Resumo de configuracao e endpoints."""
    s = get_settings()
    _kv(
        {
            "env": s.env,
            "app_name": s.app_name,
            "database_url": s.database_url,
            "jwt_algorithm": s.jwt_algorithm,
            "jwt_key_id": s.jwt_key_id,
            "access_token_minutes": s.access_token_minutes,
            "refresh_token_days": s.refresh_token_days,
            "otp_ttl_minutes": s.otp_ttl_minutes,
            "notify_base_url": s.notify_base_url,
            "ratelimit_otp": s.ratelimit_otp,
            "ratelimit_login": s.ratelimit_login,
            "ratelimit_oauth": s.ratelimit_oauth,
        }
    )


@app.command("health")
def health(
    base_url: Annotated[str, typer.Option("--base-url")] = "http://127.0.0.1",
) -> None:
    """Bate em /healthz."""
    import httpx

    try:
        r = httpx.get(f"{base_url.rstrip('/')}/healthz", timeout=3.0)
        console.print_json(data=r.json())
        raise typer.Exit(code=0 if r.status_code == 200 else 1)
    except httpx.HTTPError as exc:
        _die(str(exc))


def main() -> None:
    """Console entrypoint."""
    app()


if __name__ == "__main__":
    main()
