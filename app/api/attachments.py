import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.auth import require_admin, get_current_user
from app.models.user import User
from app.models.course import Lesson, LessonAttachment, Enrollment, Section, Module

router = APIRouter()

FILES_DIR = Path("/app/data/files")
# Fallback for local development
if not FILES_DIR.parent.exists():
    FILES_DIR = Path(__file__).parent.parent.parent / "data" / "files"


@router.post("/lessons/{lesson_id}/attachments")
async def upload_attachment(
    lesson_id: str,
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    FILES_DIR.mkdir(parents=True, exist_ok=True)

    attachment_id = str(uuid.uuid4())
    # Sanitize filename
    original = file.filename or "file"
    ext = Path(original).suffix
    stored_name = f"{attachment_id}{ext}"

    file_path = FILES_DIR / stored_name
    content = await file.read()
    file_path.write_bytes(content)

    attachment = LessonAttachment(
        id=attachment_id,
        lesson_id=lesson_id,
        filename=stored_name,
        original_filename=original,
        file_size=len(content),
    )
    db.add(attachment)
    await db.flush()

    return {
        "id": attachment.id,
        "original_filename": attachment.original_filename,
        "file_size": attachment.file_size,
    }


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(
    attachment_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download with standard Authorization header auth (no token in URL)."""
    result = await db.execute(
        select(LessonAttachment).where(LessonAttachment.id == attachment_id)
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    if not user.is_admin:
        enrolled = await db.execute(
            select(Enrollment)
            .join(Module, Module.course_id == Enrollment.course_id)
            .join(Section, Section.module_id == Module.id)
            .join(Lesson, Lesson.section_id == Section.id)
            .where(Lesson.id == attachment.lesson_id, Enrollment.user_id == user.id)
        )
        if not enrolled.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not enrolled")

    file_path = FILES_DIR / attachment.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=attachment.original_filename,
        media_type="application/octet-stream",
    )


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LessonAttachment).where(LessonAttachment.id == attachment_id)
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Delete file
    file_path = FILES_DIR / attachment.filename
    if file_path.exists():
        file_path.unlink()

    await db.delete(attachment)
    return {"ok": True}


@router.get("/lessons/{lesson_id}/attachments")
async def list_attachments(
    lesson_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LessonAttachment)
        .where(LessonAttachment.lesson_id == lesson_id)
        .order_by(LessonAttachment.created_at)
    )
    attachments = result.scalars().all()
    return [
        {
            "id": a.id,
            "original_filename": a.original_filename,
            "file_size": a.file_size,
        }
        for a in attachments
    ]
