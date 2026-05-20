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


@router.get(
    "/{course_id}/announcements/preview",
    response_model=AnnouncementPreviewResponse,
)
async def preview_announcement(
    course_id: str,
    target_type: str,
    target_id: str,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementPreviewResponse:
    await _require_course(db, course_id)
    target_title, module_title, _cta = await _resolve_target(db, course_id, target_type, target_id)

    if target_type == "module":
        suggested_subject = f"Neues Modul: {target_title}"
        suggested_body = (
            f"in deinem Kurs ist ein neues Modul verfügbar:\n\n"
            f"{target_title}\n\n"
            f"Schau gleich rein und mach weiter."
        )
    else:
        suggested_subject = f"Neue Lektion in {module_title}: {target_title}"
        suggested_body = (
            f"in deinem Kurs ist eine neue Lektion verfügbar:\n\n"
            f"{module_title} – {target_title}\n\n"
            f"Schau gleich rein und mach weiter."
        )

    enrolled = await _enrolled_users(db, course_id)

    return AnnouncementPreviewResponse(
        suggested_subject=suggested_subject,
        suggested_body=suggested_body,
        recipient_count=len(enrolled),
        target_title=target_title,
        target_module_title=module_title,
    )


@router.post(
    "/{course_id}/announcements",
    response_model=AnnouncementCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_announcement(
    course_id: str,
    payload: AnnouncementCreateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementCreateResponse:
    course = await _require_course(db, course_id)
    target_title, module_title, cta_url = await _resolve_target(
        db, course_id, payload.target_type, payload.target_id
    )

    enrolled = await _enrolled_users(db, course_id)
    if not enrolled:
        raise HTTPException(
            status_code=422,
            detail="Keine aktiven Teilnehmerinnen für diesen Kurs",
        )

    sent = 0
    failed = 0
    for user in enrolled:
        try:
            ok = send_announcement_email(
                to_email=user.email,
                to_name=user.name or "",
                subject=payload.subject,
                body_text=payload.body,
                cta_url=cta_url,
            )
            if ok:
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    announcement = Announcement(
        course_id=course_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        subject=payload.subject,
        body=payload.body,
        recipient_count=len(enrolled),
        created_by_user_id=admin.id,
    )
    db.add(announcement)
    await db.commit()
    await db.refresh(announcement)

    return AnnouncementCreateResponse(
        announcement=AnnouncementResponse(
            id=announcement.id,
            course_id=announcement.course_id,
            target_type=announcement.target_type,  # type: ignore
            target_id=announcement.target_id,
            target_title=target_title,
            target_module_title=module_title,
            subject=announcement.subject,
            body=announcement.body,
            recipient_count=announcement.recipient_count,
            sent_at=announcement.sent_at,
            created_by=CreatedByInfo(id=admin.id, name=admin.name or ""),
        ),
        delivery_summary={"sent": sent, "failed": failed},
    )
