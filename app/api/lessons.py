from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.auth import require_admin
from app.models.user import User
from app.models.course import Lesson
from app.schemas.course import LessonCreate, LessonUpdate

router = APIRouter()


@router.post("/", response_model=dict)
async def create_lesson(data: LessonCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    lesson = Lesson(**data.model_dump())
    db.add(lesson)
    await db.flush()
    return {"id": lesson.id}


@router.put("/{lesson_id}", response_model=dict)
async def update_lesson(lesson_id: str, data: LessonUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(lesson, key, value)
    return {"id": lesson.id}


@router.delete("/{lesson_id}")
async def delete_lesson(lesson_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    await db.delete(lesson)
    return {"ok": True}
