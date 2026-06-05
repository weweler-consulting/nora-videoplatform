"""Findet neue Meet-Recordings im Drive-Ordner und legt LiveCallImport-Zeilen an.
Dedup über drive_file_id → mehrfaches Laufen erzeugt keine Duplikate."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core import db as db_module
from app.core.config import settings
from app.core.live_call_parser import parse_occurrence_at, is_group_recording
from app.integrations.google_drive import list_video_files
from app.models.live_call import LiveCallSeries, LiveCallImport

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 21


async def detect_new_recordings() -> int:
    """Pro aktiver Serie den Ordner pollen, neue Videos als 'new'-Import anlegen.
    Gibt die Anzahl neu angelegter Zeilen zurück."""
    folder = settings.meet_recordings_folder_id
    if not folder:
        return 0
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    created = 0
    async with db_module.async_session() as db:
        series_rows = (await db.execute(
            select(LiveCallSeries).where(LiveCallSeries.active.is_(True))
        )).scalars().all()
        known = set((await db.execute(select(LiveCallImport.drive_file_id))).scalars().all())

        for series in series_rows:
            try:
                files = list_video_files(folder, series.recording_name_prefix, since)
            except Exception as e:  # Drive/Auth-Fehler → diese Runde überspringen
                logger.warning(f"Live-Call-Detector: Drive-Listing fehlgeschlagen ({series.recording_name_prefix}): {e}")
                continue
            for f in files:
                fid = f["id"]
                if fid in known or not is_group_recording(f["name"], series.recording_name_prefix):
                    continue
                db.add(LiveCallImport(
                    series_id=series.id, drive_file_id=fid, recording_name=f["name"],
                    occurrence_at=parse_occurrence_at(f["name"]), status="new",
                ))
                known.add(fid)
                created += 1
        if created:
            await db.commit()
            logger.info(f"Live-Call-Detector: {created} neue Recording(s) erkannt")
    return created
