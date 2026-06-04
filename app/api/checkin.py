"""Admin-API für Check-In-Formulare.

Ein Check-in = ein Modul (Container) mit genau einer Lektion vom Typ 'checkin',
die auf ein editierbares Template zeigt. So erscheint der Check-in als Eintrag
in der Modulliste, rendert im Lektions-Player-Frame und zählt über LessonProgress
in den Fortschritt (Phase 3).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.auth import get_current_user, require_admin
from app.core.time import utc_now
from app.models.user import User
from app.models.course import Course, Module, Section, Lesson, LessonProgress
from app.models.checkin import CheckinTemplate, CheckinStep, CheckinResponse, CrmOutbox
from app.api.progress import _require_enrollment_for_lesson
from app.schemas.checkin import (
    CheckinTemplateOut, CheckinStepOut, CheckinLessonOut,
    CheckinModuleCreate, CheckinLessonUpdate, CheckinSubmit, CheckinResponseOut,
)

router = APIRouter()

# Schritt-Typen, die keine Antwort erwarten (reine Anzeige).
_NON_ANSWER_TYPES = {"intro", "bestaetigung"}

# Antwort-Limits: bremsen einen böswilligen eingeloggten Client (Storage-DoS)
# und halten die Datenqualität sauber (keine Junk-Keys für spätere Auswertung).
_MAX_ANSWER_STR = 5000
_MAX_ANSWER_LIST = 50


def _iso_utc(dt) -> str:
    """ISO-8601 mit 'Z'. utc_now() liefert naive UTC; ohne 'Z' würde Node's
    new Date() den String als LOKALE Zeit parsen → Zeitversatz im CRM."""
    return dt.isoformat() + "Z"

_DEFAULT_TITLE = {
    "start": "Check-in: Bestandsaufnahme",
    "laufend": "Wöchentlicher Check-in",
    "ende": "Abschluss-Check-in",
}


async def _resolve_template(db: AsyncSession, typ: str) -> CheckinTemplate:
    result = await db.execute(
        select(CheckinTemplate).where(CheckinTemplate.typ == typ)
        .order_by(CheckinTemplate.created_at.desc())
    )
    template = result.scalars().first()
    if not template:
        raise HTTPException(status_code=404, detail=f"Kein Check-In-Template für typ '{typ}'")
    return template


async def _load_checkin_lesson(db: AsyncSession, lesson_id: str) -> tuple[Lesson, Section, Module]:
    lesson = (await db.execute(select(Lesson).where(Lesson.id == lesson_id))).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lektion nicht gefunden")
    if lesson.type != "checkin":
        raise HTTPException(status_code=400, detail="Lektion ist kein Check-in")
    section = (await db.execute(select(Section).where(Section.id == lesson.section_id))).scalar_one_or_none()
    module = (
        (await db.execute(select(Module).where(Module.id == section.module_id))).scalar_one_or_none()
        if section else None
    )
    return lesson, section, module


def _merge_steps(template_steps: list[CheckinStep], overrides: dict) -> list[CheckinStepOut]:
    step_overrides = (overrides or {}).get("steps", {}) or {}
    out: list[CheckinStepOut] = []
    for s in template_steps:
        ov = step_overrides.get(s.key, {}) or {}
        is_overridden = bool(ov.get("frage") is not None or ov.get("optionen") is not None)
        out.append(CheckinStepOut(
            key=s.key, typ=s.typ,
            frage=ov.get("frage") if ov.get("frage") is not None else s.frage,
            hilfetext=s.hilfetext,
            pflichtfeld=s.pflichtfeld,
            optionen=ov.get("optionen") if ov.get("optionen") is not None else s.optionen,
            skala_min=s.skala_min, skala_max=s.skala_max, skala_labels=s.skala_labels,
            sort_order=s.sort_order, overridden=is_overridden,
        ))
    return out


@router.get("/templates", response_model=list[CheckinTemplateOut])
async def list_templates(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CheckinTemplate).order_by(CheckinTemplate.typ))
    return [CheckinTemplateOut(id=t.id, typ=t.typ, name=t.name) for t in result.scalars().all()]


@router.post("/modules", response_model=dict)
async def create_checkin_module(
    data: CheckinModuleCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    course = (await db.execute(select(Course).where(Course.id == data.course_id))).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Kurs nicht gefunden")
    template = await _resolve_template(db, data.template_typ)

    title = (data.title or "").strip() or _DEFAULT_TITLE.get(data.template_typ, "Check-in")
    if data.week_index and not data.title:
        title = f"Check-in Woche {data.week_index}"

    # Ans Ende: max(sort_order)+1. len-basiert würde nach dem Löschen eines
    # Moduls mit einem bestehenden sort_order kollidieren (→ kaputte Reihenfolge).
    max_so = (await db.execute(
        select(func.max(Module.sort_order)).where(Module.course_id == course.id)
    )).scalar()
    sort_order = (max_so + 1) if max_so is not None else 0

    module = Module(course_id=course.id, title=title, sort_order=sort_order)
    db.add(module)
    await db.flush()
    section = Section(module_id=module.id, title="Check-In", sort_order=0)
    db.add(section)
    await db.flush()

    overrides: dict = {}
    if data.week_index is not None:
        overrides["week_index"] = data.week_index
    lesson = Lesson(
        section_id=section.id, title=title, sort_order=0,
        type="checkin", checkin_template_id=template.id, checkin_overrides=overrides,
    )
    db.add(lesson)
    await db.flush()
    return {"module_id": module.id, "lesson_id": lesson.id}


@router.get("/lessons/{lesson_id}", response_model=CheckinLessonOut)
async def get_checkin_lesson(
    lesson_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    # Enrollment wie bei submit/response — sonst könnte jede eingeloggte Klientin
    # die Formularstruktur fremder Kurse per Lektions-ID auslesen. Admin wird
    # in der Helferfunktion durchgelassen.
    await _require_enrollment_for_lesson(db, user, lesson_id)
    lesson, section, module = await _load_checkin_lesson(db, lesson_id)
    template = (
        await db.execute(
            select(CheckinTemplate).where(CheckinTemplate.id == lesson.checkin_template_id)
        )
    ).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template nicht gefunden")
    steps = (await db.execute(
        select(CheckinStep).where(CheckinStep.template_id == template.id).order_by(CheckinStep.sort_order)
    )).scalars().all()
    overrides = lesson.checkin_overrides or {}
    return CheckinLessonOut(
        lesson_id=lesson.id,
        module_id=module.id if module else "",
        course_id=module.course_id if module else "",
        title=lesson.title,
        template_id=template.id,
        template_typ=template.typ,
        template_name=template.name,
        week_index=overrides.get("week_index"),
        steps=_merge_steps(steps, overrides),
    )


@router.put("/lessons/{lesson_id}", response_model=dict)
async def update_checkin_lesson(
    lesson_id: str, data: CheckinLessonUpdate,
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    lesson, section, module = await _load_checkin_lesson(db, lesson_id)

    if data.title is not None:
        title = data.title.strip()
        if title:
            lesson.title = title
            if module:  # Modul-Titel mitziehen → Modulliste zeigt denselben Namen
                module.title = title

    # checkin_overrides als neues dict zuweisen, damit SQLAlchemy die Änderung
    # erkennt (JSON-Spalte ohne MutableDict trackt In-Place-Mutationen nicht).
    overrides = dict(lesson.checkin_overrides or {})
    if data.week_index is not None:
        overrides["week_index"] = data.week_index
    if data.step_overrides is not None:
        steps = dict(overrides.get("steps", {}))
        for key, ov in data.step_overrides.items():
            cur = dict(steps.get(key, {}))
            if ov.frage is not None:
                cur["frage"] = ov.frage
            if ov.optionen is not None:
                cur["optionen"] = ov.optionen
            # Leerer String / leere Liste = Override entfernen (zurück zum Standard)
            if cur.get("frage") == "":
                cur.pop("frage", None)
            if cur.get("optionen") == []:
                cur.pop("optionen", None)
            if cur:
                steps[key] = cur
            else:
                steps.pop(key, None)
        overrides["steps"] = steps
    lesson.checkin_overrides = overrides

    return {"id": lesson.id}


def _answered(value) -> bool:
    return value not in (None, "", [], {})


@router.get("/lessons/{lesson_id}/response", response_model=CheckinResponseOut)
async def get_checkin_response(
    lesson_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Bestehende Antwort der Klientin (für Read-only/Bearbeiten beim Wiederöffnen)."""
    await _require_enrollment_for_lesson(db, user, lesson_id)
    resp = (await db.execute(
        select(CheckinResponse).where(
            CheckinResponse.user_id == user.id, CheckinResponse.lesson_id == lesson_id
        )
    )).scalar_one_or_none()
    if not resp:
        return CheckinResponseOut(submitted=False)
    return CheckinResponseOut(
        submitted=resp.status == "submitted",
        answers=resp.answers or {},
        submitted_at=resp.submitted_at.isoformat() if resp.submitted_at else None,
        week_index=resp.week_index,
        template_typ=resp.template_typ,
    )


@router.post("/lessons/{lesson_id}/submit", response_model=dict)
async def submit_checkin(
    lesson_id: str, data: CheckinSubmit,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Antwort speichern (ZUERST in der video-platform → treibt Player & Fortschritt),
    Lektion als abgeschlossen markieren. CRM-Sync folgt in Phase 4."""
    await _require_enrollment_for_lesson(db, user, lesson_id)
    lesson, section, module = await _load_checkin_lesson(db, lesson_id)
    if module is None:
        # Verwaiste Check-in-Lektion (Section ohne Modul). Sauber abfangen statt
        # einen Leerstring in die NOT-NULL-FK course_id zu schreiben (→ 500).
        raise HTTPException(status_code=409, detail="Check-in-Lektion ist keinem Modul zugeordnet")
    template = (await db.execute(
        select(CheckinTemplate).where(CheckinTemplate.id == lesson.checkin_template_id)
    )).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template nicht gefunden")
    steps = (await db.execute(
        select(CheckinStep).where(CheckinStep.template_id == template.id)
    )).scalars().all()

    answers = data.answers or {}
    # Nur bekannte Template-Keys zulassen (Datenqualität für spätere Auswertung)
    # und Werte begrenzen (Storage-DoS durch eingeloggten Client).
    valid_keys = {s.key for s in steps}
    unknown = [k for k in answers if k not in valid_keys]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unbekannte Antwort-Keys: {', '.join(unknown[:5])}")
    for k, v in answers.items():
        if isinstance(v, str) and len(v) > _MAX_ANSWER_STR:
            raise HTTPException(status_code=422, detail=f"Antwort '{k}' ist zu lang")
        if isinstance(v, list):
            if len(v) > _MAX_ANSWER_LIST:
                raise HTTPException(status_code=422, detail=f"Zu viele Werte bei '{k}'")
            if any(isinstance(item, str) and len(item) > _MAX_ANSWER_STR for item in v):
                raise HTTPException(status_code=422, detail=f"Antwort '{k}' ist zu lang")

    # Pflichtfelder prüfen (intro/bestaetigung erwarten keine Antwort)
    missing = [
        s.key for s in steps
        if s.pflichtfeld and s.typ not in _NON_ANSWER_TYPES and not _answered(answers.get(s.key))
    ]
    if missing:
        raise HTTPException(status_code=422, detail=f"Pflichtfelder fehlen: {', '.join(missing)}")

    overrides = lesson.checkin_overrides or {}
    week_index = overrides.get("week_index")

    # Upsert auf (user, lesson). Bearbeiten setzt synced_to_crm zurück → re-sync.
    resp = (await db.execute(
        select(CheckinResponse).where(
            CheckinResponse.user_id == user.id, CheckinResponse.lesson_id == lesson_id
        )
    )).scalar_one_or_none()
    now = utc_now()
    if resp:
        resp.answers = answers
        resp.status = "submitted"
        resp.submitted_at = now
        resp.week_index = week_index
        resp.template_typ = template.typ
        resp.synced_to_crm = False
    else:
        db.add(CheckinResponse(
            user_id=user.id,
            course_id=module.course_id,
            lesson_id=lesson_id,
            template_typ=template.typ,
            week_index=week_index,
            answers=answers,
            status="submitted",
            submitted_at=now,
        ))

    # Lektion als abgeschlossen markieren (zählt in den Fortschritt)
    progress = (await db.execute(
        select(LessonProgress).where(
            LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson_id
        )
    )).scalar_one_or_none()
    if progress:
        progress.completed = True
        progress.completed_at = now
    else:
        db.add(LessonProgress(user_id=user.id, lesson_id=lesson_id, completed=True, completed_at=now))

    # CRM-Sync nicht-blockierend über die Outbox anstoßen. In derselben
    # Transaktion wie die Antwort → entweder beides oder nichts (kein verlorener
    # Sync). Der Background-Loop (app/core/crm_sync.py) liefert ab.
    db.add(CrmOutbox(
        event_type="checkin_response",
        user_id=user.id,
        course_id=module.course_id,
        payload={
            "event_type": "checkin_response",
            "email": user.email,
            "user_id": user.id,
            "course_id": module.course_id,
            "lesson_id": lesson_id,
            "template_typ": template.typ,
            "week_index": week_index,
            "submitted_at": _iso_utc(now),
            "answers": answers,
        },
    ))

    return {"ok": True, "submitted_at": _iso_utc(now)}
