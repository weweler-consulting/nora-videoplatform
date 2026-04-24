from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.course import Course, Enrollment
from app.models.hub import CourseHub, HubDownload
from app.models.user import User
from app.schemas.hub import (
    HubDownloadSchema, HubLinkSchema, HubLiveCallSchema, HubPayload, HubProductSchema,
)

router = APIRouter()


async def _ensure_access(
    course_id: str, user: User, db: AsyncSession, *, admin_only: bool = False,
) -> None:
    if user.is_admin:
        return
    if admin_only:
        raise HTTPException(status_code=403, detail="Admin required")
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == user.id, Enrollment.course_id == course_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not enrolled in this course")


async def _load_hub(db: AsyncSession, course_id: str) -> CourseHub:
    result = await db.execute(
        select(CourseHub).where(CourseHub.course_id == course_id).options(
            selectinload(CourseHub.links),
            selectinload(CourseHub.live_calls),
            selectinload(CourseHub.products),
            selectinload(CourseHub.downloads),
        )
    )
    hub = result.scalar_one_or_none()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")
    return hub


def _hub_to_payload(hub: CourseHub) -> HubPayload:
    return HubPayload(
        hero_variant=hub.hero_variant, hero_eyebrow=hub.hero_eyebrow,
        hero_title_html=hub.hero_title_html, hero_body=hub.hero_body,
        contact_user_id=hub.contact_user_id,
        contact_name_override=hub.contact_name_override, contact_role=hub.contact_role,
        contact_email_override=hub.contact_email_override,
        contact_whatsapp_url=hub.contact_whatsapp_url,
        contact_photo_url=hub.contact_photo_url,
        show_contact=hub.show_contact, show_live_calls=hub.show_live_calls,
        show_products=hub.show_products, show_downloads=hub.show_downloads,
        links=[HubLinkSchema(id=l.id, icon_type=l.icon_type, label=l.label,
                             sublabel=l.sublabel, url=l.url, sort_order=l.sort_order)
               for l in hub.links],
        live_calls=[HubLiveCallSchema(id=c.id, tag=c.tag, title=c.title,
                                      body=c.body, sort_order=c.sort_order)
                    for c in hub.live_calls],
        products=[HubProductSchema(id=p.id, label=p.label, title=p.title,
                                   description=p.description, cta_text=p.cta_text,
                                   url=p.url, image_url=p.image_url,
                                   highlight=p.highlight, sort_order=p.sort_order)
                  for p in hub.products],
        downloads=[HubDownloadSchema(id=d.id, title=d.title, description=d.description,
                                     file_path=d.file_path, file_name=d.file_name,
                                     file_size_kb=d.file_size_kb, sort_order=d.sort_order)
                   for d in hub.downloads],
    )


@router.get("/{course_id}/hub", response_model=HubPayload)
async def get_course_hub(
    course_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify course exists (gives 404 rather than 403 for unknown IDs)
    result = await db.execute(select(Course).where(Course.id == course_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Course not found")
    await _ensure_access(course_id, user, db)
    hub = await _load_hub(db, course_id)
    return _hub_to_payload(hub)


@router.get("/{course_id}/hub/downloads/{download_id}")
async def download_hub_file(
    course_id: str,
    download_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_access(course_id, user, db)
    result = await db.execute(
        select(HubDownload).join(CourseHub, CourseHub.id == HubDownload.hub_id)
        .where(HubDownload.id == download_id, CourseHub.course_id == course_id)
    )
    download = result.scalar_one_or_none()
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")
    path = Path(download.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    encoded = quote(download.file_name)
    content_disposition = (
        f'attachment; filename="{download.file_name}"; filename*=utf-8\'\'{encoded}'
    )
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition},
    )
