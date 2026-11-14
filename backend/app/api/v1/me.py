from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AuthServiceDep, CurrentDep, DbDep
from app.api.v1.auth import me_response
from app.schemas.auth import (
    ChangePasswordRequest,
    MeResponse,
    MessageResponse,
    UpdateProfileRequest,
)

router = APIRouter(prefix="/me", tags=["me"])


@router.patch("")
async def update_profile(body: UpdateProfileRequest, ctx: CurrentDep, db: DbDep) -> MeResponse:
    ctx.user.full_name = body.full_name
    await db.commit()
    return me_response(ctx)


@router.post("/password")
async def change_password(
    body: ChangePasswordRequest, ctx: CurrentDep, service: AuthServiceDep
) -> MessageResponse:
    await service.change_password(
        user=ctx.user,
        workspace_id=ctx.workspace.id,
        current_password=body.current_password,
        new_password=body.new_password,
        keep_family=ctx.family_id,
    )
    return MessageResponse(message="Password updated. Other devices have been signed out.")
