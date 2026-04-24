"""Admin endpoints for CourseHub editing."""
import os
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.db import get_db
from app.integrations.bunny_storage import BunnyNotConfigured, upload_image
from app.models.course import Course
from app.models.hub import CourseHub
from app.models.user import User
from app.schemas.hub import UploadImageResponse, UploadPdfResponse


router = APIRouter()


def _hub_storage_dir() -> Path:
    base = Path(os.environ.get("HUB_STORAGE_DIR", "/app/data/hub_downloads"))
    if not base.parent.exists():
        base = Path(__file__).resolve().parent.parent.parent / "data" / "hub_downloads"
    base.mkdir(parents=True, exist_ok=True)
    return base


MAX_PDF_BYTES = 20 * 1024 * 1024


async def _require_course(db: AsyncSession, course_id: str) -> Course:
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.post("/{course_id}/hub/pdf", response_model=UploadPdfResponse)
async def upload_hub_pdf(
    course_id: str,
    file: UploadFile = File(...),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_course(db, course_id)

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="PDF erwartet")

    content = await file.read()
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail="Maximal 20 MB")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Kein gültiges PDF")

    course_dir = _hub_storage_dir() / course_id
    course_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.pdf"
    path = course_dir / filename
    path.write_bytes(content)

    return UploadPdfResponse(
        file_path=str(path),
        file_name=file.filename or "download.pdf",
        file_size_kb=max(1, len(content) // 1024),
    )


MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/{course_id}/hub/image", response_model=UploadImageResponse)
async def upload_hub_image(
    course_id: str,
    file: UploadFile = File(...),
    kind: Literal["product", "contact_photo"] = Form(...),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_course(db, course_id)

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Nur JPEG, PNG oder WebP")

    content = await file.read()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Maximal 5 MB")

    try:
        url = await upload_image(
            content, course_id=course_id, kind=kind,
            filename=file.filename or "image.bin",
        )
    except BunnyNotConfigured as e:
        raise HTTPException(status_code=503, detail=f"Bunny Storage nicht konfiguriert: {e}")

    return UploadImageResponse(url=url)
