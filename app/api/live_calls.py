"""Admin-Endpoints für das Live-Call-Serie→Kurs-Mapping.

Prefix-Vorschlag: leitet aus realen Drive-Namen den Teil VOR dem Datum ab und
filtert bereits gemappte raus → im Admin anklickbar statt abtippen.
"""
import asyncio
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.announcements import PLATFORM_BASE_URL
from app.core.auth import require_admin
from app.core.config import settings
from app.core.db import get_db
from app.core.email import send_announcement_email
from app.core.live_call_token import verify_action_token
from app.core.time import utc_now
from app.integrations.bunny_stream import delete_video_by_embed_url
from app.integrations.google_drive import list_video_files
from app.models.course import Lesson, Announcement, Enrollment, Section, Module
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


# --- Freigabe-Flow: GET zeigt nur eine Bestätigungsseite, POST führt aus.
# Gegen E-Mail-Prefetch (Gmail-Proxy, MS Safe Links, Link-Scanner): ein GET darf
# NICHTS verändern, sonst könnte ein Scanner ungeklickt veröffentlichen/löschen.

def _page(msg: str) -> str:
    return (f"<!DOCTYPE html><html lang='de'><head><meta charset='utf-8'></head>"
            f"<body style='font-family:Arial;text-align:center;padding:60px;color:#303030;'>"
            f"<h2>{msg}</h2></body></html>")


def _confirm_page(action_path: str, import_id: str, token: str, heading: str, button: str, hint: str) -> str:
    return (f"<!DOCTYPE html><html lang='de'><head><meta charset='utf-8'></head>"
            f"<body style='font-family:Arial;text-align:center;padding:60px;color:#303030;'>"
            f"<h2>{heading}</h2><p style='color:#666;'>{hint}</p>"
            f"<form method='post' action='{action_path}' style='margin-top:24px;'>"
            f"<input type='hidden' name='import_id' value='{import_id}'>"
            f"<input type='hidden' name='token' value='{token}'>"
            f"<button type='submit' style='background:#D47479;color:#fff;border:0;font-weight:700;"
            f"padding:12px 24px;border-radius:6px;font-size:15px;cursor:pointer;'>{button}</button>"
            f"</form></body></html>")


async def _enrolled_mailable(db, course_id: str) -> list[User]:
    """Eingeschriebene, denen man wirklich mailen kann — aktiv, kein Admin, mit
    Passwort (gleiche Gate wie der drip_notifier)."""
    result = await db.execute(
        select(User).join(Enrollment, Enrollment.user_id == User.id).where(
            Enrollment.course_id == course_id,
            User.is_active.is_(True), User.is_admin.is_(False), User.hashed_password != "",
        )
    )
    return list(result.scalars().all())


async def _send_lesson_announcement(db, course_id: str, lesson_id: str, subject: str, body: str) -> None:
    enrolled = await _enrolled_mailable(db, course_id)
    db.add(Announcement(course_id=course_id, target_type="lesson", target_id=lesson_id,
                        subject=subject, body=body, recipient_count=len(enrolled), created_by_user_id=None))
    cta_url = f"{PLATFORM_BASE_URL}/course/{course_id}/lesson/{lesson_id}"

    def _fanout() -> None:
        # Blockierendes smtplib (pro Empfängerin) gebündelt in EINEM Thread —
        # der Event-Loop bleibt frei. ORM-Attribute sind geladen (expire_on_commit
        # =False), daher in-Thread lesbar ohne DB-Zugriff.
        for u in enrolled:
            try:
                send_announcement_email(to_email=u.email, to_name=u.name or "", subject=subject, body_text=body, cta_url=cta_url)
            except Exception:
                pass

    await asyncio.to_thread(_fanout)


async def _approve(db, imp: LiveCallImport) -> None:
    # Atomar beanspruchen: nur wer 'imported'→'publishing' schafft, fährt fort.
    # Verhindert Doppel-Ankündigung bei zwei gleichzeitigen Aufrufen (Doppelklick
    # oder Scanner+Mensch) — der Mail-Fanout passiert nur einmal.
    claim = await db.execute(
        update(LiveCallImport)
        .where(LiveCallImport.id == imp.id, LiveCallImport.status == "imported")
        .values(status="publishing")
    )
    if (claim.rowcount or 0) == 0:
        return  # nicht (mehr) freigebbar oder bereits in Arbeit/veröffentlicht
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
    await db.execute(
        update(LiveCallImport).where(LiveCallImport.id == imp.id).values(status="published", published_at=utc_now())
    )
    await db.commit()


@router.get("/approve", response_class=HTMLResponse)
async def approve_confirm(import_id: str, token: str):
    if verify_action_token(token, "approve") != import_id:
        return HTMLResponse(_page("Ungültiger oder abgelaufener Link."), status_code=400)
    return HTMLResponse(_confirm_page(
        "/api/v1/live-calls/approve", import_id, token,
        "Live-Call freigeben?", "Ja, freigeben & ankündigen",
        "Die Lektion wird sichtbar und die Kundinnen bekommen die Ankündigungs-Mail.",
    ))


@router.post("/approve", response_class=HTMLResponse)
async def approve_action(import_id: str = Form(...), token: str = Form(...), db: AsyncSession = Depends(get_db)):
    if verify_action_token(token, "approve") != import_id:
        return HTMLResponse(_page("Ungültiger oder abgelaufener Link."), status_code=400)
    imp = (await db.execute(select(LiveCallImport).where(LiveCallImport.id == import_id))).scalar_one_or_none()
    if not imp:
        return HTMLResponse(_page("Import nicht gefunden."), status_code=404)
    await _approve(db, imp)
    return HTMLResponse(_page("Freigegeben & angekündigt ✅ — die Lektion ist jetzt sichtbar."))


async def _dismiss(db, imp: LiveCallImport) -> None:
    if imp.status in ("dismissed", "published"):
        return  # 'published' NICHT zerstören (Lektion ist live + angekündigt); 'dismissed' idempotent
    lesson = (await db.execute(select(Lesson).where(Lesson.id == imp.lesson_id))).scalar_one_or_none() if imp.lesson_id else None
    if lesson is not None:
        if lesson.video_url:
            await asyncio.to_thread(delete_video_by_embed_url, lesson.video_url)
        await db.delete(lesson)
    # Auto-angelegtes, dann leeres 'Live Call <Datum>'-Modul mit aufräumen (NUR wenn
    # WIR es angelegt haben — Platzhalter der Kursleiterin bleiben unangetastet).
    if imp.module_created and imp.module_id:
        remaining = (await db.execute(
            select(func.count(Lesson.id)).join(Section, Lesson.section_id == Section.id)
            .where(Section.module_id == imp.module_id)
        )).scalar_one()
        if remaining == 0:
            mod = (await db.execute(select(Module).where(Module.id == imp.module_id))).scalar_one_or_none()
            if mod is not None:
                await db.delete(mod)  # cascade löscht die Section
    imp.status = "dismissed"
    await db.commit()


@router.get("/dismiss", response_class=HTMLResponse)
async def dismiss_confirm(import_id: str, token: str, db: AsyncSession = Depends(get_db)):
    if verify_action_token(token, "dismiss") != import_id:
        return HTMLResponse(_page("Ungültiger oder abgelaufener Link."), status_code=400)
    imp = (await db.execute(select(LiveCallImport).where(LiveCallImport.id == import_id))).scalar_one_or_none()
    if imp and imp.status == "published":
        return HTMLResponse(_page("Schon freigegeben — Verwerfen nicht möglich."))
    return HTMLResponse(_confirm_page(
        "/api/v1/live-calls/dismiss", import_id, token,
        "Live-Call verwerfen?", "Ja, verwerfen",
        "Die (versteckte) Lektion und das hochgeladene Video werden gelöscht.",
    ))


@router.post("/dismiss", response_class=HTMLResponse)
async def dismiss_action(import_id: str = Form(...), token: str = Form(...), db: AsyncSession = Depends(get_db)):
    if verify_action_token(token, "dismiss") != import_id:
        return HTMLResponse(_page("Ungültiger oder abgelaufener Link."), status_code=400)
    imp = (await db.execute(select(LiveCallImport).where(LiveCallImport.id == import_id))).scalar_one_or_none()
    if not imp:
        return HTMLResponse(_page("Import nicht gefunden."), status_code=404)
    await _dismiss(db, imp)
    return HTMLResponse(_page("Verworfen ✅ — Lektion und Video wurden entfernt."))


# --- Admin-Liste + Admin-Aktionen (für die Pending-Review-Oberfläche) ---

class ImportOut(BaseModel):
    id: str
    series_id: str
    recording_name: str
    occurrence_at: datetime | None
    status: str
    module_id: str | None
    lesson_id: str | None


@router.get("/imports", response_model=list[ImportOut])
async def list_imports(status: str | None = None, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    q = select(LiveCallImport).order_by(LiveCallImport.created_at.desc())
    if status:
        q = q.where(LiveCallImport.status == status)
    rows = (await db.execute(q)).scalars().all()
    return [ImportOut(id=r.id, series_id=r.series_id, recording_name=r.recording_name,
                      occurrence_at=r.occurrence_at, status=r.status, module_id=r.module_id, lesson_id=r.lesson_id) for r in rows]


@router.post("/imports/{import_id}/approve")
async def admin_approve(import_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    imp = (await db.execute(select(LiveCallImport).where(LiveCallImport.id == import_id))).scalar_one_or_none()
    if not imp:
        raise HTTPException(404, "Import nicht gefunden")
    await _approve(db, imp)
    return {"ok": True}


@router.post("/imports/{import_id}/dismiss")
async def admin_dismiss(import_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    imp = (await db.execute(select(LiveCallImport).where(LiveCallImport.id == import_id))).scalar_one_or_none()
    if not imp:
        raise HTTPException(404, "Import nicht gefunden")
    await _dismiss(db, imp)
    return {"ok": True}
