import pytest

from app.models.course import Course, Module, Section, Lesson
from tests.test_checkin import _mk_user, _enroll, _auth


async def _course_with_hidden_lesson(session):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    module = Module(course_id=course.id, title="M", sort_order=0); session.add(module); await session.commit()
    section = Section(module_id=module.id, title="S", sort_order=0); session.add(section); await session.commit()
    visible = Lesson(section_id=section.id, title="Sichtbar", type="video", is_published=True, sort_order=0)
    hidden = Lesson(section_id=section.id, title="Versteckt", type="video", is_published=False, sort_order=1)
    session.add_all([visible, hidden]); await session.commit()
    return course


def _titles(resp_json):
    return [l["title"] for m in resp_json["modules"] for s in m["sections"] for l in s["lessons"]]


@pytest.mark.asyncio
async def test_hidden_lesson_excluded_for_client(client, session):
    course = await _course_with_hidden_lesson(session)
    user = await _mk_user(session, admin=False)
    await _enroll(session, user.id, course.id)
    r = await client.get(f"/api/v1/courses/{course.id}", headers=_auth(user))
    assert r.status_code == 200, r.text
    titles = _titles(r.json())
    assert "Sichtbar" in titles and "Versteckt" not in titles


@pytest.mark.asyncio
async def test_hidden_lesson_visible_for_admin(client, session):
    course = await _course_with_hidden_lesson(session)
    admin = await _mk_user(session, admin=True)
    r = await client.get(f"/api/v1/courses/admin/{course.id}", headers=_auth(admin))
    assert r.status_code == 200, r.text
    titles = _titles(r.json())
    assert "Sichtbar" in titles and "Versteckt" in titles
