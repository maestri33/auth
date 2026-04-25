from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import uuid4

from auth.database import get_db
from auth.docs import DOCS_DIR, markdown_response
from auth.models import Role, RoleIncompatibility, User
from auth.schemas import (
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
from auth.security import create_access_token, create_refresh_token, decode_refresh_token
from auth.services import (
    active_roles,
    build_otp_message,
    consume_otp,
    create_otp,
    get_config_value,
    notify_client_from_db,
    set_user_role,
)

router = APIRouter(tags=["auth"])
INITIAL_ROLES = {"lead", "candidato"}


# ---------------------------------------------------------------------------
# /check/
# ---------------------------------------------------------------------------
@router.get("/check/")
def get_check_doc():
    return markdown_response(DOCS_DIR, "check.md")


@router.post("/check/", response_model=CheckResponse)
async def check(payload: CheckRequest, db: Session = Depends(get_db)) -> CheckResponse:
    notify = notify_client_from_db(db)
    recipient = await notify.check_recipient(payload.phone)
    local_user = db.scalar(select(User).where(User.phone == payload.phone))
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
@router.get("/register/")
def get_register_doc():
    return markdown_response(DOCS_DIR, "register.md")


@router.post(
    "/register/",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    if not db.get(Role, payload.role):
        raise HTTPException(status_code=404, detail="role nao encontrada")
    if payload.role not in INITIAL_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"role de registro deve ser uma das fases iniciais: {', '.join(sorted(INITIAL_ROLES))}",
        )
    if db.scalar(select(User).where(User.phone == payload.phone)):
        raise HTTPException(status_code=409, detail="telefone ja cadastrado")

    notify = notify_client_from_db(db)
    await notify.check_recipient(payload.phone)

    external_id = str(uuid4())
    db.add(User(external_id=external_id, phone=payload.phone))
    db.flush()

    set_user_role(db, external_id, payload.role, enabled=True)
    await notify.create_recipient(external_id, payload.phone)
    db.commit()

    return RegisterResponse(
        status="ok",
        message="cadastro realizado com sucesso",
        external_id=external_id,
        role=payload.role,
    )


# ---------------------------------------------------------------------------
# /otp/request
# ---------------------------------------------------------------------------
@router.get("/otp/request")
def get_otp_doc():
    return markdown_response(DOCS_DIR, "otp-request.md")


@router.post("/otp/request", response_model=OtpResponse)
async def otp_request(payload: OtpRequest, db: Session = Depends(get_db)) -> OtpResponse:
    if not payload.external_id and not payload.phone:
        raise HTTPException(status_code=400, detail="informe external_id ou phone")

    user = None
    if payload.external_id:
        user = db.get(User, payload.external_id)
    elif payload.phone:
        user = db.scalar(select(User).where(User.phone == payload.phone))

    if not user:
        raise HTTPException(status_code=404, detail="usuario nao encontrado")

    notify = notify_client_from_db(db)
    otp = create_otp(db, user.external_id)
    await notify.send_notification(user.external_id, build_otp_message(otp))
    db.commit()

    return OtpResponse(
        status="ok",
        message="otp enviado com sucesso",
        external_id=user.external_id,
    )


# ---------------------------------------------------------------------------
# /.well-known/auth
# ---------------------------------------------------------------------------
@router.get("/.well-known/auth", response_model=DiscoveryResponse)
def discovery(db: Session = Depends(get_db)) -> DiscoveryResponse:
    from auth.config import get_settings

    settings = get_settings()
    roles_data = []
    for role in db.scalars(select(Role).order_by(Role.name)).all():
        incompatible = db.scalars(
            select(RoleIncompatibility.incompatible_with).where(
                RoleIncompatibility.role_name == role.name
            )
        ).all()
        roles_data.append({
            "name": role.name,
            "is_staff": role.is_staff,
            "is_transitory": role.is_transitory,
            "transitions_to": role.transitions_to,
            "requires_role": role.requires_role,
            "incompatible_roles": incompatible,
            "description": role.description,
        })

    return DiscoveryResponse(
        service=settings.app_name,
        version="0.1.0",
        jwt_algorithm=settings.jwt_algorithm,
        jwt_token_format="Header: {alg, typ}. Payload: {sub, roles, type, exp}. Signature: HMAC-SHA256",
        available_roles=roles_data,
        endpoints={
            "config": "/config/",
            "check": "/check/",
            "register": "/register/",
            "otp_request": "/otp/request",
            "login": "/login/",
            "refresh": "/refresh/",
            "roles_list": "/roles/list/",
            "roles_create": "/roles/",
            "user_roles_get": "/user/{external_id}/roles",
            "user_roles_patch": "/user/{external_id}/roles",
            "user_transition": "/user/{external_id}/transition",
        },
    )


# ---------------------------------------------------------------------------
# /login/
# ---------------------------------------------------------------------------
@router.get("/login/")
def get_login_doc():
    return markdown_response(DOCS_DIR, "login.md")


@router.post("/login/", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if not db.get(User, payload.external_id):
        raise HTTPException(status_code=404, detail="usuario nao encontrado")
    consume_otp(db, payload.external_id, payload.otp)
    roles = active_roles(db, payload.external_id)
    access_token = create_access_token(payload.external_id, roles)
    refresh_token = create_refresh_token(payload.external_id, roles)
    db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        external_id=payload.external_id,
        roles=roles,
    )


# ---------------------------------------------------------------------------
# /refresh/
# ---------------------------------------------------------------------------
@router.get("/refresh/")
def get_refresh_doc():
    return markdown_response(DOCS_DIR, "refresh.md")


@router.post("/refresh/", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        external_id = decode_refresh_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if not db.get(User, external_id):
        raise HTTPException(status_code=404, detail="usuario nao encontrado")
    roles = active_roles(db, external_id)
    return TokenResponse(
        access_token=create_access_token(external_id, roles),
        refresh_token=create_refresh_token(external_id, roles),
        external_id=external_id,
        roles=roles,
    )
