import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course, Lesson
from app.models.live_call import LiveCallSeries, LiveCallImport
from app.core import live_call_importer


@pytest.mark.asyncio
async def test_import_creates_hidden_lesson(session, monkeypatch):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="P"); session.add(series); await session.commit()
    imp = LiveCallImport(series_id=series.id, drive_file_id="f1",
                         recording_name="P - 2026/10/02 19:14 WEST - Recording",
                         occurrence_at=datetime(2026, 10, 2, 19, 14), status="new")
    session.add(imp); await session.commit()

    # Drive-Download + Bunny-Upload mocken (kein echtes Netz)
    monkeypatch.setattr(live_call_importer, "download_to_file", lambda fid, path: open(path, "wb").close())
    monkeypatch.setattr(live_call_importer, "upload_video_from_file",
                        lambda title, path: "https://iframe.mediadelivery.net/embed/1/vid")

    assert await live_call_importer.import_pending() == 1

    session.expire_all()
    row = (await session.execute(_select(LiveCallImport).where(LiveCallImport.drive_file_id == "f1"))).scalar_one()
    assert row.status == "imported" and row.lesson_id is not None and row.module_id is not None
    lesson = (await session.execute(_select(Lesson).where(Lesson.id == row.lesson_id))).scalar_one()
    assert lesson.type == "video" and lesson.is_published is False
    assert lesson.video_url == "https://iframe.mediadelivery.net/embed/1/vid"

    # Idempotent: schon 'imported' → kein zweiter Durchlauf, keine zweite Lektion
    assert await live_call_importer.import_pending() == 0
    rows = (await session.execute(_select(Lesson).where(Lesson.section_id == lesson.section_id))).scalars().all()
    assert len(rows) == 1
