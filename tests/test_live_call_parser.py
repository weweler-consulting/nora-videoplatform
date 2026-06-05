from datetime import datetime

from app.core.live_call_parser import parse_occurrence_at, is_group_recording


def test_parse_occurrence_at_group_recording():
    name = "Live Call | Glukose Balance - 2026/06/04 19:14 WEST - Recording"
    assert parse_occurrence_at(name) == datetime(2026, 6, 4, 19, 14)


def test_parse_occurrence_at_handles_notizen_name():
    # Notizen-Doc trägt dasselbe Datum; mimeType-Filter trennt Video/Doc,
    # aber der Parser muss das Datum trotzdem sauber ziehen.
    name = "Live Call | Glukose Balance – 2026/05/28 19:14 WEST – Notizen von Nora"
    assert parse_occurrence_at(name) == datetime(2026, 5, 28, 19, 14)


def test_parse_occurrence_at_returns_none_without_date():
    assert parse_occurrence_at("Irgendein Dokument ohne Datum") is None


def test_is_group_recording_matches_prefix():
    prefix = "Live Call | Glukose Balance"
    assert is_group_recording("Live Call | Glukose Balance - 2026/06/04 19:14 WEST - Recording", prefix) is True


def test_is_group_recording_excludes_one_on_one():
    prefix = "Live Call | Glukose Balance"
    assert is_group_recording("Glukose Balance Coaching - Kathi x Nora - 2026/06/03 11:01 WEST - Recording", prefix) is False
