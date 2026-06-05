"""Verarbeitet 'new' LiveCallImport-Zeilen → versteckte Video-Lektion im richtigen
Kurs. Drive→Temp→Bunny gestreamt; jeder Schritt idempotent; Fehler → retry."""
import logging
import os
import tempfile

from sqlalchemy import select

from app.core import db as db_module
from app.core.live_call_placement import resolve_target_section
from app.integrations.google_drive import download_to_file
from app.integrations.bunny_stream import upload_video_from_file
from app.models.course import Lesson
from app.models.live_call import LiveCallSeries, LiveCallImport

logger = logging.getLogger(__name__)

MAX_RETRIES = 5


async def import_pending() -> int:
    """Alle 'new'-Importe verarbeiten. Gibt die Anzahl erfolgreich importierter zurück."""
    done = 0
    async with db_module.async_session() as db:
        rows = (await db.execute(
            select(LiveCallImport).where(
                LiveCallImport.status == "new", LiveCallImport.retry_count < MAX_RETRIES
            )
        )).scalars().all()
        for imp in rows:
            try:
                await _import_one(db, imp)
                done += 1
            except Exception as e:
                imp.retry_count += 1
                imp.last_error = str(e)[:500]
                if imp.retry_count >= MAX_RETRIES:
                    imp.status = "failed"
                    logger.warning(f"Live-Call-Import gibt auf: {imp.recording_name} ({e})")
                await db.commit()
        if done:
            logger.info(f"Live-Call-Importer: {done} Recording(s) importiert (versteckt)")
    return done


async def _import_one(db, imp: LiveCallImport) -> None:
    series = (await db.execute(
        select(LiveCallSeries).where(LiveCallSeries.id == imp.series_id)
    )).scalar_one()
    if imp.occurrence_at is None:
        raise ValueError("kein Datum im Recording-Namen geparst")

    section_id, module_id = await resolve_target_section(db, series.course_id, imp.occurrence_at)
    title = f"Live-Call {imp.occurrence_at.strftime('%d.%m.%Y')}"

    tmp = os.path.join(tempfile.gettempdir(), f"livecall_{imp.drive_file_id}.mp4")
    try:
        download_to_file(imp.drive_file_id, tmp)
        embed_url = upload_video_from_file(title, tmp)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    lesson = Lesson(
        section_id=section_id, title=title, type="video",
        video_url=embed_url, is_published=False, sort_order=0,
    )
    db.add(lesson)
    await db.flush()

    imp.module_id = module_id
    imp.lesson_id = lesson.id
    imp.status = "imported"
    await db.commit()
