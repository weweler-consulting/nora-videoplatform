"""Admin endpoints for CourseHub editing."""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.db import get_db
from app.models.course import Course
from app.models.hub import CourseHub
from app.models.user import User
from app.schemas.hub import UploadPdfResponse


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
