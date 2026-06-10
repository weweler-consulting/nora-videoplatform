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

_DATE_RE = re.compile(r"(\d{4})/(\d{2})/(\d{2})(?:\s+(\d{2}):(\d{2}))?")


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


def is_group_recording(name: str, prefix: str) -> bool:
    """True, wenn der Name mit dem kurs-spezifischen Prefix beginnt."""
    return name.startswith(prefix)
