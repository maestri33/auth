from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select

from auth_service.auth import service as auth_service
from auth_service.auth.schemas import (
    CheckRequest,
    CheckResponse,
    DiscoveryResponse,
    LoginRequest,
    OtpRequest,
    OtpResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from auth_service.core.config import get_settings
from auth_service.core.deps import DbSession
from auth_service.core.docs import DOCS_DIR, markdown_response
from auth_service.core.exceptions import BadRequest, Conflict, NotFound, Unauthorized
from auth_service.core.rate_limit import limiter
from auth_service.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from auth_service.notify.client import notify_client_from_db
from auth_service.roles.models import Role, RoleIncompatibility
from auth_service.users import service as users_service
from auth_service.users.models import User

_settings = get_settings()
router = APIRouter(tags=["auth"])

INITIAL_ROLES = {"lead", "candidato"}


# ---------------------------------------------------------------------------
# /check/
# ---------------------------------------------------------------------------
@router.get("/check/", include_in_schema=False)
async def get_check_doc():
    return markdown_response(DOCS_DIR, "check.md")


@router.post("/check/", response_model=CheckResponse)
async def check(payload: CheckRequest, db: DbSession) -> CheckResponse:
    notify = await notify_client_from_db(db, _settings)
    recipient = await notify.check_recipient(payload.phone)
    local_user = await db.scalar(select(User).where(User.phone == payload.phone))
    return CheckResponse(
        found_in_notify=recipient.exists,
        found_locally=local_user is not None,
        notify_external_id=recipient.external_id,
        local_external_id=local_user.external_id if local_user else None,
        whatsapp_valid=recipient.whatsapp_valid,
    )


# ---------------------------------------------------------------------------
# /register/
# ---------------------------------------------------------------------------
@router.get("/register/", include_in_schema=False)
async def get_register_doc():
    return markdown_response(DOCS_DIR, "register.md")


@router.post(
    "/register/",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "role nao encontrada"},
        400: {"description": "role nao permitida ou numero sem WhatsApp"},
        409: {"description": "telefone ja cadastrado (local ou Notify)"},
    },
)
async def register(payload: RegisterRequest, db: DbSession) -> RegisterResponse:
    if not await db.get(Role, payload.role):
        raise NotFound("role nao encontrada")
    if payload.role not in INITIAL_ROLES:
        raise BadRequest(
            "role de registro deve ser uma das fases iniciais: " + ", ".join(sorted(INITIAL_ROLES))
        )
    if await db.scalar(select(User).where(User.phone == payload.phone)):
        raise Conflict("telefone ja cadastrado")

    notify = await notify_client_from_db(db, _settings)

    # Bloqueio 1: numero ja cadastrado no Notify
    pre = await notify.check_recipient(payload.phone)
    if pre.exists:
        raise Conflict("telefone ja cadastrado no Notify")

    # Cria recipient no Notify (validacao de WhatsApp acontece aqui)
    external_id = str(uuid4())
    recipient = await notify.create_recipient(external_id, payload.phone)

    # Bloqueio 2: numero sem WhatsApp valido -> rollback do recipient
    if recipient.whatsapp_valid is False:
        if recipient.id:
            try:
                await notify.delete_recipient(recipient.id)
            except Exception:
                pass
        raise BadRequest("numero sem WhatsApp valido")

    # Cria usuario local apenas apos validar Notify + WhatsApp
    db.add(User(external_id=external_id, phone=payload.phone))
    await db.flush()
    await users_service.set_user_role(db, external_id, payload.role, enabled=True)
    await db.commit()

    return RegisterResponse(
        status="ok",
        message="cadastro realizado com sucesso",
        external_id=external_id,
        role=payload.role,
    )


# ---------------------------------------------------------------------------
# /otp/request
# ---------------------------------------------------------------------------
@router.get("/otp/request", include_in_schema=False)
async def get_otp_doc():
    return markdown_response(DOCS_DIR, "otp-request.md")


@router.post(
    "/otp/request",
    response_model=OtpResponse,
    responses={400: {"description": "parametros invalidos"}, 404: {"description": "usuario nao encontrado"}},
)
@limiter.limit(_settings.ratelimit_otp)
async def otp_request(
    request: Request, response: Response, payload: OtpRequest, db: DbSession
) -> OtpResponse:
    if not payload.external_id and not payload.phone:
        raise BadRequest("informe external_id ou phone")

    user: User | None = None
    if payload.external_id:
        user = await db.get(User, payload.external_id)
    elif payload.phone:
        user = await db.scalar(select(User).where(User.phone == payload.phone))

    if not user:
        raise NotFound("usuario nao encontrado")

    notify = await notify_client_from_db(db, _settings)
    otp = await auth_service.create_otp(db, user.external_id)
    await notify.send_notification(user.external_id, auth_service.build_otp_message(otp))
    await db.commit()

    return OtpResponse(status="ok", message="otp enviado com sucesso", external_id=user.external_id)


# ---------------------------------------------------------------------------
# /login/
# ---------------------------------------------------------------------------
@router.get("/login/", include_in_schema=False)
async def get_login_doc():
    return markdown_response(DOCS_DIR, "login.md")


@router.post(
    "/login/",
    response_model=TokenResponse,
    responses={401: {"description": "otp invalido ou expirado"}, 404: {"description": "usuario nao encontrado"}},
)
@limiter.limit(_settings.ratelimit_login)
async def login(
    request: Request, response: Response, payload: LoginRequest, db: DbSession
) -> TokenResponse:
    if not await db.get(User, payload.external_id):
        raise NotFound("usuario nao encontrado")
    await auth_service.consume_otp(db, payload.external_id, payload.otp)
    roles = await users_service.active_roles(db, payload.external_id)
    access = create_access_token(payload.external_id, roles)
    refresh = create_refresh_token(payload.external_id, roles)
    await db.commit()
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        external_id=payload.external_id,
        roles=roles,
    )


# ---------------------------------------------------------------------------
# /refresh/
# ---------------------------------------------------------------------------
@router.get("/refresh/", include_in_schema=False)
async def get_refresh_doc():
    return markdown_response(DOCS_DIR, "refresh.md")


@router.post(
    "/refresh/",
    response_model=TokenResponse,
    responses={401: {"description": "refresh_token invalido"}, 404: {"description": "usuario nao encontrado"}},
)
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenResponse:
    try:
        decoded = decode_token(payload.refresh_token, expected_type="refresh")
    except ValueError as exc:
        raise Unauthorized(str(exc)) from exc
    external_id = decoded["sub"]
    if not await db.get(User, external_id):
        raise NotFound("usuario nao encontrado")
    roles = await users_service.active_roles(db, external_id)
    return TokenResponse(
        access_token=create_access_token(external_id, roles),
        refresh_token=create_refresh_token(external_id, roles),
        external_id=external_id,
        roles=roles,
    )


# ---------------------------------------------------------------------------
# /.well-known/auth
# ---------------------------------------------------------------------------
@router.get("/.well-known/auth", response_model=DiscoveryResponse)
async def discovery(db: DbSession) -> DiscoveryResponse:
    settings = get_settings()
    roles_data: list[dict] = []
    for role in (await db.scalars(select(Role).order_by(Role.name))).all():
        incompatible = (
            await db.scalars(
                select(RoleIncompatibility.incompatible_with).where(
                    RoleIncompatibility.role_name == role.name
                )
            )
        ).all()
        roles_data.append(
            {
                "name": role.name,
                "is_staff": role.is_staff,
                "is_transitory": role.is_transitory,
                "transitions_to": role.transitions_to,
                "requires_role": role.requires_role,
                "incompatible_roles": list(incompatible),
                "description": role.description,
            }
        )

    return DiscoveryResponse(
        service=settings.app_name,
        version="0.3.0",
        jwt_algorithm=settings.jwt_algorithm,
        jwt_token_format=(
            "JWT (PyJWT). Header inclui kid. Payload: iss, sub, roles|scopes, type, iat, exp."
        ),
        available_roles=roles_data,
        endpoints={
            "config": "/config/",
            "check": "/check/",
            "register": "/register/",
            "otp_request": "/otp/request",
            "login": "/login/",
            "refresh": "/refresh/",
            "oauth_token": "/oauth/token",
            "oauth_clients": "/oauth/clients/",
            "roles_list": "/roles/list/",
            "roles_create": "/roles/",
            "user_roles_get": "/user/{external_id}/roles",
            "user_roles_patch": "/user/{external_id}/roles",
            "user_transition": "/user/{external_id}/transition",
            "healthz": "/healthz",
        },
    )
