import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, hash_password
from app.core.checkin_seed import seed_checkin_templates
from app.models.course import Course, Module, Section, Lesson
from app.models.user import User


async def _mk_user(session: AsyncSession, *, admin: bool = False) -> User:
    user = User(
        email=f"{uuid.uuid4().hex}@example.com",
        name="Test",
        hashed_password=hash_password("pw"),
        is_admin=admin,
    )
    session.add(user)
    await session.commit()
    return user


async def _mk_course(session: AsyncSession) -> Course:
    course = Course(title="4-Wochen Test", is_active=True)
    session.add(course)
    await session.commit()
    return course


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.mark.asyncio
async def test_list_templates_after_seed(client, session):
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    r = await client.get("/api/v1/checkin/templates", headers=_auth(admin))
    assert r.status_code == 200
    typen = {t["typ"] for t in r.json()}
    assert {"start", "laufend"} <= typen


@pytest.mark.asyncio
async def test_create_checkin_module_requires_admin(client, session):
    await seed_checkin_templates()
    user = await _mk_user(session, admin=False)
    course = await _mk_course(session)
    r = await client.post(
        "/api/v1/checkin/modules",
        headers=_auth(user),
        json={"course_id": course.id, "template_typ": "start"},
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_checkin_module_builds_module_section_lesson(client, session):
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)

    r = await client.post(
        "/api/v1/checkin/modules",
        headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "laufend", "week_index": 1},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    lesson_id = body["lesson_id"]

    # Lektion ist type='checkin' mit Template-Verweis
    lesson = (await session.execute(
        Lesson.__table__.select().where(Lesson.id == lesson_id)
    )).first()
    assert lesson is not None

    # Admin-Kurs-Tree zeigt das Modul als Check-in
    r2 = await client.get(f"/api/v1/courses/admin/{course.id}", headers=_auth(admin))
    assert r2.status_code == 200
    mod = r2.json()["modules"][0]
    assert mod["is_checkin"] is True
    assert mod["checkin_typ"] == "laufend"
    assert mod["checkin_week_index"] == 1
    assert mod["checkin_lesson_id"] == lesson_id
    inner = mod["sections"][0]["lessons"][0]
    assert inner["type"] == "checkin"


@pytest.mark.asyncio
async def test_get_and_override_checkin_lesson(client, session):
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post(
        "/api/v1/checkin/modules",
        headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "laufend", "week_index": 1},
    )).json()
    lesson_id = created["lesson_id"]

    # Default-Frage der Umsetzungsfrage steht
    r = await client.get(f"/api/v1/checkin/lessons/{lesson_id}", headers=_auth(admin))
    assert r.status_code == 200
    data = r.json()
    assert data["template_typ"] == "laufend"
    assert data["week_index"] == 1
    umsetzung = next(s for s in data["steps"] if s["key"] == "umsetzung")
    assert "blutzuckerfreundlich" in umsetzung["frage"]
    assert umsetzung["overridden"] is False
    # Stabile Kern-Keys vorhanden
    keys = {s["key"] for s in data["steps"]}
    assert {"wohlbefinden", "energie", "heisshunger", "umsetzung"} <= keys

    # Override der Wochenfrage + week_index ändern
    r2 = await client.put(
        f"/api/v1/checkin/lessons/{lesson_id}",
        headers=_auth(admin),
        json={
            "week_index": 2,
            "title": "Check-in Woche 2",
            "step_overrides": {
                "umsetzung": {"frage": "Wie oft hast du die Reihenfolge umgesetzt?"}
            },
        },
    )
    assert r2.status_code == 200

    r3 = await client.get(f"/api/v1/checkin/lessons/{lesson_id}", headers=_auth(admin))
    data3 = r3.json()
    assert data3["week_index"] == 2
    assert data3["title"] == "Check-in Woche 2"
    ums = next(s for s in data3["steps"] if s["key"] == "umsetzung")
    assert ums["frage"] == "Wie oft hast du die Reihenfolge umgesetzt?"
    assert ums["overridden"] is True
    # Andere Keys unverändert (Vergleichbarkeit bleibt)
    energie = next(s for s in data3["steps"] if s["key"] == "energie")
    assert energie["overridden"] is False


@pytest.mark.asyncio
async def test_module_reorder_persists(client, session):
    """Modul-Reorder nutzt das bestehende PUT /modules/{id} mit sort_order."""
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    # ein Video-Modul + ein Check-in-Modul
    vid = (await client.post("/api/v1/modules/", headers=_auth(admin),
                             json={"course_id": course.id, "title": "Live Call", "sort_order": 0})).json()
    chk = (await client.post("/api/v1/checkin/modules", headers=_auth(admin),
                             json={"course_id": course.id, "template_typ": "start"})).json()

    # tauschen: Check-in nach vorne
    await client.put(f"/api/v1/modules/{chk['module_id']}", headers=_auth(admin), json={"sort_order": 0})
    await client.put(f"/api/v1/modules/{vid['id']}", headers=_auth(admin), json={"sort_order": 1})

    r = await client.get(f"/api/v1/courses/admin/{course.id}", headers=_auth(admin))
    mods = r.json()["modules"]
    assert mods[0]["is_checkin"] is True
    assert mods[1]["is_checkin"] is False
