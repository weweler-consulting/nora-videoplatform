"""Admin endpoints for course announcements (V1: immediate send)."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.db import get_db
from app.core.email import send_announcement_email
from app.models.course import (
    Announcement,
    Course,
    Enrollment,
    Lesson,
    Module,
    Section,
)
from app.models.user import User
from app.schemas.announcement import (
    AnnouncementCreateRequest,
    AnnouncementCreateResponse,
    AnnouncementListResponse,
    AnnouncementPreviewResponse,
    AnnouncementResponse,
    CreatedByInfo,
)

router = APIRouter()

PLATFORM_BASE_URL = "https://kurse.noraweweler.de"


async def _require_course(db: AsyncSession, course_id: str) -> Course:
    course = (await db.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Kurs nicht gefunden")
    return course


async def _resolve_target(
    db: AsyncSession,
    course_id: str,
    target_type: str,
    target_id: str,
) -> tuple[str, Optional[str], str]:
    """Resolve target. Returns (target_title, target_module_title, cta_url).

    Raises 422 if target doesn't belong to course.
    """
    if target_type == "module":
        module = (
            await db.execute(
                select(Module).where(and_(Module.id == target_id, Module.course_id == course_id))
            )
        ).scalar_one_or_none()
        if not module:
            raise HTTPException(
                status_code=422,
                detail="Modul gehört nicht zu diesem Kurs oder existiert nicht",
            )
        cta = f"{PLATFORM_BASE_URL}/course/{course_id}"
        return module.title, None, cta

    if target_type == "lesson":
        result = await db.execute(
            select(Lesson, Section, Module)
            .join(Section, Lesson.section_id == Section.id)
            .join(Module, Section.module_id == Module.id)
            .where(and_(Lesson.id == target_id, Module.course_id == course_id))
        )
        row = result.first()
        if not row:
            raise HTTPException(
                status_code=422,
                detail="Lektion gehört nicht zu diesem Kurs oder existiert nicht",
            )
        lesson, _section, module = row
        cta = f"{PLATFORM_BASE_URL}/course/{course_id}/lesson/{lesson.id}"
        return lesson.title, module.title, cta

    raise HTTPException(status_code=422, detail="Ungültiger target_type")


async def _enrolled_users(db: AsyncSession, course_id: str) -> list[User]:
    result = await db.execute(
        select(User).join(Enrollment, Enrollment.user_id == User.id).where(Enrollment.course_id == course_id)
    )
    return list(result.scalars().all())
