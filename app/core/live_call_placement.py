"""Hybride Platzierung: füllt ein dat. 'Live Call <Datum>'-Platzhaltermodul ohne
Video-Lektion, sonst legt es ein neues Modul am Ende an. Gibt (section_id, module_id)."""
from datetime import datetime

from sqlalchemy import select, func

from app.models.course import Module, Section, Lesson


def _date_variants(d: datetime) -> list[str]:
    """DE-Datumsformate, die in Modultiteln vorkommen können."""
    return [
        d.strftime("%d.%m.%Y"),   # 02.10.2026
        d.strftime("%-d.%-m.%Y"), # 2.10.2026
        d.strftime("%d.%m."),     # 02.10.
        d.strftime("%-d.%-m."),   # 2.10.
    ]


async def _find_placeholder(db, course_id: str, occurrence_at: datetime):
    """Ein Modul des Kurses, dessen Titel das Datum enthält und das keine Video-
    Lektion hat. None, wenn keins passt."""
    variants = _date_variants(occurrence_at)
    modules = (await db.execute(select(Module).where(Module.course_id == course_id))).scalars().all()
    for m in modules:
        title = m.title or ""
        if not any(v in title for v in variants):
            continue
        n_videos = (await db.execute(
            select(func.count(Lesson.id))
            .join(Section, Lesson.section_id == Section.id)
            .where(Section.module_id == m.id, Lesson.type == "video")
        )).scalar_one()
        if n_videos == 0:
            return m
    return None


async def _ensure_section(db, module_id: str) -> str:
    sec = (await db.execute(
        select(Section).where(Section.module_id == module_id).order_by(Section.sort_order)
    )).scalars().first()
    if sec:
        return sec.id
    sec = Section(module_id=module_id, title="Aufzeichnung", sort_order=0)
    db.add(sec)
    await db.flush()
    return sec.id


async def resolve_target_section(db, course_id: str, occurrence_at: datetime) -> tuple[str, str]:
    """(section_id, module_id) für die Live-Call-Lektion."""
    placeholder = await _find_placeholder(db, course_id, occurrence_at)
    if placeholder is not None:
        return await _ensure_section(db, placeholder.id), placeholder.id

    next_order = ((await db.execute(
        select(func.max(Module.sort_order)).where(Module.course_id == course_id)
    )).scalar() or 0) + 1
    module = Module(course_id=course_id, title=f"Live Call {occurrence_at.strftime('%d.%m.%Y')}", sort_order=next_order)
    db.add(module)
    await db.flush()
    section_id = await _ensure_section(db, module.id)
    return section_id, module.id
