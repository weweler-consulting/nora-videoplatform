import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course
from app.models.live_call import LiveCallSeries, LiveCallImport
from app.core import live_call_detector


@pytest.mark.asyncio
async def test_detect_creates_rows_dedup(session, monkeypatch):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="4-Wochen Glukose Balance Code Live Call")
    session.add(series); await session.commit()

    fake = [
        {"id": "f1", "name": "4-Wochen Glukose Balance Code Live Call - 2026/10/02 19:14 WEST - Recording",
         "mimeType": "video/mp4", "modifiedTime": "2026-10-02T17:14:00Z"},
    ]
    monkeypatch.setattr(live_call_detector, "list_video_files", lambda folder, prefix, since: fake)
    monkeypatch.setattr(live_call_detector.settings, "meet_recordings_folder_id", "FOLDER", raising=False)

    n = await live_call_detector.detect_new_recordings()
    assert n == 1
    row = (await session.execute(_select(LiveCallImport).where(LiveCallImport.drive_file_id == "f1"))).scalar_one()
    assert row.status == "new"
    assert row.occurrence_at == datetime(2026, 10, 2, 19, 14)

    # Zweiter Lauf: Dedup über drive_file_id → kein zweiter Eintrag
    assert await live_call_detector.detect_new_recordings() == 0
