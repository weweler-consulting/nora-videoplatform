"""Read-only-Backup aller Check-in-Daten aus der Produktions-DB (Cloudron).

Schreibt einen wiederherstellbaren JSON-Snapshot der Check-in-Tabellen — allen
voran `checkin_responses` (die von Klientinnen ausgefüllten Antworten, die nicht
verloren gehen dürfen). `checkin_templates` und `checkin_steps` sind mit drin,
damit der Snapshot selbsterklärend und vollständig wiederherstellbar ist.

Sicher: führt ausschließlich SELECTs aus, schreibt nichts in die DB.

Verwendung (im kurse Cloudron-Container, vom App-Root `/app`):
    python3 scripts/backup_checkins.py
    python3 scripts/backup_checkins.py /app/data/checkin_backup.json

Ohne Pfad-Argument wird `./checkin_backup_<UTC-Zeitstempel>.json` geschrieben.
Verbindet via asyncpg direkt zu CLOUDRON_POSTGRESQL_URL (wie scripts/sql.py),
ohne den FastAPI-Config-Layer (kein NORA_SECRET_KEY o. Ä. nötig).
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import asyncpg

# Reihenfolge bewusst: Antworten zuerst (die schützenswerten Nutzerdaten),
# danach die Konfiguration (Templates/Steps).
TABLES = ["checkin_responses", "checkin_templates", "checkin_steps"]


async def _dump_table(conn: asyncpg.Connection, table: str) -> list:
    """Eine Tabelle als Liste von Zeilen-Dicts. row_to_json serialisiert jede
    Spalte korrekt (jsonb -> verschachteltes JSON, Timestamps -> ISO-8601);
    ::text, damit asyncpg garantiert einen String liefert, den wir einmal parsen.
    Tabellenname ist eine feste Konstante aus TABLES (keine Nutzereingabe)."""
    raw = await conn.fetchval(
        f"SELECT coalesce(json_agg(row_to_json(t)), '[]'::json)::text FROM {table} t"
    )
    return json.loads(raw)


async def main() -> None:
    url = os.environ.get("CLOUDRON_POSTGRESQL_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("CLOUDRON_POSTGRESQL_URL not set in environment", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    out_path = sys.argv[1] if len(sys.argv) > 1 else f"checkin_backup_{stamp}.json"

    conn = await asyncpg.connect(url)
    try:
        snapshot = {
            "exported_at": now.isoformat(),
            "tables": {table: await _dump_table(conn, table) for table in TABLES},
        }
    finally:
        await conn.close()

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    counts = ", ".join(f"{t}={len(snapshot['tables'][t])}" for t in TABLES)
    print(f"Backup geschrieben: {os.path.abspath(out_path)}")
    print(f"Zeilen: {counts}")


if __name__ == "__main__":
    asyncio.run(main())
