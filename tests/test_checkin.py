import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, hash_password
from app.core.checkin_seed import seed_checkin_templates
from app.models.course import Course, Module, Section, Lesson, Enrollment, LessonProgress
from app.models.checkin import CheckinResponse, CrmOutbox
from app.models.user import User
from sqlalchemy import select as _select


class _FakeResp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class _FakeClient:
    """Ersetzt httpx.AsyncClient im CRM-Sync-Test."""
    calls: list = []
    status: int = 200

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None, headers=None):
        _FakeClient.calls.append({"url": url, "json": json, "headers": headers})
        return _FakeResp(_FakeClient.status)


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


async def _enroll(session: AsyncSession, user_id: str, course_id: str) -> None:
    session.add(Enrollment(user_id=user_id, course_id=course_id))
    await session.commit()


@pytest.mark.asyncio
async def test_submit_checkin_marks_complete_and_persists(client, session):
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post(
        "/api/v1/checkin/modules", headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "laufend", "week_index": 1},
    )).json()
    lesson_id = created["lesson_id"]

    klientin = await _mk_user(session, admin=False)
    await _enroll(session, klientin.id, course.id)

    # Vor Submit: keine Antwort
    r0 = await client.get(f"/api/v1/checkin/lessons/{lesson_id}/response", headers=_auth(klientin))
    assert r0.json()["submitted"] is False

    # Pflichtfelder fehlen -> 422
    rbad = await client.post(
        f"/api/v1/checkin/lessons/{lesson_id}/submit", headers=_auth(klientin),
        json={"answers": {"win": "nur ein Win"}},
    )
    assert rbad.status_code == 422

    # Vollständig -> 200
    answers = {"wohlbefinden": 8, "energie": 7, "heisshunger": "weniger",
               "umsetzung": "5 Tage", "win": "mehr Energie", "huerde": "Wochenende"}
    rok = await client.post(
        f"/api/v1/checkin/lessons/{lesson_id}/submit", headers=_auth(klientin),
        json={"answers": answers},
    )
    assert rok.status_code == 200, rok.text

    # Lektion gilt als abgeschlossen
    prog = (await session.execute(_select(LessonProgress).where(
        LessonProgress.user_id == klientin.id, LessonProgress.lesson_id == lesson_id))).scalar_one_or_none()
    assert prog is not None and prog.completed is True

    # Antwort persistiert + read-only abrufbar
    r1 = await client.get(f"/api/v1/checkin/lessons/{lesson_id}/response", headers=_auth(klientin))
    data = r1.json()
    assert data["submitted"] is True
    assert data["answers"]["wohlbefinden"] == 8
    assert data["week_index"] == 1

    # Response-Zeile mit synced_to_crm=False (für Phase-4-Sync)
    resp = (await session.execute(_select(CheckinResponse).where(
        CheckinResponse.user_id == klientin.id, CheckinResponse.lesson_id == lesson_id))).scalar_one()
    assert resp.synced_to_crm is False
    assert resp.template_typ == "laufend"


@pytest.mark.asyncio
async def test_submit_requires_enrollment(client, session):
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post(
        "/api/v1/checkin/modules", headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "start"},
    )).json()
    lesson_id = created["lesson_id"]

    fremd = await _mk_user(session, admin=False)  # nicht eingeschrieben
    r = await client.post(
        f"/api/v1/checkin/lessons/{lesson_id}/submit", headers=_auth(fremd),
        json={"answers": {"hauptziel": ["Mehr Energie"], "energie": 5,
                          "nachmittagstief": "selten", "heisshunger": "selten",
                          "fruehstueck_status": "herzhaft & eiweißreich"}},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_edit_resubmit_updates_and_resets_sync(client, session):
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post(
        "/api/v1/checkin/modules", headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "laufend", "week_index": 2},
    )).json()
    lesson_id = created["lesson_id"]
    klientin = await _mk_user(session, admin=False)
    await _enroll(session, klientin.id, course.id)

    base = {"wohlbefinden": 5, "energie": 5, "heisshunger": "gleich"}
    await client.post(f"/api/v1/checkin/lessons/{lesson_id}/submit", headers=_auth(klientin),
                      json={"answers": base})
    # Sync simulieren
    resp = (await session.execute(_select(CheckinResponse).where(
        CheckinResponse.lesson_id == lesson_id))).scalar_one()
    resp.synced_to_crm = True
    await session.commit()

    # Bearbeiten -> neue Werte, synced_to_crm zurückgesetzt (re-sync)
    await client.post(f"/api/v1/checkin/lessons/{lesson_id}/submit", headers=_auth(klientin),
                      json={"answers": {**base, "wohlbefinden": 9}})
    await session.refresh(resp)
    assert resp.answers["wohlbefinden"] == 9
    assert resp.synced_to_crm is False


@pytest.mark.asyncio
async def test_submit_enqueues_crm_outbox(client, session):
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post(
        "/api/v1/checkin/modules", headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "laufend", "week_index": 1},
    )).json()
    lesson_id = created["lesson_id"]
    klientin = await _mk_user(session, admin=False)
    await _enroll(session, klientin.id, course.id)

    await client.post(f"/api/v1/checkin/lessons/{lesson_id}/submit", headers=_auth(klientin),
                      json={"answers": {"wohlbefinden": 6, "energie": 6, "heisshunger": "gleich"}})

    rows = (await session.execute(_select(CrmOutbox))).scalars().all()
    assert len(rows) == 1
    p = rows[0].payload
    assert p["event_type"] == "checkin_response"
    assert p["email"] == klientin.email
    assert p["lesson_id"] == lesson_id
    assert p["template_typ"] == "laufend"
    assert p["week_index"] == 1
    assert p["answers"]["wohlbefinden"] == 6
    assert rows[0].synced_at is None


@pytest.mark.asyncio
async def test_crm_sync_processes_outbox(client, session, monkeypatch):
    from app.core import crm_sync
    from app.core.config import settings

    # CRM-Sync konfigurieren + httpx faken
    monkeypatch.setattr(settings, "crm_webhook_url", "https://crm.test/api/webhooks/course-checkin")
    monkeypatch.setattr(settings, "crm_checkin_secret", "shhh-secret")
    _FakeClient.calls = []
    _FakeClient.status = 200
    monkeypatch.setattr(crm_sync.httpx, "AsyncClient", _FakeClient)

    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post(
        "/api/v1/checkin/modules", headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "start"},
    )).json()
    lesson_id = created["lesson_id"]
    klientin = await _mk_user(session, admin=False)
    await _enroll(session, klientin.id, course.id)
    await client.post(f"/api/v1/checkin/lessons/{lesson_id}/submit", headers=_auth(klientin),
                      json={"answers": {"hauptziel": ["Mehr Energie"], "energie": 7,
                                        "nachmittagstief": "selten", "heisshunger": "selten",
                                        "fruehstueck_status": "herzhaft & eiweißreich"}})

    n = await crm_sync.process_crm_outbox()
    assert n == 1
    # POST mit Secret-Header an die konfigurierte URL
    assert len(_FakeClient.calls) == 1
    call = _FakeClient.calls[0]
    assert call["url"] == "https://crm.test/api/webhooks/course-checkin"
    assert call["headers"]["X-Webhook-Secret"] == "shhh-secret"
    assert call["json"]["email"] == klientin.email

    # Outbox-Zeile als gesynct markiert, Antwort-Flag gesetzt
    outbox = (await session.execute(_select(CrmOutbox))).scalars().all()
    assert outbox[0].synced_at is not None
    resp = (await session.execute(_select(CheckinResponse).where(
        CheckinResponse.lesson_id == lesson_id))).scalar_one()
    assert resp.synced_to_crm is True


@pytest.mark.asyncio
async def test_crm_sync_retries_on_failure(client, session, monkeypatch):
    from app.core import crm_sync
    from app.core.config import settings

    monkeypatch.setattr(settings, "crm_webhook_url", "https://crm.test/hook")
    monkeypatch.setattr(settings, "crm_checkin_secret", "s")
    _FakeClient.calls = []
    _FakeClient.status = 500
    monkeypatch.setattr(crm_sync.httpx, "AsyncClient", _FakeClient)

    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post(
        "/api/v1/checkin/modules", headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "start"},
    )).json()
    klientin = await _mk_user(session, admin=False)
    await _enroll(session, klientin.id, course.id)
    await client.post(f"/api/v1/checkin/lessons/{created['lesson_id']}/submit", headers=_auth(klientin),
                      json={"answers": {"hauptziel": ["Mehr Energie"], "energie": 7,
                                        "nachmittagstief": "selten", "heisshunger": "selten",
                                        "fruehstueck_status": "herzhaft & eiweißreich"}})

    n = await crm_sync.process_crm_outbox()
    assert n == 0
    outbox = (await session.execute(_select(CrmOutbox))).scalars().all()
    assert outbox[0].synced_at is None
    assert outbox[0].retry_count == 1
    assert "http 500" in (outbox[0].last_error or "")
