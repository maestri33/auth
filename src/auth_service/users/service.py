from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.core.exceptions import BadRequest, NotFound
from auth_service.roles.models import Role, RoleIncompatibility
from auth_service.users.models import User, UserRole


async def active_roles(db: AsyncSession, external_id: str) -> list[str]:
    rows = await db.scalars(
        select(UserRole.role_name).where(
            UserRole.external_id == external_id, UserRole.enabled.is_(True)
        )
    )
    return list(rows.all())


async def ensure_role_can_be_enabled(db: AsyncSession, external_id: str, role_name: str) -> None:
    role = await db.get(Role, role_name)
    if not role:
        raise NotFound("role nao encontrada")
    roles = set(await active_roles(db, external_id))
    if role.requires_role and role.requires_role not in roles:
        raise BadRequest(f"role {role_name} exige role {role.requires_role}")
    incompatible_rows = await db.scalars(
        select(RoleIncompatibility.incompatible_with).where(RoleIncompatibility.role_name == role_name)
    )
    incompatible = set(incompatible_rows.all())
    conflicts = sorted(incompatible.intersection(roles))
    if conflicts:
        raise BadRequest(f"role incompativel com: {', '.join(conflicts)}")


async def set_user_role(db: AsyncSession, external_id: str, role_name: str, enabled: bool = True) -> None:
    if not await db.get(User, external_id):
        raise NotFound("usuario nao encontrado")
    if enabled:
        await ensure_role_can_be_enabled(db, external_id, role_name)
    user_role = await db.scalar(
        select(UserRole).where(UserRole.external_id == external_id, UserRole.role_name == role_name)
    )
    if user_role:
        user_role.enabled = enabled
    else:
        db.add(UserRole(external_id=external_id, role_name=role_name, enabled=enabled))
        await db.flush()


async def transition_user_role(db: AsyncSession, external_id: str, role_name: str) -> str:
    if not await db.get(User, external_id):
        raise NotFound("usuario nao encontrado")
    role = await db.get(Role, role_name)
    if not role:
        raise NotFound("role nao encontrada")
    if not role.is_transitory:
        raise BadRequest(f"role {role_name} nao e transitoria")
    if not role.transitions_to:
        raise BadRequest(f"role {role_name} nao tem transitions_to definido")

    active = set(await active_roles(db, external_id))
    if role_name not in active:
        raise BadRequest(f"usuario nao possui a role {role_name} ativa")

    target = role.transitions_to
    user_role = await db.scalar(
        select(UserRole).where(UserRole.external_id == external_id, UserRole.role_name == role_name)
    )
    user_role.enabled = False
    await db.flush()

    await set_user_role(db, external_id, target, enabled=True)
    return target


async def create_local_user(
    db: AsyncSession, phone: str, role_name: str, external_id: str | None = None
) -> User:
    external_id = external_id or str(uuid4())
    user = User(external_id=external_id, phone=phone)
    db.add(user)
    await db.flush()
    await set_user_role(db, external_id, role_name, enabled=True)
    return user
