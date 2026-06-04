"""Outbound CRM-Sync für Check-in-Antworten.

Muster wie drip_notifier: ein In-Process-asyncio-Loop arbeitet die crm_outbox ab,
POSTet an den nora-crm-Webhook (X-Webhook-Secret) und markiert erfolgreiche
Zeilen. Nicht-blockierend für die Player-UX (die Antwort liegt schon in der
video-platform); Retry über crm_outbox.retry_count.
"""
import asyncio
import logging

import httpx
from sqlalchemy import select, update

from app.core import db as db_module
from app.core.config import settings
from app.core.time import utc_now
from app.models.checkin import CrmOutbox, CheckinResponse

logger = logging.getLogger(__name__)

MAX_RETRIES = 10
BATCH_SIZE = 25
INTERVAL_SECONDS = 60
_warned_unconfigured = False


def _configured() -> bool:
    return bool(settings.crm_webhook_url and settings.crm_checkin_secret)


def _record_failure(row, error: str) -> None:
    """Fehlversuch zählen; beim Erreichen von MAX_RETRIES laut loggen, damit eine
    aufgegebene Zeile (z. B. Kontakt fehlt im CRM) nicht still verschwindet."""
    row.retry_count += 1
    row.last_error = error[:500]
    if row.retry_count >= MAX_RETRIES:
        logger.warning(
            f"CRM-Sync gibt auf nach {MAX_RETRIES} Versuchen: outbox={row.id} "
            f"lesson={row.payload.get('lesson_id')} email={row.payload.get('email')} ({error})"
        )


async def process_crm_outbox() -> int:
    """Eine Runde: offene Outbox-Zeilen abarbeiten. Gibt die Anzahl erfolgreich
    gesyncter Zeilen zurück."""
    global _warned_unconfigured
    if not _configured():
        if not _warned_unconfigured:
            logger.warning("CRM-Sync nicht konfiguriert (NORA_CRM_WEBHOOK_URL/NORA_CRM_CHECKIN_SECRET) — Outbox wartet.")
            _warned_unconfigured = True
        return 0

    async with db_module.async_session() as db:
        rows = (await db.execute(
            select(CrmOutbox)
            .where(CrmOutbox.synced_at.is_(None), CrmOutbox.retry_count < MAX_RETRIES)
            .order_by(CrmOutbox.created_at)  # älteste zuerst → letzter Stand gewinnt im CRM
            .limit(BATCH_SIZE)
        )).scalars().all()
        if not rows:
            return 0

        synced = 0
        async with httpx.AsyncClient(timeout=15.0) as client:
            for row in rows:
                try:
                    resp = await client.post(
                        settings.crm_webhook_url,
                        json=row.payload,
                        headers={"X-Webhook-Secret": settings.crm_checkin_secret},
                    )
                except Exception as e:  # Netzwerk/Timeout → retry
                    _record_failure(row, f"request: {type(e).__name__}")
                    continue

                if 200 <= resp.status_code < 300:  # jeder 2xx zählt (z. B. 202/204)
                    row.synced_at = utc_now()
                    # Best-effort Flag an der Antwort (oldest-first → konsistent)
                    if row.user_id and row.payload.get("lesson_id"):
                        await db.execute(
                            update(CheckinResponse)
                            .where(
                                CheckinResponse.user_id == row.user_id,
                                CheckinResponse.lesson_id == row.payload["lesson_id"],
                            )
                            .values(synced_to_crm=True)
                        )
                    synced += 1
                else:
                    # Nur Status, kein Response-Body → keine PII/Health-Daten im Log/DB.
                    _record_failure(row, f"http {resp.status_code}")

        await db.commit()
        if synced:
            logger.info(f"CRM-Sync: {synced} Check-in-Antwort(en) übertragen")
        return synced


async def crm_sync_loop():
    """Outbox alle INTERVAL_SECONDS abarbeiten."""
    while True:
        try:
            await process_crm_outbox()
        except Exception as e:
            logger.error(f"CRM-Sync-Loop-Fehler: {e}", exc_info=True)
        await asyncio.sleep(INTERVAL_SECONDS)
