"""Admin-Endpoints für das Live-Call-Serie→Kurs-Mapping.

Prefix-Vorschlag: leitet aus realen Drive-Namen den Teil VOR dem Datum ab und
filtert bereits gemappte raus → im Admin anklickbar statt abtippen.
"""
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.announcements import _enrolled_users, PLATFORM_BASE_URL
from app.core.auth import require_admin
from app.core.config import settings
from app.core.db import get_db
from app.core.email import send_announcement_email
from app.core.live_call_token import verify_action_token
from app.core.time import utc_now
from app.integrations.bunny_stream import delete_video_by_embed_url
from app.integrations.google_drive import list_video_files
from app.models.course import Lesson, Announcement
from app.models.live_call import LiveCallSeries, LiveCallImport
from app.models.user import User

router = APIRouter()

_PREFIX_SPLIT = re.compile(r"\s*-\s*\d{4}/\d{2}/\d{2}\s")  # alles vor " - YYYY/MM/DD "


class SeriesCreate(BaseModel):
    course_id: str
    recording_name_prefix: str


class SeriesOut(BaseModel):
    id: str
    course_id: str
    recording_name_prefix: str
    active: bool


def list_all_video_names(folder: str, since: str) -> list[str]:
    """Alle Video-Namen im Ordner (prefixlos), für den Vorschlag."""
    return [f["name"] for f in list_video_files(folder, "", since)]


@router.post("/series", response_model=SeriesOut)
async def create_series(data: SeriesCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    prefix = data.recording_name_prefix.strip()
    if not prefix:
        raise HTTPException(400, "recording_name_prefix erforderlich")
    series = LiveCallSeries(course_id=data.course_id, recording_name_prefix=prefix)
    db.add(series)
    await db.commit()
    return SeriesOut(id=series.id, course_id=series.course_id,
                     recording_name_prefix=series.recording_name_prefix, active=series.active)


@router.get("/series", response_model=list[SeriesOut])
async def list_series(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(LiveCallSeries))).scalars().all()
    return [SeriesOut(id=s.id, course_id=s.course_id,
                      recording_name_prefix=s.recording_name_prefix, active=s.active) for s in rows]


@router.delete("/series/{series_id}")
async def delete_series(series_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(LiveCallSeries).where(LiveCallSeries.id == series_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Serie nicht gefunden")
    await db.delete(s)
    await db.commit()
    return {"ok": True}


@router.get("/suggest-prefixes", response_model=list[str])
async def suggest_prefixes(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Kandidaten-Prefixe aus realen Drive-Namen, die noch zu keiner Serie passen."""
    folder = settings.meet_recordings_folder_id
    if not folder:
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = set((await db.execute(select(LiveCallSeries.recording_name_prefix))).scalars().all())
    out: list[str] = []
    for name in list_all_video_names(folder, since):
        prefix = _PREFIX_SPLIT.split(name, maxsplit=1)[0].strip()
        if prefix and prefix not in existing and not any(name.startswith(e) for e in existing) and prefix not in out:
            out.append(prefix)
    return out


# --- Freigabe-Flow (1-Klick aus der Mail, token-authentifiziert) ---

def _page(msg: str) -> str:
    return (f"<!DOCTYPE html><html lang='de'><body style='font-family:Arial;text-align:center;"
            f"padding:60px;color:#303030;'><h2>{msg}</h2></body></html>")


async def _send_lesson_announcement(db, course_id: str, lesson_id: str, subject: str, body: str) -> None:
    enrolled = await _enrolled_users(db, course_id)
    db.add(Announcement(course_id=course_id, target_type="lesson", target_id=lesson_id,
                        subject=subject, body=body, recipient_count=len(enrolled), created_by_user_id=None))
    cta_url = f"{PLATFORM_BASE_URL}/course/{course_id}/lesson/{lesson_id}"
    for u in enrolled:
        try:
            send_announcement_email(to_email=u.email, to_name=u.name or "", subject=subject, body_text=body, cta_url=cta_url)
        except Exception:
            pass


async def _approve(db, imp: LiveCallImport) -> None:
    if imp.status == "published":
        return  # idempotent — keine zweite Ankündigung
    if imp.status != "imported":
        raise HTTPException(409, f"Import im Status '{imp.status}' nicht freigebbar")
    series = (await db.execute(select(LiveCallSeries).where(LiveCallSeries.id == imp.series_id))).scalar_one()
    lesson = (await db.execute(select(Lesson).where(Lesson.id == imp.lesson_id))).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(404, "Lektion nicht gefunden")
    lesson.is_published = True
    datum = imp.occurrence_at.strftime("%d.%m.%Y") if imp.occurrence_at else ""
    subject = f"Die Aufzeichnung vom {datum} ist da 💛"
    body = ("Hallo,\n\ndie Aufzeichnung unseres letzten Live-Calls ist jetzt für dich im Kurs verfügbar. "
            "Schau sie dir in Ruhe an – und nutze, was für dich passt.\n\nViel Freude damit!")
    await _send_lesson_announcement(db, series.course_id, imp.lesson_id, subject, body)
    imp.status = "published"
    imp.published_at = utc_now()
    await db.commit()


@router.get("/approve", response_class=HTMLResponse)
async def approve_link(import_id: str, token: str, db: AsyncSession = Depends(get_db)):
    if verify_action_token(token, "approve") != import_id:
        return HTMLResponse(_page("Ungültiger oder abgelaufener Link."), status_code=400)
    imp = (await db.execute(select(LiveCallImport).where(LiveCallImport.id == import_id))).scalar_one_or_none()
    if not imp:
        return HTMLResponse(_page("Import nicht gefunden."), status_code=404)
    await _approve(db, imp)
    return HTMLResponse(_page("Freigegeben & angekündigt ✅ — die Lektion ist jetzt sichtbar."))
