from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ImpersonatorInfo(BaseModel):
    id: str
    name: str
    email: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    is_admin: bool
    # Set when the current session is an admin viewing the platform "aus
    # Kundensicht". `impersonator` describes the admin behind the session.
    impersonated: bool = False
    impersonator: Optional[ImpersonatorInfo] = None


class InviteInfoResponse(BaseModel):
    email: str
    name: str
    course_titles: list[str]


class AcceptInviteRequest(BaseModel):
    token: str
    password: str = Field(min_length=8)
    accept_terms: bool


class ConfirmEmailChangeRequest(BaseModel):
    token: str
