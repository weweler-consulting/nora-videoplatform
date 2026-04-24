import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_email_change_token,
    decode_email_change_token,
    get_current_user,
)
from app.core.email import send_invite_email, send_password_reset_email, send_email_change_verification
from app.core.ratelimit import limiter
from app.core.time import utc_now
from app.models.user import User
from app.models.course import Enrollment
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    InviteInfoResponse,
    AcceptInviteRequest,
    ConfirmEmailChangeRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user and user.invite_token and not user.invite_accepted_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Einladung noch nicht bestätigt. Bitte prüfe dein E-Mail-Postfach.",
        )
    if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/hour")
async def register(request: Request, data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(email=data.email, name=data.name, hashed_password=hash_password(data.password))
    db.add(user)
    await db.flush()
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(id=user.id, email=user.email, name=user.name, is_admin=user.is_admin)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None


@router.put("/password")
async def change_password(data: ChangePasswordRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Aktuelles Passwort ist falsch")
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Passwort muss mindestens 8 Zeichen haben")
    user.hashed_password = hash_password(data.new_password)
    return {"ok": True}


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


@router.post("/forgot-password")
@limiter.limit("5/hour")
async def forgot_password(request: Request, data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(User)
            .where(User.email == data.email)
            .options(selectinload(User.enrollments).selectinload(Enrollment.course))
        )
        user = result.unique().scalar_one_or_none()
        if not user:
            return {"ok": True}
        base = str(request.base_url).rstrip("/").replace("http://", "https://", 1)
        if not user.invite_accepted_at:
            # User has never accepted their invite. A reset link is useless — they
            # need to accept the invite (which also sets the password). Refresh
            # the invite token if expired and resend the invite email.
            if not user.invite_token or not user.invite_token_expires or user.invite_token_expires < utc_now():
                user.invite_token = secrets.token_urlsafe(32)
                user.invite_token_expires = utc_now() + timedelta(days=7)
                await db.flush()
            invite_url = f"{base}/accept-invite?token={user.invite_token}"
            course_title = next(
                (e.course.title for e in user.enrollments if e.course is not None),
                "Kurs",
            )
            try:
                send_invite_email(user.email, user.name, course_title, invite_url)
            except Exception as e:
                logger.error(f"Failed to resend invite email on forgot-password: {e}")
            return {"ok": True}
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = utc_now() + timedelta(hours=1)
        await db.flush()
        reset_url = f"{base}/reset-password?token={token}"
        try:
            send_password_reset_email(user.email, user.name, reset_url)
        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
    except Exception as e:
        logger.error(f"Forgot password error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}


@router.post("/reset-password")
@limiter.limit("10/hour")
async def reset_password(request: Request, data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Passwort muss mindestens 8 Zeichen haben")
    result = await db.execute(select(User).where(User.reset_token == data.token))
    user = result.scalar_one_or_none()
    if not user or not user.reset_token_expires or user.reset_token_expires < utc_now():
        raise HTTPException(status_code=400, detail="Link ist ungültig oder abgelaufen")
    user.hashed_password = hash_password(data.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    return {"ok": True}


@router.put("/profile")
async def update_profile(
    request: Request,
    data: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.name is not None:
        user.name = data.name

    email_change_pending = False
    pending_email: Optional[str] = None
    if data.email is not None and data.email != user.email:
        existing = await db.execute(select(User).where(User.email == data.email, User.id != user.id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="E-Mail wird bereits verwendet")
        token = create_email_change_token(user.id, data.email)
        base = str(request.base_url).rstrip("/").replace("http://", "https://", 1)
        confirm_url = f"{base}/confirm-email-change?token={token}"
        try:
            send_email_change_verification(data.email, user.name, confirm_url)
        except Exception as e:
            logger.error(f"Failed to send email-change verification: {e}")
            raise HTTPException(status_code=500, detail="Konnte Bestätigungs-Mail nicht verschicken.")
        email_change_pending = True
        pending_email = data.email

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_admin": user.is_admin,
        "email_change_pending": email_change_pending,
        "pending_email": pending_email,
    }


@router.post("/confirm-email-change")
@limiter.limit("10/hour")
async def confirm_email_change(
    request: Request,
    data: ConfirmEmailChangeRequest,
    db: AsyncSession = Depends(get_db),
):
    decoded = decode_email_change_token(data.token)
    if not decoded:
        raise HTTPException(status_code=400, detail="Bestätigungslink ist ungültig oder abgelaufen.")
    user_id, new_email = decoded

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Nutzer nicht gefunden.")

    existing = await db.execute(select(User).where(User.email == new_email, User.id != user.id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Die E-Mail wird bereits verwendet.")

    user.email = new_email
    return {"ok": True, "email": new_email}


@router.get("/invite/{token}", response_model=InviteInfoResponse)
async def get_invite_info(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .where(User.invite_token == token)
        .options(selectinload(User.enrollments).selectinload(Enrollment.course))
    )
    user = result.unique().scalar_one_or_none()
    if not user or not user.invite_token_expires or user.invite_token_expires < utc_now():
        raise HTTPException(status_code=400, detail="Einladungslink ist ungültig oder abgelaufen.")
    course_titles = [e.course.title for e in user.enrollments if e.course is not None]
    return InviteInfoResponse(email=user.email, name=user.name, course_titles=course_titles)


@router.post("/invite/accept", response_model=TokenResponse)
@limiter.limit("10/hour")
async def accept_invite(request: Request, data: AcceptInviteRequest, db: AsyncSession = Depends(get_db)):
    if not data.accept_terms:
        raise HTTPException(status_code=400, detail="AGB und Datenschutz müssen akzeptiert werden.")
    result = await db.execute(select(User).where(User.invite_token == data.token))
    user = result.scalar_one_or_none()
    if not user or not user.invite_token_expires or user.invite_token_expires < utc_now():
        raise HTTPException(status_code=400, detail="Einladungslink ist ungültig oder abgelaufen.")
    now = utc_now()
    user.hashed_password = hash_password(data.password)
    user.invite_token = None
    user.invite_token_expires = None
    user.invite_accepted_at = now
    user.terms_accepted_at = now
    user.is_active = True
    await db.flush()
    return TokenResponse(access_token=create_access_token(user.id))
