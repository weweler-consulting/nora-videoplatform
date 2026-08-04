"""Parsing der Meet-Recording-Dateinamen der Gruppen-Live-Calls.

Schema (Video):  "<Prefix> - YYYY/MM/DD [HH:MM <TZ>] - Recording"
Beispiele:       "Live Call | Glukose Balance - 2026/06/04 19:14 WEST - Recording"
                 "Live Call | Glukose Balance - 2026/04/30 - Recording"

Die Uhrzeit ist optional — die real von Meet erzeugten Namen enthalten oft nur
das Datum (so alle bisherigen Prod-Recordings).

Der Prefix ist kurs-spezifisch und trennt Gruppen-Live-Calls von 1:1-Calls/
Beratungsgesprächen im selben Ordner. Video vs. Notizen-Doc wird über den
mimeType in der Drive-Query getrennt, nicht hier.
"""
import re
from datetime import datetime

# Datum mit / oder - als Trenner (Meet hat die Schreibweise über die Jahre variiert).
_DATE_RE = re.compile(r"(\d{4})[/-](\d{2})[/-](\d{2})(?:\s+(\d{2}):(\d{2}))?")
_DRIVE_TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})")


def parse_occurrence_at(name: str) -> datetime | None:
    """Datum (+ optionale Uhrzeit, sonst 00:00) als naive lokale Wandzeit aus dem
    Namen ziehen; None ohne Treffer."""
    m = _DATE_RE.search(name)
    if not m:
        return None
    y, mo, d, h, mi = (int(g) if g is not None else 0 for g in m.groups())
    try:
        return datetime(y, mo, d, h, mi)
    except ValueError:
        return None


def occurrence_from_drive_file(f: dict) -> datetime | None:
    """Termin-Zeitpunkt einer Drive-Datei: bevorzugt aus dem Namen, sonst als
    Rückfallebene der Upload-Zeitpunkt (createdTime, UTC).

    Ohne Zeitpunkt setzt der Importer die Zeile hart auf 'failed' (kein Retry) —
    ändert Google also nochmal das Namensschema, ist der Upload-Zeitpunkt die
    deutlich bessere Näherung als ein Totalausfall: Meet lädt direkt nach dem Call
    hoch, das Datum stimmt damit praktisch immer."""
    return parse_occurrence_at(f.get("name", "")) or _parse_drive_timestamp(f.get("createdTime"))


def _parse_drive_timestamp(value: str | None) -> datetime | None:
    """RFC-3339-UTC-Zeitstempel der Drive-API als naive Wandzeit (Datum zählt)."""
    if not value:
        return None
    m = _DRIVE_TS_RE.match(value)
    if not m:
        return None
    try:
        return datetime(*(int(g) for g in m.groups()))
    except ValueError:
        return None


def is_group_recording(name: str, prefix: str) -> bool:
    """True, wenn der Name mit dem kurs-spezifischen Prefix beginnt."""
    return name.startswith(prefix)
