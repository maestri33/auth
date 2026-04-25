from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from auth_service.audit import service as audit_service
from auth_service.audit.schemas import AuditEventOut, AuditListOut
from auth_service.core.deps import DbSession, require_scopes

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "/events",
    response_model=AuditListOut,
    dependencies=[Depends(require_scopes("admin"))],
)
async def list_events(
    db: DbSession,
    actor_id: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    target_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditListOut:
    rows = await audit_service.query(
        db,
        actor_id=actor_id,
        action=action,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )
    return AuditListOut(
        events=[AuditEventOut.model_validate(r) for r in rows],
        limit=limit,
        offset=offset,
    )
