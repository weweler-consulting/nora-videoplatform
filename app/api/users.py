from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.auth import require_admin, hash_password
from app.models.user import User
from app.models.course import Enrollment, Course

router = APIRouter()


class UserWithEnrollments(BaseModel):
    id: str
    email: str
    name: str
    is_admin: bool
    enrollments: list[dict] = []


class InviteRequest(BaseModel):
    email: EmailStr
    name: str
    course_id: str
    password: str = "changeme123"


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
            id=u.id, email=u.email, name=u.name, is_admin=u.is_admin,
            enrollments=[
                {"enrollment_id": e.id, "course_id": e.course.id, "course_title": e.course.title}
                for e in u.enrollments
            ],
        )
        for u in users
    ]


@router.post("/invite", response_model=dict)
async def invite_user(data: InviteRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
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

    return {"user_id": user.id, "enrolled": True}


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
