"""Admin-Endpoints für das Live-Call-Serie→Kurs-Mapping.

Prefix-Vorschlag: leitet aus realen Drive-Namen den Teil VOR dem Datum ab und
filtert bereits gemappte raus → im Admin anklickbar statt abtippen.
"""
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.config import settings
from app.core.db import get_db
from app.integrations.google_drive import list_video_files
from app.models.live_call import LiveCallSeries
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
