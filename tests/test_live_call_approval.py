import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course, Module, Section, Lesson, Announcement
from app.models.live_call import LiveCallSeries, LiveCallImport
from app.core.live_call_token import create_action_token
import app.api.live_calls as lc
from tests.test_checkin import _mk_user, _enroll


async def _imported(session):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    module = Module(course_id=course.id, title="Live Call 02.10.2026", sort_order=0); session.add(module); await session.commit()
    section = Section(module_id=module.id, title="Aufzeichnung", sort_order=0); session.add(section); await session.commit()
    lesson = Lesson(section_id=section.id, title="Live-Call 02.10.2026", type="video",
                    video_url="https://iframe.mediadelivery.net/embed/1/v", is_published=False, sort_order=0)
    session.add(lesson); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="P"); session.add(series); await session.commit()
    imp = LiveCallImport(series_id=series.id, drive_file_id="f1", recording_name="P - 2026/10/02 19:14 WEST - Recording",
                         occurrence_at=datetime(2026, 10, 2, 19, 14), status="imported", module_id=module.id, lesson_id=lesson.id)
    session.add(imp); await session.commit()
    return course, lesson, imp


@pytest.mark.asyncio
async def test_approve_publishes_and_announces(client, session, monkeypatch):
    course, lesson, imp = await _imported(session)
    klientin = await _mk_user(session, admin=False); await _enroll(session, klientin.id, course.id)
    sent = []
    monkeypatch.setattr(lc, "send_announcement_email", lambda **k: sent.append(k.get("to_email")) or True)

    tok = create_action_token(imp.id, "approve")
    # GET zeigt nur die Bestätigungsseite — darf NICHTS ändern (Anti-Prefetch).
    g = await client.get(f"/api/v1/live-calls/approve?import_id={imp.id}&token={tok}")
    assert g.status_code == 200
    session.expunge_all()
    assert (await session.execute(_select(Lesson).where(Lesson.id == lesson.id))).scalar_one().is_published is False
    assert sent == []

    # POST führt aus.
    r = await client.post("/api/v1/live-calls/approve", data={"import_id": imp.id, "token": tok})
    assert r.status_code == 200

    session.expunge_all()
    les = (await session.execute(_select(Lesson).where(Lesson.id == lesson.id))).scalar_one()
    assert les.is_published is True
    row = (await session.execute(_select(LiveCallImport).where(LiveCallImport.id == imp.id))).scalar_one()
    assert row.status == "published" and row.published_at is not None
    assert klientin.email in sent
    ann = (await session.execute(_select(Announcement).where(Announcement.target_id == lesson.id))).scalar_one()
    assert ann.target_type == "lesson"

    # Idempotent: erneut POST → keine zweite Ankündigung
    sent.clear()
    r2 = await client.post("/api/v1/live-calls/approve", data={"import_id": imp.id, "token": tok})
    assert r2.status_code == 200 and sent == []


@pytest.mark.asyncio
async def test_approve_bad_token(client, session):
    _course, _lesson, imp = await _imported(session)
    r = await client.post("/api/v1/live-calls/approve", data={"import_id": imp.id, "token": "falsch"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_announcement_only_to_mailable(client, session, monkeypatch):
    """Inaktive, Admins und Nutzer ohne Passwort werden NICHT angeschrieben."""
    course, lesson, imp = await _imported(session)
    active = await _mk_user(session, admin=False); await _enroll(session, active.id, course.id)
    admin = await _mk_user(session, admin=True); await _enroll(session, admin.id, course.id)
    inactive = await _mk_user(session, admin=False); inactive.is_active = False
    await session.commit(); await _enroll(session, inactive.id, course.id)
    sent = []
    monkeypatch.setattr(lc, "send_announcement_email", lambda **k: sent.append(k.get("to_email")) or True)

    tok = create_action_token(imp.id, "approve")
    r = await client.post("/api/v1/live-calls/approve", data={"import_id": imp.id, "token": tok})
    assert r.status_code == 200
    assert sent == [active.email]  # nur die aktive Klientin, nicht Admin/inaktiv
