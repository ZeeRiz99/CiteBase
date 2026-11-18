from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.cookies import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
    set_csrf_cookie,
)
from app.api.deps import AuthServiceDep, ClientDep, CurrentContext, CurrentDep, SettingsDep
from app.core.config import Settings
from app.core.errors import NotAuthenticated, error_body
from app.core.security import decode_access_token
from app.schemas.auth import (
    CsrfResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenRequest,
    UserOut,
    WorkspaceOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def me_response(ctx: CurrentContext, settings: Settings) -> MeResponse:
    return MeResponse(
        user=UserOut(
            id=ctx.user.id,
            email=ctx.user.email,
            full_name=ctx.user.full_name,
            email_verified=ctx.user.email_verified_at is not None,
        ),
        workspace=WorkspaceOut(
            id=ctx.workspace.id, name=ctx.workspace.name, slug=ctx.workspace.slug
        ),
        role=ctx.role,
        email_verification_required=settings.require_verified_email,
    )


@router.get("/csrf")
async def csrf(response: Response, settings: SettingsDep) -> CsrfResponse:
    return CsrfResponse(csrf_token=set_csrf_cookie(response, settings))


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    client: ClientDep,
) -> MessageResponse:
    tokens = await service.register(
        full_name=body.full_name,
        email=str(body.email),
        password=body.password,
        workspace_name=body.workspace_name,
        client=client,
    )
    set_auth_cookies(response, settings, tokens)
    return MessageResponse(message="Account created. Check your email to confirm your address.")


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    client: ClientDep,
) -> MessageResponse:
    tokens = await service.login(email=str(body.email), password=body.password, client=client)
    set_auth_cookies(response, settings, tokens)
    return MessageResponse(message="Signed in.")


@router.post("/refresh", response_model=MessageResponse)
async def refresh(
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    client: ClientDep,
) -> MessageResponse | JSONResponse:
    try:
        tokens = await service.refresh(
            refresh_token=request.cookies.get(REFRESH_COOKIE), client=client
        )
    except NotAuthenticated as exc:
        failed = JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, getattr(request.state, "request_id", None)),
        )
        # A dead session clears its cookies (incl. the marker) so the UI cannot loop. A tab race
        # keeps them: the other tab's request already stored fresh ones in the shared jar.
        if exc.code != "refresh_race":
            clear_auth_cookies(failed)
        return failed
    set_auth_cookies(response, settings, tokens)
    return MessageResponse(message="Session refreshed.")


@router.post("/logout")
async def logout(
    request: Request, response: Response, service: AuthServiceDep, settings: SettingsDep
) -> MessageResponse:
    access = request.cookies.get(ACCESS_COOKIE)
    claims = decode_access_token(settings, access) if access else None
    await service.logout(
        session_id=claims.session_id if claims else None,
        refresh_token=request.cookies.get(REFRESH_COOKIE),
    )
    clear_auth_cookies(response)
    return MessageResponse(message="Signed out.")


@router.post("/verify-email")
async def verify_email(body: TokenRequest, service: AuthServiceDep) -> MessageResponse:
    await service.verify_email(token=body.token)
    return MessageResponse(message="Email confirmed.")


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(ctx: CurrentDep, service: AuthServiceDep) -> MessageResponse:
    await service.resend_verification(user=ctx.user)
    return MessageResponse(message="If your email is not confirmed yet, a new link is on its way.")


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    body: ForgotPasswordRequest, service: AuthServiceDep, client: ClientDep
) -> MessageResponse:
    await service.forgot_password(email=str(body.email), client=client)
    return MessageResponse(
        message="If an account exists for that email, a reset link is on its way."
    )


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest, response: Response, service: AuthServiceDep, client: ClientDep
) -> MessageResponse:
    await service.reset_password(token=body.token, password=body.password, client=client)
    clear_auth_cookies(response)
    return MessageResponse(message="Password updated. Sign in with your new password.")


@router.get("/me")
async def me(ctx: CurrentDep, settings: SettingsDep) -> MeResponse:
    return me_response(ctx, settings)


@router.post("/confirm-email-change")
async def confirm_email_change(
    body: TokenRequest, response: Response, service: AuthServiceDep, client: ClientDep
) -> MessageResponse:
    new_email = await service.confirm_email_change(token=body.token, client=client)
    clear_auth_cookies(response)  # every session ended: sign in again with the new address
    return MessageResponse(message=f"Your sign-in email is now {new_email}. Sign in again.")
