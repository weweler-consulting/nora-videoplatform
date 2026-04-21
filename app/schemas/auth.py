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


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    is_admin: bool


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
