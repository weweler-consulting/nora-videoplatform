import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course
from app.models.live_call import LiveCallSeries, LiveCallImport
from app.core import live_call_notify


@pytest.mark.asyncio
async def test_notify_sends_once_and_marks(session, monkeypatch):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="P"); session.add(series); await session.commit()
    imp = LiveCallImport(series_id=series.id, drive_file_id="f1", recording_name="P - 2026/10/02 19:14 WEST - Recording",
                         occurrence_at=datetime(2026, 10, 2, 19, 14), status="imported", lesson_id="les-1")
    session.add(imp); await session.commit()

    sent = []
    monkeypatch.setattr(live_call_notify, "send_simple_email", lambda to, subject, html: sent.append((to, subject, html)) or True)
    monkeypatch.setattr(live_call_notify.settings, "live_call_notify_email", "nora@noraweweler.de", raising=False)

    assert await live_call_notify.notify_pending_imports() == 1
    assert len(sent) == 1 and sent[0][0] == "nora@noraweweler.de"
    assert "approve?import_id=" in sent[0][2] and "dismiss?import_id=" in sent[0][2]

    session.expire_all()
    row = (await session.execute(_select(LiveCallImport).where(LiveCallImport.drive_file_id == "f1"))).scalar_one()
    assert row.notified_at is not None

    # Zweiter Lauf: schon notified → keine zweite Mail
    assert await live_call_notify.notify_pending_imports() == 0
