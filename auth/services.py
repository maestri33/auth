from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.config import get_settings
from auth.docs import NOTIFY_DIR, read_markdown
from auth.models import AppConfig, OtpChallenge, Role, RoleIncompatibility, User, UserRole
from auth.notify_client import NotifyClient
from auth.schemas import RoleCreate
from auth.security import generate_otp, hash_otp, verify_otp


DEFAULT_ROLES = [
    RoleCreate(name="student"),
    RoleCreate(name="promotor"),
    RoleCreate(name="lead", is_transitory=True, transitions_to="student", incompatible_roles=["student"]),
    RoleCreate(name="candidato", is_transitory=True, transitions_to="promotor", incompatible_roles=["promotor"]),
    RoleCreate(name="coordenador", is_staff=True, requires_role="promotor"),
]


def get_config_value(db: Session, key: str, fallback: str) -> str:
    item = db.get(AppConfig, key)
    return item.value if item else fallback


def set_config_value(db: Session, key: str, value: str) -> None:
    item = db.get(AppConfig, key)
    if item:
        item.value = value
    else:
        db.add(AppConfig(key=key, value=value))


def notify_client_from_db(db: Session) -> NotifyClient:
    settings = get_settings()
    return NotifyClient(
        get_config_value(db, "notify_base_url", settings.notify_base_url),
        get_config_value(db, "notify_cli", settings.notify_cli),
        settings.notify_timeout_seconds,
    )


def seed_defaults(db: Session) -> None:
    for role in DEFAULT_ROLES:
        if not db.get(Role, role.name):
            db.add(
                Role(
                    name=role.name,
                    is_staff=role.is_staff,
                    is_transitory=role.is_transitory,
                    transitions_to=role.transitions_to,
                    requires_role=role.requires_role,
                    description=role.description,
                )
            )
    db.flush()
    for role in DEFAULT_ROLES:
        for incompatible in role.incompatible_roles:
            exists = db.scalar(
                select(RoleIncompatibility).where(
                    RoleIncompatibility.role_name == role.name,
                    RoleIncompatibility.incompatible_with == incompatible,
                )
            )
            reverse_exists = db.scalar(
                select(RoleIncompatibility).where(
                    RoleIncompatibility.role_name == incompatible,
                    RoleIncompatibility.incompatible_with == role.name,
                )
            )
            if not exists:
                db.add(RoleIncompatibility(role_name=role.name, incompatible_with=incompatible))
            if not reverse_exists:
                db.add(RoleIncompatibility(role_name=incompatible, incompatible_with=role.name))
    db.commit()


def create_role(db: Session, payload: RoleCreate) -> Role:
    if db.get(Role, payload.name):
        raise HTTPException(status_code=409, detail="role ja existe")
    ensure_referenced_roles(db, payload)
    role = Role(
        name=payload.name,
        is_staff=payload.is_staff,
        is_transitory=payload.is_transitory,
        transitions_to=payload.transitions_to,
        requires_role=payload.requires_role,
        description=payload.description,
    )
    db.add(role)
    db.flush()
    for incompatible in payload.incompatible_roles:
        db.add(RoleIncompatibility(role_name=payload.name, incompatible_with=incompatible))
        db.add(RoleIncompatibility(role_name=incompatible, incompatible_with=payload.name))
    db.commit()
    db.refresh(role)
    return role


def ensure_referenced_roles(db: Session, payload: RoleCreate) -> None:
    refs = [payload.transitions_to, payload.requires_role, *payload.incompatible_roles]
    missing = [name for name in refs if name and not db.get(Role, name)]
    if missing:
        raise HTTPException(status_code=400, detail=f"roles referenciadas nao existem: {', '.join(missing)}")


def role_to_dict(db: Session, role: Role) -> dict:
    incompatible = db.scalars(
        select(RoleIncompatibility.incompatible_with).where(RoleIncompatibility.role_name == role.name)
    ).all()
    return {
        "name": role.name,
        "is_staff": role.is_staff,
        "is_transitory": role.is_transitory,
        "transitions_to": role.transitions_to,
        "requires_role": role.requires_role,
        "incompatible_roles": incompatible,
        "description": role.description,
    }


def active_roles(db: Session, external_id: str) -> list[str]:
    return db.scalars(
        select(UserRole.role_name).where(UserRole.external_id == external_id, UserRole.enabled.is_(True))
    ).all()


def ensure_role_can_be_enabled(db: Session, external_id: str, role_name: str) -> None:
    role = db.get(Role, role_name)
    if not role:
        raise HTTPException(status_code=404, detail="role nao encontrada")
    roles = set(active_roles(db, external_id))
    if role.requires_role and role.requires_role not in roles:
        raise HTTPException(status_code=400, detail=f"role {role_name} exige role {role.requires_role}")
    incompatible = set(
        db.scalars(
            select(RoleIncompatibility.incompatible_with).where(RoleIncompatibility.role_name == role_name)
        ).all()
    )
    conflicts = sorted(incompatible.intersection(roles))
    if conflicts:
        raise HTTPException(status_code=400, detail=f"role incompativel com: {', '.join(conflicts)}")


def set_user_role(db: Session, external_id: str, role_name: str, enabled: bool = True) -> None:
    if not db.get(User, external_id):
        raise HTTPException(status_code=404, detail="usuario nao encontrado")
    if enabled:
        ensure_role_can_be_enabled(db, external_id, role_name)
    user_role = db.scalar(select(UserRole).where(UserRole.external_id == external_id, UserRole.role_name == role_name))
    if user_role:
        user_role.enabled = enabled
    else:
        db.add(UserRole(external_id=external_id, role_name=role_name, enabled=enabled))
        db.flush()


def transition_user_role(db: Session, external_id: str, role_name: str) -> str:
    """Desativa uma role transitoria e ativa sua transitions_to. Retorna a role destino."""
    if not db.get(User, external_id):
        raise HTTPException(status_code=404, detail="usuario nao encontrado")

    role = db.get(Role, role_name)
    if not role:
        raise HTTPException(status_code=404, detail="role nao encontrada")
    if not role.is_transitory:
        raise HTTPException(status_code=400, detail=f"role {role_name} nao e transitoria")
    if not role.transitions_to:
        raise HTTPException(status_code=400, detail=f"role {role_name} nao tem transitions_to definido")

    active = set(active_roles(db, external_id))
    if role_name not in active:
        raise HTTPException(status_code=400, detail=f"usuario nao possui a role {role_name} ativa")

    target = role.transitions_to
    # Desativa a transitoria
    user_role = db.scalar(
        select(UserRole).where(UserRole.external_id == external_id, UserRole.role_name == role_name)
    )
    user_role.enabled = False
    db.flush()

    # Ativa a role destino (valida incompatibilidades)
    set_user_role(db, external_id, target, enabled=True)
    return target


def create_otp(db: Session, external_id: str) -> str:
    settings = get_settings()
    otp = generate_otp()
    db.add(
        OtpChallenge(
            external_id=external_id,
            otp_hash=hash_otp(otp),
            expires_at=datetime.utcnow() + timedelta(minutes=settings.otp_ttl_minutes),
        )
    )
    return otp


def consume_otp(db: Session, external_id: str, otp: str) -> None:
    challenge = db.scalar(
        select(OtpChallenge)
        .where(
            OtpChallenge.external_id == external_id,
            OtpChallenge.consumed_at.is_(None),
            OtpChallenge.expires_at > datetime.utcnow(),
        )
        .order_by(OtpChallenge.created_at.desc())
    )
    if not challenge or not verify_otp(otp, challenge.otp_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="otp invalido ou expirado")
    challenge.consumed_at = datetime.utcnow()


def build_otp_message(otp: str) -> str:
    template = read_markdown(NOTIFY_DIR, "otp.md")
    return template.replace("{{ otp }}", otp)


def create_local_user(db: Session, phone: str, role_name: str, external_id: str | None = None) -> User:
    external_id = external_id or str(uuid4())
    user = User(external_id=external_id, phone=phone)
    db.add(user)
    db.flush()
    set_user_role(db, external_id, role_name, enabled=True)
    return user
