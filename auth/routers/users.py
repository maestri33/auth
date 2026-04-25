from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.database import get_db
from auth.docs import DOCS_DIR, markdown_response
from auth.models import Role, User
from auth.schemas import (
    RoleCreate,
    RoleOut,
    RolePatch,
    TransitionRequest,
    UserRolesOut,
)
from auth.services import (
    active_roles,
    create_role,
    role_to_dict,
    set_user_role,
    transition_user_role,
)

router = APIRouter(tags=["users"])


# ---------------------------------------------------------------------------
# /roles/
# ---------------------------------------------------------------------------
@router.get("/roles/")
def get_roles_doc():
    return markdown_response(DOCS_DIR, "roles.md")


@router.get("/roles/list/")
def list_roles(db: Session = Depends(get_db)):
    roles = [role_to_dict(db, role) for role in db.scalars(select(Role).order_by(Role.name)).all()]
    return {"roles": roles}


@router.post("/roles/", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def post_role(payload: RoleCreate, db: Session = Depends(get_db)):
    role = create_role(db, payload)
    return role_to_dict(db, role)


# ---------------------------------------------------------------------------
# /user/
# ---------------------------------------------------------------------------
@router.get("/user/transition")
def get_transition_doc():
    return markdown_response(DOCS_DIR, "transition.md")


@router.get("/user/{external_id}/roles", response_model=UserRolesOut)
def get_user_roles(external_id: str, db: Session = Depends(get_db)) -> UserRolesOut:
    if not db.get(User, external_id):
        raise HTTPException(status_code=404, detail="usuario nao encontrado")
    return UserRolesOut(external_id=external_id, roles=active_roles(db, external_id))


@router.patch("/user/{external_id}/roles", response_model=UserRolesOut)
def patch_user_role(external_id: str, payload: RolePatch, db: Session = Depends(get_db)) -> UserRolesOut:
    set_user_role(db, external_id, payload.role, payload.enabled)
    db.commit()
    return UserRolesOut(external_id=external_id, roles=active_roles(db, external_id))


@router.post("/user/{external_id}/transition", response_model=UserRolesOut)
def transition(external_id: str, payload: TransitionRequest, db: Session = Depends(get_db)) -> UserRolesOut:
    target = transition_user_role(db, external_id, payload.role)
    db.commit()
    return UserRolesOut(external_id=external_id, roles=active_roles(db, external_id))
