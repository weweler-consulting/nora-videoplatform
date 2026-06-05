"""Outbound CRM-Sync für Check-in-Antworten.

Muster wie drip_notifier: ein In-Process-asyncio-Loop arbeitet die crm_outbox ab,
POSTet an den nora-crm-Webhook (X-Webhook-Secret) und markiert erfolgreiche
Zeilen. Nicht-blockierend für die Player-UX (die Antwort liegt schon in der
video-platform); Retry über crm_outbox.retry_count.
"""
import asyncio
import logging
from datetime import timedelta

import httpx
from sqlalchemy import select, update, delete

from app.core import db as db_module
from app.core.config import settings
from app.core.time import utc_now
from app.models.checkin import CrmOutbox, CheckinResponse

logger = logging.getLogger(__name__)

MAX_RETRIES = 10
BATCH_SIZE = 25
INTERVAL_SECONDS = 60
# Gesyncte Outbox-Zeilen nach dieser Frist löschen (Daten liegen dann im CRM +
# in checkin_responses → redundant). Geparkte Fehlversuche bleiben unberührt.
OUTBOX_RETENTION_DAYS = 30
_PRUNE_EVERY_N_CYCLES = max(1, 3600 // INTERVAL_SECONDS)  # ~stündlich
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


async def prune_crm_outbox(retention_days: int = OUTBOX_RETENTION_DAYS) -> int:
    """Löscht erfolgreich gesyncte Outbox-Zeilen, die älter als retention_days
    sind — die Daten liegen dann im CRM UND in checkin_responses, die Zeile ist
    redundant (und hält PII vor). GEPARKTE Fehlversuche (synced_at IS NULL)
    bleiben: sie signalisieren nicht zugestellte Daten und sollen sichtbar sein."""
    cutoff = utc_now() - timedelta(days=retention_days)
    async with db_module.async_session() as db:
        result = await db.execute(
            delete(CrmOutbox).where(
                CrmOutbox.synced_at.is_not(None),
                CrmOutbox.synced_at < cutoff,
            )
        )
        await db.commit()
        deleted = result.rowcount or 0
        if deleted:
            logger.info(f"CRM-Outbox-Prune: {deleted} gesyncte Zeile(n) älter als {retention_days}d gelöscht")
        return deleted


async def crm_sync_loop():
    """Outbox alle INTERVAL_SECONDS abarbeiten; ~stündlich gesyncte Altzeilen prunen."""
    cycle = 0
    while True:
        try:
            await process_crm_outbox()
            if cycle % _PRUNE_EVERY_N_CYCLES == 0:
                await prune_crm_outbox()
        except Exception as e:
            logger.error(f"CRM-Sync-Loop-Fehler: {e}", exc_info=True)
        cycle += 1
        await asyncio.sleep(INTERVAL_SECONDS)
