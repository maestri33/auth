from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.core.exceptions import BadRequest, Conflict
from auth_service.roles.models import Role, RoleIncompatibility
from auth_service.roles.schemas import RoleCreate, RoleOut

DEFAULT_ROLES: list[RoleCreate] = [
    RoleCreate(name="student"),
    RoleCreate(name="promotor"),
    RoleCreate(name="lead", is_transitory=True, transitions_to="student", incompatible_roles=["student"]),
    RoleCreate(
        name="candidato", is_transitory=True, transitions_to="promotor", incompatible_roles=["promotor"]
    ),
    RoleCreate(name="coordenador", is_staff=True, requires_role="promotor"),
]


async def seed_defaults(db: AsyncSession) -> None:
    for role in DEFAULT_ROLES:
        if not await db.get(Role, role.name):
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
    await db.flush()
    for role in DEFAULT_ROLES:
        for incompatible in role.incompatible_roles:
            for a, b in [(role.name, incompatible), (incompatible, role.name)]:
                exists = await db.scalar(
                    select(RoleIncompatibility).where(
                        RoleIncompatibility.role_name == a,
                        RoleIncompatibility.incompatible_with == b,
                    )
                )
                if not exists:
                    db.add(RoleIncompatibility(role_name=a, incompatible_with=b))
    await db.commit()


async def _ensure_referenced_roles(db: AsyncSession, payload: RoleCreate) -> None:
    refs = [payload.transitions_to, payload.requires_role, *payload.incompatible_roles]
    missing: list[str] = []
    for name in refs:
        if name and not await db.get(Role, name):
            missing.append(name)
    if missing:
        raise BadRequest(f"roles referenciadas nao existem: {', '.join(missing)}")


async def create_role(db: AsyncSession, payload: RoleCreate) -> Role:
    if await db.get(Role, payload.name):
        raise Conflict("role ja existe")
    await _ensure_referenced_roles(db, payload)
    role = Role(
        name=payload.name,
        is_staff=payload.is_staff,
        is_transitory=payload.is_transitory,
        transitions_to=payload.transitions_to,
        requires_role=payload.requires_role,
        description=payload.description,
    )
    db.add(role)
    await db.flush()
    for incompatible in payload.incompatible_roles:
        db.add(RoleIncompatibility(role_name=payload.name, incompatible_with=incompatible))
        db.add(RoleIncompatibility(role_name=incompatible, incompatible_with=payload.name))
    await db.commit()
    await db.refresh(role)
    return role


async def list_roles(db: AsyncSession) -> list[RoleOut]:
    roles = (await db.scalars(select(Role).order_by(Role.name))).all()
    out: list[RoleOut] = []
    for role in roles:
        incompatible = (
            await db.scalars(
                select(RoleIncompatibility.incompatible_with).where(
                    RoleIncompatibility.role_name == role.name
                )
            )
        ).all()
        out.append(
            RoleOut(
                name=role.name,
                is_staff=role.is_staff,
                is_transitory=role.is_transitory,
                transitions_to=role.transitions_to,
                requires_role=role.requires_role,
                incompatible_roles=list(incompatible),
                description=role.description,
            )
        )
    return out


async def role_with_incompat(db: AsyncSession, role: Role) -> RoleOut:
    incompatible = (
        await db.scalars(
            select(RoleIncompatibility.incompatible_with).where(RoleIncompatibility.role_name == role.name)
        )
    ).all()
    return RoleOut(
        name=role.name,
        is_staff=role.is_staff,
        is_transitory=role.is_transitory,
        transitions_to=role.transitions_to,
        requires_role=role.requires_role,
        incompatible_roles=list(incompatible),
        description=role.description,
    )
