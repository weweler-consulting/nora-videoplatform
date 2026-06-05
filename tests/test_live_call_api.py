import pytest
from tests.test_checkin import _mk_user, _mk_course, _auth


@pytest.mark.asyncio
async def test_series_crud_and_suggest(client, session, monkeypatch):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)

    # Anlegen
    r = await client.post("/api/v1/live-calls/series", headers=_auth(admin),
                          json={"course_id": course.id, "recording_name_prefix": "4-Wochen Glukose Balance Code Live Call"})
    assert r.status_code == 200, r.text
    series_id = r.json()["id"]

    # Liste
    r = await client.get("/api/v1/live-calls/series", headers=_auth(admin))
    assert any(s["id"] == series_id for s in r.json())

    # Prefix-Vorschlag: Drive-Namen, die zu keiner Serie passen → Kandidaten-Prefixe
    import app.api.live_calls as lc
    monkeypatch.setattr(lc.settings, "meet_recordings_folder_id", "FOLDER", raising=False)
    monkeypatch.setattr(lc, "list_all_video_names", lambda folder, since: [
        "Gruppencoaching Herbst 2026 Live Call - 2026/10/02 19:14 WEST - Recording",
        "4-Wochen Glukose Balance Code Live Call - 2026/10/02 19:14 WEST - Recording",  # schon gemappt
    ])
    r = await client.get("/api/v1/live-calls/suggest-prefixes", headers=_auth(admin))
    suggestions = r.json()
    assert "Gruppencoaching Herbst 2026 Live Call" in suggestions
    assert "4-Wochen Glukose Balance Code Live Call" not in suggestions  # bereits gemappt


@pytest.mark.asyncio
async def test_series_requires_admin(client, session):
    user = await _mk_user(session, admin=False)
    course = await _mk_course(session)
    r = await client.post("/api/v1/live-calls/series", headers=_auth(user),
                          json={"course_id": course.id, "recording_name_prefix": "X"})
    assert r.status_code in (401, 403)
