"""Verarbeitet 'new' LiveCallImport-Zeilen → versteckte Video-Lektion im richtigen
Kurs. Drive→Temp→Bunny gestreamt; blockierende I/O läuft in Threads (Event-Loop
bleibt frei); I/O VOR DB-Writes; jeder Schritt idempotent; Fehler → retry."""
import asyncio
import logging
import os
import tempfile

from sqlalchemy import select, update

from app.core import db as db_module
from app.core.live_call_placement import resolve_target_section
from app.integrations.google_drive import download_to_file
from app.integrations.bunny_stream import upload_video_from_file, delete_video_by_embed_url
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
            # Kein Datum geparst → deterministisch nicht importierbar, direkt 'failed'
            # (statt 5 Retries zu verbrennen).
            if imp.occurrence_at is None:
                imp.status = "failed"
                imp.last_error = "kein Datum im Recording-Namen geparst"
                await db.commit()
                continue
            # Werte VOR dem try sichern — nach einem rollback sind ORM-Attribute
            # expired (async-Lazy-Load wäre heikel); id ist PK und bleibt gültig.
            imp_id, prev_retry, rec_name = imp.id, imp.retry_count, imp.recording_name
            try:
                await _import_one(db, imp)
                done += 1
            except Exception as e:
                await db.rollback()
                new_retry = prev_retry + 1
                vals = {"retry_count": new_retry, "last_error": str(e)[:500]}
                if new_retry >= MAX_RETRIES:
                    vals["status"] = "failed"
                    logger.warning(f"Live-Call-Import gibt auf: {rec_name} ({e})")
                await db.execute(update(LiveCallImport).where(LiveCallImport.id == imp_id).values(**vals))
                await db.commit()
        if done:
            logger.info(f"Live-Call-Importer: {done} Recording(s) importiert (versteckt)")
    return done


async def _import_one(db, imp: LiveCallImport) -> None:
    series = (await db.execute(
        select(LiveCallSeries).where(LiveCallSeries.id == imp.series_id)
    )).scalar_one()
    title = f"Live-Call {imp.occurrence_at.strftime('%d.%m.%Y')}"

    # Blockierende I/O ZUERST und in Threads — der Event-Loop bleibt frei, und ein
    # Download-/Upload-Fehler hinterlässt KEINE halb-angelegten DB-Zeilen.
    tmp = os.path.join(tempfile.gettempdir(), f"livecall_{imp.drive_file_id}.mp4")
    try:
        await asyncio.to_thread(download_to_file, imp.drive_file_id, tmp)
        embed_url = await asyncio.to_thread(upload_video_from_file, title, tmp)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    # Ab hier DB-Writes. Schlägt etwas fehl, das hochgeladene Bunny-Video wieder
    # löschen (sonst Waise) und sauber rollbacken.
    try:
        section_id, module_id, module_created = await resolve_target_section(db, series.course_id, imp.occurrence_at)
        lesson = Lesson(
            section_id=section_id, title=title, type="video",
            video_url=embed_url, is_published=False, sort_order=0,
        )
        db.add(lesson)
        await db.flush()
        imp.module_id = module_id
        imp.module_created = module_created
        imp.lesson_id = lesson.id
        imp.status = "imported"
        await db.commit()
    except Exception:
        await db.rollback()
        await asyncio.to_thread(delete_video_by_embed_url, embed_url)
        raise
