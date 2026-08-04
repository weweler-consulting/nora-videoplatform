from datetime import datetime

from app.core.live_call_parser import (
    parse_occurrence_at,
    is_group_recording,
    occurrence_from_drive_file,
)


def test_parse_occurrence_at_group_recording():
    name = "Live Call | Glukose Balance - 2026/06/04 19:14 WEST - Recording"
    assert parse_occurrence_at(name) == datetime(2026, 6, 4, 19, 14)


def test_parse_occurrence_at_handles_notizen_name():
    # Notizen-Doc trägt dasselbe Datum; mimeType-Filter trennt Video/Doc,
    # aber der Parser muss das Datum trotzdem sauber ziehen.
    name = "Live Call | Glukose Balance – 2026/05/28 19:14 WEST – Notizen von Nora"
    assert parse_occurrence_at(name) == datetime(2026, 5, 28, 19, 14)


def test_parse_occurrence_at_date_only_recording():
    # Reales Prod-Namensformat: Meet liefert oft KEINE Uhrzeit im Dateinamen.
    name = "Live Call | Glukose Balance - 2026/04/30 - Recording"
    assert parse_occurrence_at(name) == datetime(2026, 4, 30, 0, 0)


def test_parse_occurrence_at_date_only_vier_wochen_kurs():
    name = "4-Wochen Glukose Balance Code Live Call - 2026/06/10 - Recording"
    assert parse_occurrence_at(name) == datetime(2026, 6, 10, 0, 0)


def test_parse_occurrence_at_returns_none_without_date():
    assert parse_occurrence_at("Irgendein Dokument ohne Datum") is None


def test_parse_occurrence_at_accepts_dashed_date():
    # Absicherung, falls Meet auf ISO-Schreibweise umstellt.
    name = "Live Call 4 Wochen Glukose Balance Code (Start Aug 2026) - 2026-08-04 - Recording"
    assert parse_occurrence_at(name) == datetime(2026, 8, 4, 0, 0)


def test_occurrence_from_drive_file_prefers_name():
    f = {"name": "Live Call | Glukose Balance - 2026/04/30 - Recording",
         "createdTime": "2026-05-02T09:00:00.000Z"}
    assert occurrence_from_drive_file(f) == datetime(2026, 4, 30, 0, 0)


def test_occurrence_from_drive_file_falls_back_to_created_time():
    # Ohne Datum im Namen würde der Importer die Zeile hart auf 'failed' setzen —
    # der Upload-Zeitpunkt ist die brauchbare Näherung.
    f = {"name": "Live Call 4 Wochen Glukose Balance Code (Start Aug 2026)",
         "createdTime": "2026-08-04T17:42:11.000Z"}
    assert occurrence_from_drive_file(f) == datetime(2026, 8, 4, 17, 42)


def test_occurrence_from_drive_file_none_without_any_hint():
    assert occurrence_from_drive_file({"name": "Ohne alles"}) is None


def test_is_group_recording_matches_prefix():
    prefix = "Live Call | Glukose Balance"
    assert is_group_recording("Live Call | Glukose Balance - 2026/06/04 19:14 WEST - Recording", prefix) is True


def test_is_group_recording_excludes_one_on_one():
    prefix = "Live Call | Glukose Balance"
    assert is_group_recording("Glukose Balance Coaching - Kathi x Nora - 2026/06/03 11:01 WEST - Recording", prefix) is False
