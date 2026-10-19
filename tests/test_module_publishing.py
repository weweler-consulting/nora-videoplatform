"""Modul-Entwurf/Live: Nora baut Module in Ruhe, Kundinnen sehen nur Live-Module."""
from datetime import datetime

import pytest
from sqlalchemy import select

import app.api.live_calls as lc
import app.core.db as db_module
import app.core.drip_notifier as drip
from app.core.auth import hash_password
from app.core.live_call_token import create_action_token
from app.models.course import Course, Module, Section, Lesson
from app.models.live_call import LiveCallSeries, LiveCallImport
from tests.test_checkin import _mk_user, _enroll, _auth
from tests.test_drip_notifier import _setup, _drip_count


def _module_titles(resp_json):
    return [m["title"] for m in resp_json["modules"]]


async def _course_with_new_module(client, session):
    admin = await _mk_user(session, admin=True)
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    live = Module(course_id=course.id, title="Live", sort_order=0); session.add(live); await session.commit()
    sec = Section(module_id=live.id, title="S", sort_order=0); session.add(sec); await session.commit()
    session.add(Lesson(section_id=sec.id, title="L1", type="video", sort_order=0)); await session.commit()
    r = await client.post("/api/v1/modules/", headers=_auth(admin),
                          json={"course_id": course.id, "title": "In Arbeit", "sort_order": 1})
    assert r.status_code == 200, r.text
    draft_id = r.json()["id"]
    dsec = Section(module_id=draft_id, title="S", sort_order=0); session.add(dsec); await session.commit()
    session.add(Lesson(section_id=dsec.id, title="L2", type="video", sort_order=0)); await session.commit()
    return admin, course, draft_id


@pytest.mark.asyncio
async def test_new_module_is_draft_and_hidden_from_client(client, session):
    admin, course, draft_id = await _course_with_new_module(client, session)
    klientin = await _mk_user(session, admin=False)
    await _enroll(session, klientin.id, course.id)

    r = await client.get(f"/api/v1/courses/{course.id}", headers=_auth(klientin))
    assert _module_titles(r.json()) == ["Live"]
    assert r.json()["total_lessons"] == 1

    listing = (await client.get("/api/v1/courses/", headers=_auth(klientin))).json()
    assert listing[0]["total_lessons"] == 1

    ra = await client.get(f"/api/v1/courses/admin/{course.id}", headers=_auth(admin))
    mods = {m["title"]: m for m in ra.json()["modules"]}
    assert mods["In Arbeit"]["is_published"] is False
    assert mods["Live"]["is_published"] is True


@pytest.mark.asyncio
async def test_publish_makes_module_visible(client, session):
    admin, course, draft_id = await _course_with_new_module(client, session)
    klientin = await _mk_user(session, admin=False)
    await _enroll(session, klientin.id, course.id)

    r = await client.put(f"/api/v1/modules/{draft_id}", headers=_auth(admin), json={"is_published": True})
    assert r.status_code == 200
    r = await client.get(f"/api/v1/courses/{course.id}", headers=_auth(klientin))
    assert _module_titles(r.json()) == ["Live", "In Arbeit"]


@pytest.mark.asyncio
async def test_client_cannot_complete_lesson_in_draft(client, session):
    admin, course, draft_id = await _course_with_new_module(client, session)
    klientin = await _mk_user(session, admin=False)
    await _enroll(session, klientin.id, course.id)
    lesson = (await session.execute(
        select(Lesson).join(Section).where(Section.module_id == draft_id)
    )).scalar_one()
    r = await client.post(f"/api/v1/progress/{lesson.id}/complete", headers=_auth(klientin))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_announcement_for_draft_module_rejected(client, session):
    admin, course, draft_id = await _course_with_new_module(client, session)
    r = await client.post(
        f"/api/v1/admin/courses/{course.id}/announcements", headers=_auth(admin),
        json={"target_type": "module", "target_id": draft_id, "subject": "Neu", "body": "Hallo"},
    )
    assert r.status_code == 422
    assert "Entwurf" in r.json()["detail"]


@pytest.mark.asyncio
async def test_drip_skips_draft_module(engine, session, monkeypatch):
    monkeypatch.setattr(drip, "async_session", db_module.async_session)
    calls = []
    monkeypatch.setattr(drip, "send_module_unlocked_email", lambda **kw: calls.append(kw) or True)
    user, module = await _setup(session, hashed_password=hash_password("x"))
    module.is_published = False
    await session.commit()

    await drip.check_drip_notifications()

    assert calls == []
    assert await _drip_count(session, user.id) == 0


@pytest.mark.asyncio
async def test_live_call_approval_publishes_draft_module(client, session, monkeypatch):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    module = Module(course_id=course.id, title="Live Call 02.10.2026", sort_order=0, is_published=False)
    session.add(module); await session.commit()
    section = Section(module_id=module.id, title="Aufzeichnung", sort_order=0); session.add(section); await session.commit()
    lesson = Lesson(section_id=section.id, title="Live-Call", type="video",
                    video_url="https://iframe.mediadelivery.net/embed/1/v", is_published=False, sort_order=0)
    session.add(lesson); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="P"); session.add(series); await session.commit()
    imp = LiveCallImport(series_id=series.id, drive_file_id="f1", recording_name="P - Recording",
                         occurrence_at=datetime(2026, 10, 2, 19, 14), status="imported",
                         module_id=module.id, lesson_id=lesson.id)
    session.add(imp); await session.commit()
    monkeypatch.setattr(lc, "send_announcement_email", lambda **k: True)

    tok = create_action_token(imp.id, "approve")
    r = await client.post("/api/v1/live-calls/approve", data={"import_id": imp.id, "token": tok})
    assert r.status_code == 200

    session.expunge_all()
    assert (await session.execute(select(Module).where(Module.id == module.id))).scalar_one().is_published is True
