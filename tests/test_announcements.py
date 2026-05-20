import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, hash_password
from app.models.course import Course, Enrollment, Module, Section, Lesson, Announcement
from app.models.user import User


async def _mk_user(session: AsyncSession, *, admin: bool = False, email: str | None = None) -> User:
    user = User(
        email=email or f"{uuid.uuid4().hex}@example.com",
        name="Test",
        hashed_password=hash_password("pw"),
        is_admin=admin,
    )
    session.add(user)
    await session.commit()
    return user


async def _mk_course(session: AsyncSession) -> Course:
    course = Course(title="Test Course", is_active=True)
    session.add(course)
    await session.commit()
    return course


async def _mk_module(session: AsyncSession, course_id: str, title: str = "Modul 1") -> Module:
    module = Module(course_id=course_id, title=title)
    session.add(module)
    await session.commit()
    return module


async def _mk_lesson(session: AsyncSession, module_id: str, title: str = "Lektion 1") -> Lesson:
    section = Section(module_id=module_id, title="Lektionen")
    session.add(section)
    await session.commit()
    lesson = Lesson(section_id=section.id, title=title)
    session.add(lesson)
    await session.commit()
    return lesson


async def _enroll(session: AsyncSession, user_id: str, course_id: str) -> None:
    session.add(Enrollment(user_id=user_id, course_id=course_id))
    await session.commit()


@pytest.mark.asyncio
async def test_create_announcement_requires_admin(client, session):
    user = await _mk_user(session, admin=False)
    course = await _mk_course(session)
    module = await _mk_module(session, course.id)
    token = create_access_token(user.id)
    r = await client.post(
        f"/api/v1/admin/courses/{course.id}/announcements",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_type": "module", "target_id": module.id, "subject": "s", "body": "b"},
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_announcement_module_persists_row_and_sends(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    module = await _mk_module(session, course.id)
    learner = await _mk_user(session)
    await _enroll(session, learner.id, course.id)

    token = create_access_token(admin.id)
    with patch("app.api.announcements.send_announcement_email", return_value=True) as mock_send:
        r = await client.post(
            f"/api/v1/admin/courses/{course.id}/announcements",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "target_type": "module",
                "target_id": module.id,
                "subject": "Neues Modul",
                "body": "Schau rein",
            },
        )

    assert r.status_code == 201, r.text
    data = r.json()
    assert data["announcement"]["target_type"] == "module"
    assert data["announcement"]["target_title"] == "Modul 1"
    assert data["announcement"]["recipient_count"] == 1
    assert data["delivery_summary"] == {"sent": 1, "failed": 0}
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_create_announcement_lesson_target_uses_lesson_cta_url(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    module = await _mk_module(session, course.id)
    lesson = await _mk_lesson(session, module.id)
    learner = await _mk_user(session)
    await _enroll(session, learner.id, course.id)

    token = create_access_token(admin.id)
    with patch("app.api.announcements.send_announcement_email", return_value=True) as mock_send:
        r = await client.post(
            f"/api/v1/admin/courses/{course.id}/announcements",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "target_type": "lesson",
                "target_id": lesson.id,
                "subject": "Neue Lektion",
                "body": "Schau rein",
            },
        )

    assert r.status_code == 201
    sent_kwargs = mock_send.call_args.kwargs
    assert f"/course/{course.id}/lesson/{lesson.id}" in sent_kwargs["cta_url"]
    assert r.json()["announcement"]["target_module_title"] == "Modul 1"


@pytest.mark.asyncio
async def test_create_announcement_rejects_target_from_other_course(client, session):
    admin = await _mk_user(session, admin=True)
    course_a = await _mk_course(session)
    course_b = await _mk_course(session)
    module_b = await _mk_module(session, course_b.id, title="Foreign")
    learner = await _mk_user(session)
    await _enroll(session, learner.id, course_a.id)

    token = create_access_token(admin.id)
    r = await client.post(
        f"/api/v1/admin/courses/{course_a.id}/announcements",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_type": "module", "target_id": module_b.id, "subject": "s", "body": "b"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_announcement_rejects_when_no_enrollments(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    module = await _mk_module(session, course.id)

    token = create_access_token(admin.id)
    r = await client.post(
        f"/api/v1/admin/courses/{course.id}/announcements",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_type": "module", "target_id": module.id, "subject": "s", "body": "b"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_preview_returns_suggestions_and_count(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    module = await _mk_module(session, course.id, title="Hormone")
    for _ in range(3):
        learner = await _mk_user(session)
        await _enroll(session, learner.id, course.id)

    token = create_access_token(admin.id)
    r = await client.get(
        f"/api/v1/admin/courses/{course.id}/announcements/preview",
        params={"target_type": "module", "target_id": module.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "Hormone" in data["suggested_subject"]
    assert data["recipient_count"] == 3
    assert data["target_title"] == "Hormone"


@pytest.mark.asyncio
async def test_list_announcements_returns_sorted_history(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    module = await _mk_module(session, course.id)
    learner = await _mk_user(session)
    await _enroll(session, learner.id, course.id)
    token = create_access_token(admin.id)

    with patch("app.api.announcements.send_announcement_email", return_value=True):
        for i in range(2):
            r = await client.post(
                f"/api/v1/admin/courses/{course.id}/announcements",
                headers={"Authorization": f"Bearer {token}"},
                json={"target_type": "module", "target_id": module.id, "subject": f"S{i}", "body": "b"},
            )
            assert r.status_code == 201

    r = await client.get(
        f"/api/v1/admin/courses/{course.id}/announcements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    items = r.json()["announcements"]
    assert len(items) == 2
    assert items[0]["sent_at"] >= items[1]["sent_at"]
    assert items[0]["target_title"] == "Modul 1"


@pytest.mark.asyncio
async def test_list_announcement_shows_null_title_when_target_deleted(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    module = await _mk_module(session, course.id)
    learner = await _mk_user(session)
    await _enroll(session, learner.id, course.id)
    token = create_access_token(admin.id)

    with patch("app.api.announcements.send_announcement_email", return_value=True):
        await client.post(
            f"/api/v1/admin/courses/{course.id}/announcements",
            headers={"Authorization": f"Bearer {token}"},
            json={"target_type": "module", "target_id": module.id, "subject": "s", "body": "b"},
        )

    # Modul löschen (direkt in DB)
    await session.delete(module)
    await session.commit()

    r = await client.get(
        f"/api/v1/admin/courses/{course.id}/announcements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    items = r.json()["announcements"]
    assert len(items) == 1
    assert items[0]["target_title"] is None
