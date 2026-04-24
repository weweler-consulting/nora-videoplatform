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


from pathlib import Path as _Path

import bleach
from sqlalchemy.orm import selectinload

from app.api.hub import _hub_to_payload, _load_hub
from app.integrations.bunny_storage import delete_image
from app.models.hub import HubDownload, HubLink, HubLiveCall, HubProduct
from app.schemas.hub import HubPayload


ALLOWED_HTML_TAGS = ["em", "br"]


def _sanitize_html(raw: str) -> str:
    return bleach.clean(raw or "", tags=ALLOWED_HTML_TAGS, attributes={}, strip=True)


@router.get("/{course_id}/hub", response_model=HubPayload)
async def admin_get_hub(
    course_id: str,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_course(db, course_id)
    hub = await _load_hub(db, course_id)
    return _hub_to_payload(hub)


@router.put("/{course_id}/hub", response_model=HubPayload)
async def admin_put_hub(
    course_id: str,
    payload: HubPayload,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_course(db, course_id)
    hub = await _load_hub(db, course_id)

    # Capture old media URLs/paths for cleanup
    old_pdf_paths = {d.file_path for d in hub.downloads}
    old_image_urls = {p.image_url for p in hub.products if p.image_url}
    old_contact_photo = hub.contact_photo_url or ""

    # Hero + Contact
    hub.hero_variant = payload.hero_variant
    hub.hero_eyebrow = payload.hero_eyebrow
    hub.hero_title_html = _sanitize_html(payload.hero_title_html)
    hub.hero_body = payload.hero_body

    hub.contact_user_id = payload.contact_user_id
    hub.contact_name_override = payload.contact_name_override
    hub.contact_role = payload.contact_role
    hub.contact_email_override = payload.contact_email_override
    hub.contact_whatsapp_url = payload.contact_whatsapp_url
    hub.contact_photo_url = payload.contact_photo_url

    hub.show_contact = payload.show_contact
    hub.show_live_calls = payload.show_live_calls
    hub.show_products = payload.show_products
    hub.show_downloads = payload.show_downloads

    # Replace-all for lists
    hub.links.clear()
    hub.live_calls.clear()
    hub.products.clear()
    hub.downloads.clear()
    await db.flush()

    for i, link in enumerate(payload.links):
        hub.links.append(HubLink(
            icon_type=link.icon_type, label=link.label, sublabel=link.sublabel,
            url=link.url, sort_order=link.sort_order or i,
        ))
    for i, call in enumerate(payload.live_calls):
        hub.live_calls.append(HubLiveCall(
            tag=call.tag, title=call.title, body=call.body,
            sort_order=call.sort_order or i,
        ))
    for i, prod in enumerate(payload.products):
        hub.products.append(HubProduct(
            label=prod.label, title=prod.title, description=prod.description,
            cta_text=prod.cta_text, url=prod.url, image_url=prod.image_url,
            highlight=prod.highlight, sort_order=prod.sort_order or i,
        ))
    for i, dl in enumerate(payload.downloads):
        # Path traversal guard: only accept files inside the hub storage dir
        abs_path = _Path(dl.file_path).resolve()
        allowed_root = _hub_storage_dir().resolve()
        if not str(abs_path).startswith(str(allowed_root)):
            raise HTTPException(status_code=400, detail=f"Ungültiger Pfad: {dl.file_path}")
        hub.downloads.append(HubDownload(
            title=dl.title, description=dl.description,
            file_path=dl.file_path, file_name=dl.file_name,
            file_size_kb=dl.file_size_kb, sort_order=dl.sort_order or i,
        ))

    await db.flush()
    await db.refresh(hub, attribute_names=["links", "live_calls", "products", "downloads"])

    # Dead-file cleanup (after successful DB update)
    new_pdf_paths = {d.file_path for d in payload.downloads}
    for stale in old_pdf_paths - new_pdf_paths:
        try:
            _Path(stale).unlink(missing_ok=True)
        except OSError:
            pass

    new_image_urls = {p.image_url for p in payload.products if p.image_url}
    for stale in old_image_urls - new_image_urls:
        await delete_image(stale)

    if old_contact_photo and old_contact_photo != hub.contact_photo_url:
        await delete_image(old_contact_photo)

    return _hub_to_payload(hub)
