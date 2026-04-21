from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.auth import get_current_user
from app.core.time import utc_now
from app.models.user import User
from app.models.course import Enrollment, Module, Section, Lesson, LessonProgress

router = APIRouter()


async def _require_enrollment_for_lesson(db: AsyncSession, user: User, lesson_id: str) -> None:
    """Raise 403 if user is not enrolled in the course containing this lesson."""
    if user.is_admin:
        return
    result = await db.execute(
        select(Enrollment)
        .join(Module, Module.course_id == Enrollment.course_id)
        .join(Section, Section.module_id == Module.id)
        .join(Lesson, Lesson.section_id == Section.id)
        .where(Lesson.id == lesson_id, Enrollment.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not enrolled")


@router.post("/{lesson_id}/complete")
async def mark_complete(lesson_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _require_enrollment_for_lesson(db, user, lesson_id)
    result = await db.execute(
        select(LessonProgress).where(
            LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson_id
        )
    )
    progress = result.scalar_one_or_none()
    if progress:
        progress.completed = True
        progress.completed_at = utc_now()
    else:
        db.add(LessonProgress(
            user_id=user.id, lesson_id=lesson_id,
            completed=True, completed_at=utc_now(),
        ))
    return {"ok": True}


@router.post("/{lesson_id}/uncomplete")
async def mark_uncomplete(lesson_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _require_enrollment_for_lesson(db, user, lesson_id)
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
