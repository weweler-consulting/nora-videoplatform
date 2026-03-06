import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.auth import require_admin, hash_password
from app.models.user import User
from app.models.course import Enrollment, Course
from app.core.email import send_invite_email

logger = logging.getLogger(__name__)

router = APIRouter()


class UserWithEnrollments(BaseModel):
    id: str
    email: str
    name: str
    is_admin: bool
    is_active: bool = True
    enrollments: list[dict] = []


class InviteRequest(BaseModel):
    email: EmailStr
    name: str
    course_id: str
    password: str = "changeme123"
    send_email: bool = False


@router.get("/", response_model=list[UserWithEnrollments])
async def list_users(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .options(selectinload(User.enrollments).selectinload(Enrollment.course))
        .order_by(User.created_at.desc())
    )
    users = result.scalars().unique().all()
    return [
        UserWithEnrollments(
            id=u.id, email=u.email, name=u.name, is_admin=u.is_admin, is_active=u.is_active,
            enrollments=[
                {"enrollment_id": e.id, "course_id": e.course.id, "course_title": e.course.title}
                for e in u.enrollments
            ],
        )
        for u in users
    ]


@router.post("/invite", response_model=dict)
async def invite_user(data: InviteRequest, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user:
        user = User(email=data.email, name=data.name, hashed_password=hash_password(data.password))
        db.add(user)
        await db.flush()

    existing = await db.execute(
        select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == data.course_id)
    )
    if not existing.scalar_one_or_none():
        db.add(Enrollment(user_id=user.id, course_id=data.course_id))

    # Send invite email if requested
    email_sent = False
    if data.send_email:
        course_result = await db.execute(select(Course).where(Course.id == data.course_id))
        course = course_result.scalar_one_or_none()
        course_title = course.title if course else "Kurs"
        base = str(request.base_url).rstrip("/")
        login_url = base.replace("http://", "https://", 1) + "/login"
        try:
            email_sent = send_invite_email(data.email, data.name, course_title, data.password, login_url)
        except Exception as e:
            logger.error(f"Failed to send invite email: {e}")

    return {"user_id": user.id, "enrolled": True, "email_sent": email_sent}


@router.post("/{user_id}/enroll")
async def enroll_user(user_id: str, data: dict, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    course_id = data.get("course_id")
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id required")
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")
    existing = await db.execute(
        select(Enrollment).where(Enrollment.user_id == user_id, Enrollment.course_id == course_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Bereits eingeschrieben")
    db.add(Enrollment(user_id=user_id, course_id=course_id))
    return {"ok": True}


@router.put("/{user_id}/toggle-active")
async def toggle_active(user_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot deactivate admin user")
    user.is_active = not user.is_active
    return {"is_active": user.is_active}


@router.delete("/enrollment/{enrollment_id}")
async def remove_enrollment(enrollment_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    await db.delete(enrollment)
    return {"ok": True}


@router.delete("/{user_id}")
async def delete_user(user_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot delete admin user")
    await db.delete(user)
    return {"ok": True}
