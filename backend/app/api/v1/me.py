from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import AuthServiceDep, CurrentDep, DbDep, SettingsDep
from app.api.v1.auth import me_response
from app.schemas.auth import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    MeResponse,
    MessageResponse,
    UpdateProfileRequest,
)

router = APIRouter(prefix="/me", tags=["me"])


@router.patch("")
async def update_profile(
    body: UpdateProfileRequest, ctx: CurrentDep, db: DbDep, settings: SettingsDep
) -> MeResponse:
    ctx.user.full_name = body.full_name
    await db.commit()
    return me_response(ctx, settings)


@router.post("/email", status_code=status.HTTP_202_ACCEPTED)
async def request_email_change(
    body: ChangeEmailRequest, ctx: CurrentDep, service: AuthServiceDep
) -> MessageResponse:
    new_email = await service.request_email_change(
        user=ctx.user,
        workspace_id=ctx.workspace.id,
        new_email=str(body.new_email),
        password=body.current_password,
    )
    return MessageResponse(
        message=f"We sent a confirmation link to {new_email}. "
        "Your sign-in email changes once you open it."
    )


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
