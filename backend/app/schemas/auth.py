from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.models import Role

Password = Annotated[str, Field(min_length=10, max_length=128)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Token = Annotated[str, Field(min_length=16, max_length=200)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(_Strict):
    full_name: Name
    email: EmailStr
    password: Password
    workspace_name: Name | None = None


class LoginRequest(_Strict):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class TokenRequest(_Strict):
    token: Token


class ForgotPasswordRequest(_Strict):
    email: EmailStr


class ResetPasswordRequest(_Strict):
    token: Token
    password: Password


class ChangePasswordRequest(_Strict):
    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    new_password: Password


class UpdateProfileRequest(_Strict):
    full_name: Name


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    email_verified: bool


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class MeResponse(BaseModel):
    user: UserOut
    workspace: WorkspaceOut
    role: Role
    # True when uploads and invitations wait for a confirmed email (REQUIRE_VERIFIED_EMAIL).
    email_verification_required: bool = True


class ChangeEmailRequest(_Strict):
    new_email: EmailStr
    current_password: Annotated[str, Field(min_length=1, max_length=128)]


class MessageResponse(BaseModel):
    message: str


class CsrfResponse(BaseModel):
    csrf_token: str
