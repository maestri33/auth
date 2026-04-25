from __future__ import annotations

from fastapi import APIRouter, Depends

from auth_service.core.deps import DbSession, require_scopes
from auth_service.core.docs import DOCS_DIR, markdown_response
from auth_service.core.exceptions import NotFound
from auth_service.users import service as users_service
from auth_service.users.models import User
from auth_service.users.schemas import RolePatch, TransitionRequest, UserRolesOut

router = APIRouter(prefix="/user", tags=["users"])


@router.get("/transition", include_in_schema=False)
async def get_transition_doc():
    return markdown_response(DOCS_DIR, "transition.md")


@router.get(
    "/{external_id}/roles",
    response_model=UserRolesOut,
    responses={404: {"description": "usuario nao encontrado"}},
)
async def get_user_roles(external_id: str, db: DbSession) -> UserRolesOut:
    if not await db.get(User, external_id):
        raise NotFound("usuario nao encontrado")
    return UserRolesOut(external_id=external_id, roles=await users_service.active_roles(db, external_id))


@router.patch(
    "/{external_id}/roles",
    response_model=UserRolesOut,
    dependencies=[Depends(require_scopes("admin"))],
)
async def patch_user_role(external_id: str, payload: RolePatch, db: DbSession) -> UserRolesOut:
    await users_service.set_user_role(db, external_id, payload.role, payload.enabled)
    await db.commit()
    return UserRolesOut(external_id=external_id, roles=await users_service.active_roles(db, external_id))


@router.post(
    "/{external_id}/transition",
    response_model=UserRolesOut,
    dependencies=[Depends(require_scopes("admin"))],
)
async def transition(external_id: str, payload: TransitionRequest, db: DbSession) -> UserRolesOut:
    await users_service.transition_user_role(db, external_id, payload.role)
    await db.commit()
    return UserRolesOut(external_id=external_id, roles=await users_service.active_roles(db, external_id))
