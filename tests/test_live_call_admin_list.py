import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course, Module, Section, Lesson
from app.models.live_call import LiveCallSeries, LiveCallImport
import app.api.live_calls as lc
from tests.test_checkin import _mk_user, _enroll, _auth


@pytest.mark.asyncio
async def test_admin_list_and_approve(client, session, monkeypatch):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    module = Module(course_id=course.id, title="M", sort_order=0); session.add(module); await session.commit()
    section = Section(module_id=module.id, title="S", sort_order=0); session.add(section); await session.commit()
    lesson = Lesson(section_id=section.id, title="L", type="video", video_url="x", is_published=False, sort_order=0)
    session.add(lesson); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="P"); session.add(series); await session.commit()
    imp = LiveCallImport(series_id=series.id, drive_file_id="f1", recording_name="P - 2026/10/02 19:14 WEST - Recording",
                         occurrence_at=datetime(2026, 10, 2, 19, 14), status="imported", module_id=module.id, lesson_id=lesson.id)
    session.add(imp); await session.commit()
    imp_id = imp.id

    admin = await _mk_user(session, admin=True)
    klientin = await _mk_user(session, admin=False); await _enroll(session, klientin.id, course.id)
    monkeypatch.setattr(lc, "send_announcement_email", lambda **k: True)

    r = await client.get("/api/v1/live-calls/imports?status=imported", headers=_auth(admin))
    assert r.status_code == 200 and any(i["id"] == imp_id for i in r.json())

    r2 = await client.post(f"/api/v1/live-calls/imports/{imp_id}/approve", headers=_auth(admin))
    assert r2.status_code == 200
    session.expunge_all()
    assert (await session.execute(_select(LiveCallImport).where(LiveCallImport.id == imp_id))).scalar_one().status == "published"


@pytest.mark.asyncio
async def test_admin_list_requires_admin(client, session):
    user = await _mk_user(session, admin=False)
    r = await client.get("/api/v1/live-calls/imports", headers=_auth(user))
    assert r.status_code in (401, 403)
