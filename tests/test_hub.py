import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, hash_password
from app.models.course import Course, Enrollment
from app.models.hub import CourseHub, HubLink
from app.models.user import User


async def _mk_user(session: AsyncSession, *, admin: bool = False) -> User:
    user = User(email=f"{uuid.uuid4().hex}@example.com", name="T", hashed_password=hash_password("pw"), is_admin=admin)
    session.add(user)
    await session.commit()
    return user


async def _mk_course(session: AsyncSession) -> Course:
    course = Course(title="Test Course", is_active=True)
    session.add(course)
    await session.commit()
    return course


async def _mk_hub(session: AsyncSession, course_id: str) -> CourseHub:
    hub = CourseHub(course_id=course_id, hero_title_html="Hello", hero_eyebrow="Eyebrow")
    session.add(hub)
    await session.commit()
    return hub


@pytest.mark.asyncio
async def test_get_hub_requires_enrollment(client, session):
    user = await _mk_user(session)
    course = await _mk_course(session)
    await _mk_hub(session, course.id)
    token = create_access_token(user.id)
    r = await client.get(f"/api/v1/courses/{course.id}/hub",
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_hub_with_enrollment_returns_payload(client, session):
    user = await _mk_user(session)
    course = await _mk_course(session)
    hub = await _mk_hub(session, course.id)
    session.add(HubLink(hub_id=hub.id, icon_type="book", label="Kurs", sort_order=0))
    session.add(Enrollment(user_id=user.id, course_id=course.id))
    await session.commit()

    token = create_access_token(user.id)
    r = await client.get(f"/api/v1/courses/{course.id}/hub",
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["hero_eyebrow"] == "Eyebrow"
    assert len(data["links"]) == 1
    assert data["links"][0]["label"] == "Kurs"


@pytest.mark.asyncio
async def test_admin_sees_hub_without_enrollment(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    await _mk_hub(session, course.id)
    token = create_access_token(admin.id)
    r = await client.get(f"/api/v1/courses/{course.id}/hub",
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
