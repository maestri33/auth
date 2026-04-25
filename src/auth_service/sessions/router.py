from __future__ import annotations

from fastapi import APIRouter, Depends, status

from auth_service.audit import service as audit_service
from auth_service.core.deps import DbSession, require_scopes
from auth_service.core.exceptions import NotFound
from auth_service.sessions import service as sessions_service
from auth_service.sessions.schemas import RevokeRequest, SessionListOut, SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get(
    "/{external_id}",
    response_model=SessionListOut,
    dependencies=[Depends(require_scopes("admin"))],
)
async def list_user_sessions(external_id: str, db: DbSession) -> SessionListOut:
    rows = await sessions_service.list_for_user(db, external_id, include_revoked=True)
    return SessionListOut(sessions=[SessionOut.model_validate(r) for r in rows])


@router.post(
    "/revoke/{jti}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_scopes("admin"))],
    responses={404: {"description": "sessao nao encontrada ou ja revogada"}},
)
async def revoke_session(jti: str, payload: RevokeRequest, db: DbSession) -> None:
    session = await sessions_service.get(db, jti)
    if not session:
        raise NotFound("sessao nao encontrada")
    revoked = await sessions_service.revoke(db, jti, reason=payload.reason)
    if not revoked:
        raise NotFound("sessao ja revogada")
    await audit_service.record(
        db,
        action="session.revoked",
        target_type="session",
        target_id=jti,
        metadata={"external_id": session.external_id, "reason": payload.reason},
    )
    await db.commit()


@router.post(
    "/revoke-all/{external_id}",
    dependencies=[Depends(require_scopes("admin"))],
)
async def revoke_all(external_id: str, payload: RevokeRequest, db: DbSession) -> dict:
    n = await sessions_service.revoke_user_sessions(db, external_id, reason=payload.reason)
    if n:
        await audit_service.record(
            db,
            action="session.revoked_all",
            target_type="user",
            target_id=external_id,
            metadata={"reason": payload.reason, "count": n},
        )
    await db.commit()
    return {"revoked": n}
