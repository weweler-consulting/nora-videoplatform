import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course, Module, Section, Lesson
from app.models.live_call import LiveCallSeries, LiveCallImport
from app.core.live_call_token import create_action_token
import app.api.live_calls as lc


@pytest.mark.asyncio
async def test_dismiss_deletes_lesson_and_video(client, session, monkeypatch):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    module = Module(course_id=course.id, title="M", sort_order=0); session.add(module); await session.commit()
    section = Section(module_id=module.id, title="S", sort_order=0); session.add(section); await session.commit()
    lesson = Lesson(section_id=section.id, title="L", type="video",
                    video_url="https://iframe.mediadelivery.net/embed/1/v", is_published=False, sort_order=0)
    session.add(lesson); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="P"); session.add(series); await session.commit()
    imp = LiveCallImport(series_id=series.id, drive_file_id="f1", recording_name="P - 2026/10/02 19:14 WEST - Recording",
                         occurrence_at=datetime(2026, 10, 2, 19, 14), status="imported", module_id=module.id, lesson_id=lesson.id)
    session.add(imp); await session.commit()
    lesson_id = lesson.id

    deleted = []
    monkeypatch.setattr(lc, "delete_video_by_embed_url", lambda url: deleted.append(url))

    tok = create_action_token(imp.id, "dismiss")
    r = await client.get(f"/api/v1/live-calls/dismiss?import_id={imp.id}&token={tok}")
    assert r.status_code == 200

    session.expunge_all()
    assert (await session.execute(_select(Lesson).where(Lesson.id == lesson_id))).scalar_one_or_none() is None
    assert deleted == ["https://iframe.mediadelivery.net/embed/1/v"]
    row = (await session.execute(_select(LiveCallImport).where(LiveCallImport.id == imp.id))).scalar_one()
    assert row.status == "dismissed"
