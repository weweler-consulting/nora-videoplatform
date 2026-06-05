import uuid
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crm_sync import prune_crm_outbox
from app.core.time import utc_now

from app.core.auth import create_access_token, hash_password
from app.core.checkin_seed import (
    seed_checkin_templates,
    sync_checkin_default_texts,
    migrate_laufend_step_keys,
)
from app.models.checkin import CheckinTemplate, CheckinStep
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
    assert {"start", "laufend", "ende"} <= typen


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
    assert {"wohlbefinden", "energie", "heisshunger_trend", "umsetzung"} <= keys

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
    answers = {"wohlbefinden": 8, "energie": 7, "heisshunger_trend": "weniger",
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

    base = {"wohlbefinden": 5, "energie": 5, "heisshunger_trend": "gleich"}
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
                      json={"answers": {"wohlbefinden": 6, "energie": 6, "heisshunger_trend": "gleich"}})

    rows = (await session.execute(_select(CrmOutbox))).scalars().all()
    assert len(rows) == 1
    p = rows[0].payload
    assert p["event_type"] == "checkin_response"
    assert p["email"] == klientin.email
    assert p["lesson_id"] == lesson_id
    assert p["template_typ"] == "laufend"
    assert p["week_index"] == 1
    assert p["answers"]["wohlbefinden"] == 6
    assert p["submitted_at"].endswith("Z")  # offset-aware → CRM parst als UTC
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


# ---- Review-Fixes 1-6 ----

@pytest.mark.asyncio
async def test_create_checkin_module_sort_order_is_max_plus_one(client, session):
    """Fix 1: nach einem Modul mit hohem sort_order (Lücke nach Löschungen) bekommt
    der neue Check-in max+1, nicht len → keine Kollision."""
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    session.add(Module(course_id=course.id, title="Bestehend", sort_order=5))
    await session.commit()

    created = (await client.post(
        "/api/v1/checkin/modules", headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "start"},
    )).json()
    mod = (await session.execute(_select(Module).where(Module.id == created["module_id"]))).scalar_one()
    assert mod.sort_order == 6


@pytest.mark.asyncio
async def test_get_checkin_lesson_requires_enrollment(client, session):
    """Fix 3: GET /checkin/lessons/{id} ist enrollment-geschützt."""
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post(
        "/api/v1/checkin/modules", headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "start"},
    )).json()
    lesson_id = created["lesson_id"]

    fremd = await _mk_user(session, admin=False)
    r = await client.get(f"/api/v1/checkin/lessons/{lesson_id}", headers=_auth(fremd))
    assert r.status_code == 403

    await _enroll(session, fremd.id, course.id)
    r2 = await client.get(f"/api/v1/checkin/lessons/{lesson_id}", headers=_auth(fremd))
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_submit_rejects_unknown_keys_and_oversized(client, session):
    """Fix 5: unbekannte Keys + überlange Werte → 422."""
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

    base = {"wohlbefinden": 7, "energie": 7, "heisshunger_trend": "gleich"}
    r = await client.post(f"/api/v1/checkin/lessons/{lesson_id}/submit", headers=_auth(klientin),
                          json={"answers": {**base, "boeser_key": "x"}})
    assert r.status_code == 422
    r2 = await client.post(f"/api/v1/checkin/lessons/{lesson_id}/submit", headers=_auth(klientin),
                           json={"answers": {**base, "win": "a" * 6000}})
    assert r2.status_code == 422
    # gültig bleibt gültig
    r3 = await client.post(f"/api/v1/checkin/lessons/{lesson_id}/submit", headers=_auth(klientin),
                           json={"answers": base})
    assert r3.status_code == 200


@pytest.mark.asyncio
async def test_submit_orphaned_lesson_returns_409(client, session):
    """Fix 6: verwaiste Check-in-Lektion (Modul fehlt) → sauberes 409 statt FK-500."""
    from sqlalchemy import delete
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post(
        "/api/v1/checkin/modules", headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "start"},
    )).json()
    await session.execute(delete(Module).where(Module.id == created["module_id"]))
    await session.commit()

    r = await client.post(f"/api/v1/checkin/lessons/{created['lesson_id']}/submit", headers=_auth(admin),
                          json={"answers": {"hauptziel": ["Mehr Energie"], "energie": 5,
                                            "nachmittagstief": "selten", "heisshunger": "selten",
                                            "fruehstueck_status": "herzhaft & eiweißreich"}})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_crm_sync_accepts_204(client, session, monkeypatch):
    """Fix 4: jeder 2xx (z. B. 204) zählt als Erfolg."""
    from app.core import crm_sync
    from app.core.config import settings
    monkeypatch.setattr(settings, "crm_webhook_url", "https://crm.test/hook")
    monkeypatch.setattr(settings, "crm_checkin_secret", "s")
    _FakeClient.calls = []
    _FakeClient.status = 204
    monkeypatch.setattr(crm_sync.httpx, "AsyncClient", _FakeClient)

    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post("/api/v1/checkin/modules", headers=_auth(admin),
                                 json={"course_id": course.id, "template_typ": "start"})).json()
    klientin = await _mk_user(session, admin=False)
    await _enroll(session, klientin.id, course.id)
    await client.post(f"/api/v1/checkin/lessons/{created['lesson_id']}/submit", headers=_auth(klientin),
                      json={"answers": {"hauptziel": ["Mehr Energie"], "energie": 7,
                                        "nachmittagstief": "selten", "heisshunger": "selten",
                                        "fruehstueck_status": "herzhaft & eiweißreich"}})
    n = await crm_sync.process_crm_outbox()
    assert n == 1
    ob = (await session.execute(_select(CrmOutbox))).scalars().first()
    assert ob.synced_at is not None


@pytest.mark.asyncio
async def test_crm_sync_parks_after_max_retries(client, session, monkeypatch):
    """Fix 4: nach MAX_RETRIES wird die Zeile geparkt (nicht mehr gepostet)."""
    from app.core import crm_sync
    from app.core.config import settings
    monkeypatch.setattr(settings, "crm_webhook_url", "https://crm.test/hook")
    monkeypatch.setattr(settings, "crm_checkin_secret", "s")
    _FakeClient.calls = []
    _FakeClient.status = 404
    monkeypatch.setattr(crm_sync.httpx, "AsyncClient", _FakeClient)

    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post("/api/v1/checkin/modules", headers=_auth(admin),
                                 json={"course_id": course.id, "template_typ": "start"})).json()
    klientin = await _mk_user(session, admin=False)
    await _enroll(session, klientin.id, course.id)
    await client.post(f"/api/v1/checkin/lessons/{created['lesson_id']}/submit", headers=_auth(klientin),
                      json={"answers": {"hauptziel": ["Mehr Energie"], "energie": 7,
                                        "nachmittagstief": "selten", "heisshunger": "selten",
                                        "fruehstueck_status": "herzhaft & eiweißreich"}})
    ob = (await session.execute(_select(CrmOutbox))).scalars().one()
    ob.retry_count = crm_sync.MAX_RETRIES - 1
    await session.commit()

    n = await crm_sync.process_crm_outbox()
    assert n == 0
    await session.refresh(ob)
    assert ob.retry_count == crm_sync.MAX_RETRIES
    assert ob.synced_at is None
    # Zeile wird ab jetzt ignoriert
    n2 = await crm_sync.process_crm_outbox()
    assert n2 == 0
    assert len(_FakeClient.calls) == 1


@pytest.mark.asyncio
async def test_submit_includes_ordered_questions_in_outbox(client, session):
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post(
        "/api/v1/checkin/modules", headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "laufend", "week_index": 1},
    )).json()
    lesson_id = created["lesson_id"]
    await client.put(f"/api/v1/checkin/lessons/{lesson_id}", headers=_auth(admin),
                     json={"step_overrides": {"umsetzung": {"frage": "Eigene Wochenfrage?"}}})

    klientin = await _mk_user(session, admin=False)
    await _enroll(session, klientin.id, course.id)
    await client.post(f"/api/v1/checkin/lessons/{lesson_id}/submit", headers=_auth(klientin),
                      json={"answers": {"wohlbefinden": 8, "energie": 6, "heisshunger_trend": "gleich"}})

    row = (await session.execute(_select(CrmOutbox).order_by(CrmOutbox.created_at.desc()))).scalars().first()
    questions = row.payload["questions"]
    typen = [q["typ"] for q in questions]
    assert "intro" not in typen and "bestaetigung" not in typen
    keys = [q["key"] for q in questions]
    assert keys[:3] == ["wohlbefinden", "energie", "heisshunger_trend"]
    wohl = next(q for q in questions if q["key"] == "wohlbefinden")
    assert wohl["typ"] == "skala" and wohl["skala_max"] == 10
    ums = next(q for q in questions if q["key"] == "umsetzung")
    assert ums["frage"] == "Eigene Wochenfrage?"
    # optionen wird mitgeschickt: Auswahl-Fragen tragen ihre Optionsliste,
    # Skalen haben keine (None) — erlaubt dem CRM, Skalen zu unterscheiden.
    assert all("optionen" in q for q in questions)
    choice = next(q for q in questions if q["typ"] == "einfachauswahl")
    assert isinstance(choice["optionen"], list) and len(choice["optionen"]) > 0
    assert wohl["optionen"] is None


@pytest.mark.asyncio
async def test_submit_ende_checkin_mirrors_start_and_captures_upsell(client, session):
    """Abschluss-Formular: gespiegelte keys (energie/heisshunger/nachmittagstief)
    fürs Vorher/Nachher + premium_interesse als CRM-Datenpunkt."""
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post(
        "/api/v1/checkin/modules", headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "ende"},
    )).json()
    lesson_id = created["lesson_id"]

    klientin = await _mk_user(session, admin=False)
    await _enroll(session, klientin.id, course.id)

    # Pflichtfelder = die gespiegelten Skalen/Auswahlen; offene Felder optional.
    answers = {
        "energie": 9,
        "nachmittagstief": "selten",
        "heisshunger": "nie",
        "rueckblick": "Viel mehr Energie, kein Nachmittagstief mehr.",
        "premium_interesse": "Ja, erzähl mir mehr",
    }
    rok = await client.post(
        f"/api/v1/checkin/lessons/{lesson_id}/submit", headers=_auth(klientin),
        json={"answers": answers},
    )
    assert rok.status_code == 200, rok.text

    # Response-Zeile trägt template_typ='ende'
    resp = (await session.execute(_select(CheckinResponse).where(
        CheckinResponse.user_id == klientin.id, CheckinResponse.lesson_id == lesson_id))).scalar_one()
    assert resp.template_typ == "ende"

    # CRM-Payload: template_typ='ende', gespiegelte keys vorhanden (Vorher/Nachher),
    # Upsell-Interesse als erfasster Datenpunkt.
    row = (await session.execute(_select(CrmOutbox).order_by(CrmOutbox.created_at.desc()))).scalars().first()
    assert row.payload["template_typ"] == "ende"
    assert row.payload["answers"]["premium_interesse"] == "Ja, erzähl mir mehr"
    qkeys = {q["key"] for q in row.payload["questions"]}
    assert {"energie", "heisshunger", "nachmittagstief", "premium_interesse"} <= qkeys


@pytest.mark.asyncio
async def test_sync_default_texts_lifts_old_laufend_wording(client, session):
    """Live-Korrektur: alte win/huerde-Defaults werden angehoben, nur solange
    sie noch den alten Text tragen (sonst No-op -> manuelle Edits bleiben)."""
    await seed_checkin_templates()

    async def _frage(key: str) -> str:
        # sync_checkin_default_texts() committet in einer eigenen Session;
        # expire_all() zwingt die Test-Session, frisch aus der DB zu lesen.
        session.expire_all()
        row = (await session.execute(_select(CheckinStep).join(
            CheckinTemplate, CheckinStep.template_id == CheckinTemplate.id).where(
            CheckinTemplate.typ == "laufend", CheckinStep.key == key))).scalar_one()
        return row.frage

    # Simuliere den Live-Altzustand (DB wurde vor der Text-Änderung geseedet).
    for key, old in [("win", "Dein größter Win diese Woche?"),
                     ("huerde", "Wo hast du gehakt?")]:
        step = (await session.execute(_select(CheckinStep).join(
            CheckinTemplate, CheckinStep.template_id == CheckinTemplate.id).where(
            CheckinTemplate.typ == "laufend", CheckinStep.key == key))).scalar_one()
        step.frage = old
    await session.commit()

    await sync_checkin_default_texts()
    assert await _frage("win") == "Dein größter Erfolg diese Woche?"
    assert await _frage("huerde") == "Wo hat es nicht geklappt?"

    # Idempotent + schützt manuelle Edits: ein abweichender Text bleibt unangetastet.
    custom = (await session.execute(_select(CheckinStep).join(
        CheckinTemplate, CheckinStep.template_id == CheckinTemplate.id).where(
        CheckinTemplate.typ == "laufend", CheckinStep.key == "win"))).scalar_one()
    custom.frage = "Mein eigener Text"
    await session.commit()
    await sync_checkin_default_texts()
    assert await _frage("win") == "Mein eigener Text"


@pytest.mark.asyncio
async def test_migrate_laufend_heisshunger_key_renames_everywhere(client, session):
    """Eindeutiger laufend-Key: heisshunger -> heisshunger_trend zieht Template-
    Step, historische Antworten und Lesson-Overrides mit; start bleibt unberührt."""
    await seed_checkin_templates()
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    created = (await client.post(
        "/api/v1/checkin/modules", headers=_auth(admin),
        json={"course_id": course.id, "template_typ": "laufend", "week_index": 1},
    )).json()
    lesson_id = created["lesson_id"]
    klientin = await _mk_user(session, admin=False)

    async def _laufend_step_keys() -> set:
        session.expire_all()
        rows = (await session.execute(_select(CheckinStep.key).join(
            CheckinTemplate, CheckinStep.template_id == CheckinTemplate.id).where(
            CheckinTemplate.typ == "laufend"))).scalars().all()
        return set(rows)

    # --- Alten DB-Zustand simulieren (vor der Umbenennung geseedet) ---
    step = (await session.execute(_select(CheckinStep).join(
        CheckinTemplate, CheckinStep.template_id == CheckinTemplate.id).where(
        CheckinTemplate.typ == "laufend", CheckinStep.key == "heisshunger_trend"))).scalar_one()
    step.key = "heisshunger"
    lesson = (await session.execute(_select(Lesson).where(Lesson.id == lesson_id))).scalar_one()
    lesson.checkin_overrides = {"week_index": 1, "steps": {"heisshunger": {"frage": "Custom?"}}}
    session.add(CheckinResponse(
        user_id=klientin.id, course_id=course.id, lesson_id=lesson_id,
        template_typ="laufend", week_index=1,
        answers={"wohlbefinden": 5, "heisshunger": "weniger"},
    ))
    await session.commit()
    assert "heisshunger" in await _laufend_step_keys()

    # --- Migration ---
    await migrate_laufend_step_keys()

    # Template-Step umbenannt
    keys = await _laufend_step_keys()
    assert "heisshunger_trend" in keys and "heisshunger" not in keys
    # Historische Antwort umbenannt (verlustfrei)
    resp = (await session.execute(_select(CheckinResponse).where(
        CheckinResponse.lesson_id == lesson_id))).scalar_one()
    assert resp.answers == {"wohlbefinden": 5, "heisshunger_trend": "weniger"}
    # Lesson-Override umbenannt
    lesson = (await session.execute(_select(Lesson).where(Lesson.id == lesson_id))).scalar_one()
    assert "heisshunger_trend" in lesson.checkin_overrides["steps"]
    assert "heisshunger" not in lesson.checkin_overrides["steps"]
    # start bleibt absolut (key heisshunger) — NICHT angefasst
    start_keys = (await session.execute(_select(CheckinStep.key).join(
        CheckinTemplate, CheckinStep.template_id == CheckinTemplate.id).where(
        CheckinTemplate.typ == "start"))).scalars().all()
    assert "heisshunger" in set(start_keys)

    # Idempotent: zweiter Lauf ändert nichts mehr
    await migrate_laufend_step_keys()
    assert await _laufend_step_keys() == keys


@pytest.mark.asyncio
async def test_prune_crm_outbox_deletes_only_old_synced(client, session):
    """Pruning entfernt nur gesyncte Zeilen älter als die Retention; frische
    gesyncte UND geparkte (nie gesyncte) Zeilen bleiben erhalten."""
    now = utc_now()
    old_synced = CrmOutbox(event_type="checkin_response", payload={"x": 1},
                           created_at=now - timedelta(days=40), synced_at=now - timedelta(days=40))
    recent_synced = CrmOutbox(event_type="checkin_response", payload={"x": 2},
                              created_at=now - timedelta(days=2), synced_at=now - timedelta(days=2))
    old_parked = CrmOutbox(event_type="checkin_response", payload={"x": 3},
                           created_at=now - timedelta(days=40), synced_at=None, retry_count=10)
    session.add_all([old_synced, recent_synced, old_parked])
    await session.commit()

    deleted = await prune_crm_outbox(retention_days=30)
    assert deleted == 1

    session.expire_all()
    remaining = {r.payload["x"] for r in (await session.execute(_select(CrmOutbox))).scalars()}
    assert remaining == {2, 3}  # recent-synced + geparkt bleiben, alt-synced weg

    # Idempotent: zweiter Lauf löscht nichts mehr
    assert await prune_crm_outbox(retention_days=30) == 0
