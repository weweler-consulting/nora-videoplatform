"""Background-Loop: erkennt neue Recordings und importiert sie als versteckte
Lektionen. No-op ohne OAuth-Config oder Ordner-ID (loggt einmal)."""
import asyncio
import logging

from app.core.config import settings
from app.core.live_call_detector import detect_new_recordings
from app.core.live_call_importer import import_pending

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 20 * 60
_warned = False


async def live_call_loop():
    global _warned
    while True:
        try:
            if settings.google_oauth_configured and settings.meet_recordings_folder_id:
                await detect_new_recordings()
                await import_pending()
            elif not _warned:
                logger.warning("Live-Call-Import nicht konfiguriert (OAuth/Folder-ID) — Loop wartet.")
                _warned = True
        except Exception as e:
            logger.error(f"Live-Call-Loop-Fehler: {e}", exc_info=True)
        await asyncio.sleep(INTERVAL_SECONDS)
