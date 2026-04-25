from __future__ import annotations

from fastapi import APIRouter, Depends, status

from auth_service.audit import service as audit_service
from auth_service.core.deps import DbSession, require_scopes
from auth_service.core.docs import DOCS_DIR, markdown_response
from auth_service.roles import service as roles_service
from auth_service.roles.schemas import RoleCreate, RoleListOut, RoleOut

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/", include_in_schema=False)
async def get_roles_doc():
    return markdown_response(DOCS_DIR, "roles.md")


@router.get("/list/", response_model=RoleListOut)
async def list_roles(db: DbSession) -> RoleListOut:
    return RoleListOut(roles=await roles_service.list_roles(db))


@router.post(
    "/",
    response_model=RoleOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "role ja existe"},
        400: {"description": "role referenciada inexistente"},
    },
)
async def create_role(
    payload: RoleCreate,
    db: DbSession,
    actor: dict = Depends(require_scopes("admin")),
) -> RoleOut:
    role = await roles_service.create_role(db, payload)
    await audit_service.record(
        db,
        action="role.created",
        actor_type="client",
        actor_id=actor.get("sub"),
        target_type="role",
        target_id=payload.name,
        metadata={
            "is_staff": payload.is_staff,
            "is_transitory": payload.is_transitory,
            "transitions_to": payload.transitions_to,
            "requires_role": payload.requires_role,
            "incompatible_roles": payload.incompatible_roles,
        },
    )
    await db.commit()
    return await roles_service.role_with_incompat(db, role)
