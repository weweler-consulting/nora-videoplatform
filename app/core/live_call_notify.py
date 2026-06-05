"""Mailt Nora eine 1-Klick-Freigabe-Mail für neu importierte (versteckte)
Live-Call-Lektionen. Sendet einmal pro Import (notified_at), best-effort."""
import logging

from sqlalchemy import select

from app.core import db as db_module
from app.core.config import settings
from app.core.email import send_simple_email
from app.core.live_call_token import create_action_token
from app.core.time import utc_now
from app.models.live_call import LiveCallImport

logger = logging.getLogger(__name__)

PLATFORM_BASE_URL = "https://kurse.noraweweler.de"
_warned = False


def _email_html(imp: LiveCallImport) -> str:
    approve = f"{PLATFORM_BASE_URL}/api/v1/live-calls/approve?import_id={imp.id}&token={create_action_token(imp.id, 'approve')}"
    dismiss = f"{PLATFORM_BASE_URL}/api/v1/live-calls/dismiss?import_id={imp.id}&token={create_action_token(imp.id, 'dismiss')}"
    datum = imp.occurrence_at.strftime("%d.%m.%Y") if imp.occurrence_at else "—"
    return f"""<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;">
  <p style="font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#D47479;">Neue Live-Call-Aufzeichnung</p>
  <h2 style="margin:6px 0;color:#303030;">Live-Call vom {datum}</h2>
  <p style="color:#555;">Die Aufzeichnung ist importiert und liegt als <b>versteckte</b> Lektion bereit.</p>
  <p style="margin:24px 0;">
    <a href="{approve}" style="background:#D47479;color:#fff;text-decoration:none;font-weight:700;padding:12px 22px;border-radius:6px;">Freigeben &amp; ank&uuml;ndigen</a>
    &nbsp;&nbsp;
    <a href="{dismiss}" style="color:#888;text-decoration:underline;font-size:14px;">Verwerfen</a>
  </p>
  <p style="color:#aaa;font-size:12px;">Erst nach „Freigeben" wird die Lektion sichtbar und die Kundinnen-Mail verschickt.</p>
</div>"""


async def notify_pending_imports() -> int:
    """Mailt Nora für status='imported' & notified_at IS NULL. Gibt Anzahl Mails zurück."""
    global _warned
    to = settings.live_call_notify_email
    if not to:
        if not _warned:
            logger.warning("Live-Call-Notify: NORA_LIVE_CALL_NOTIFY_EMAIL nicht gesetzt — keine Freigabe-Mails.")
            _warned = True
        return 0
    sent = 0
    async with db_module.async_session() as db:
        rows = (await db.execute(
            select(LiveCallImport).where(LiveCallImport.status == "imported", LiveCallImport.notified_at.is_(None))
        )).scalars().all()
        for imp in rows:
            datum = imp.occurrence_at.strftime("%d.%m.%Y") if imp.occurrence_at else ""
            try:
                if send_simple_email(to, f"Neue Live-Call-Aufzeichnung vom {datum} – freigeben?", _email_html(imp)):
                    imp.notified_at = utc_now()
                    sent += 1
            except Exception as e:
                logger.warning(f"Live-Call-Notify fehlgeschlagen ({imp.recording_name}): {e}")
        if sent:
            await db.commit()
    return sent
