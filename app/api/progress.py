from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.course import LessonProgress

router = APIRouter()


@router.post("/{lesson_id}/complete")
async def mark_complete(lesson_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(LessonProgress).where(
            LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson_id
        )
    )
    progress = result.scalar_one_or_none()
    if progress:
        progress.completed = True
        progress.completed_at = datetime.utcnow()
    else:
        db.add(LessonProgress(
            user_id=user.id, lesson_id=lesson_id,
            completed=True, completed_at=datetime.utcnow(),
        ))
    return {"ok": True}


@router.post("/{lesson_id}/uncomplete")
async def mark_uncomplete(lesson_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(LessonProgress).where(
            LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson_id
        )
    )
    progress = result.scalar_one_or_none()
    if progress:
        progress.completed = False
        progress.completed_at = None
    return {"ok": True}
