import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, hash_password
from app.models.course import Course
from app.models.hub import CourseHub, HubDownload, HubLink, HubLiveCall, HubProduct
from app.models.user import User


async def _mk_user(session: AsyncSession, *, admin: bool = False) -> User:
    user = User(
        email=f"{uuid.uuid4().hex}@example.com", name="T",
        hashed_password=hash_password("pw"), is_admin=admin,
    )
    session.add(user)
    await session.commit()
    return user


async def _mk_course(session: AsyncSession, title: str = "Course") -> Course:
    course = Course(title=title, is_active=True)
    session.add(course)
    await session.commit()
    return course


async def _mk_source_hub(session: AsyncSession, course_id: str) -> CourseHub:
    hub = CourseHub(
        course_id=course_id, hero_variant="dark", hero_eyebrow="KURS · APRIL",
        hero_title_html="Willkommen", hero_body="Schön, dass du da bist.",
        contact_role="Kursleitung", contact_whatsapp_url="https://wa.me/49123",
        contact_photo_url="https://cdn.example.com/nora.jpg",
        show_products=True,
    )
    session.add(hub)
    await session.flush()
    session.add(HubLink(hub_id=hub.id, icon_type="wa", label="WhatsApp",
                        url="https://wa.me/49123", sort_order=0))
    session.add(HubLiveCall(hub_id=hub.id, tag="mo-20:00", title="Q&A", body="Montags",
                            sort_order=0))
    session.add(HubProduct(hub_id=hub.id, title="Rezeptbuch", description="50 Rezepte",
                           url="https://shop.example.com/buch",
                           image_url="https://cdn.example.com/buch.jpg", sort_order=0))
    session.add(HubDownload(hub_id=hub.id, title="Einkaufsliste", file_path="/tmp/x.pdf",
                            file_name="Einkaufsliste.pdf", file_size_kb=1))
    await session.commit()
    return hub


@pytest.mark.asyncio
async def test_copy_hub_copies_look_and_structure(client, session):
    admin = await _mk_user(session, admin=True)
    source = await _mk_course(session, "April 2026")
    await _mk_source_hub(session, source.id)
    target = await _mk_course(session, "Neue Runde")
    session.add(CourseHub(course_id=target.id))  # leerer Ziel-Hub wie bei create_course
    await session.commit()

    token = create_access_token(admin.id)
    r = await client.post(
        f"/api/v1/admin/courses/{target.id}/hub/copy-from/{source.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    # Hero + Kontakt-Texte + Flags kopiert
    assert data["hero_variant"] == "dark"
    assert data["hero_eyebrow"] == "KURS · APRIL"
    assert data["hero_body"] == "Schön, dass du da bist."
    assert data["contact_role"] == "Kursleitung"
    assert data["contact_whatsapp_url"] == "https://wa.me/49123"
    # Listen kopiert
    assert len(data["links"]) == 1 and data["links"][0]["label"] == "WhatsApp"
    assert len(data["live_calls"]) == 1 and data["live_calls"][0]["tag"] == "mo-20:00"
    assert len(data["products"]) == 1 and data["products"][0]["title"] == "Rezeptbuch"
    # Eigene Binär-Assets NICHT kopiert
    assert data["contact_photo_url"] == ""
    assert data["products"][0]["image_url"] == ""
    assert data["downloads"] == []


@pytest.mark.asyncio
async def test_copy_hub_rejects_non_empty_target(client, session):
    admin = await _mk_user(session, admin=True)
    source = await _mk_course(session, "Quelle")
    await _mk_source_hub(session, source.id)
    target = await _mk_course(session, "Ziel")
    target_hub = CourseHub(course_id=target.id)
    session.add(target_hub)
    await session.flush()
    session.add(HubLink(hub_id=target_hub.id, icon_type="book", label="Schon da", sort_order=0))
    await session.commit()

    token = create_access_token(admin.id)
    r = await client.post(
        f"/api/v1/admin/courses/{target.id}/hub/copy-from/{source.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_copy_hub_rejects_target_with_only_hero_text(client, session):
    # Hero text already typed but no links/products yet must still block the copy,
    # otherwise the hero copy would be silently overwritten.
    admin = await _mk_user(session, admin=True)
    source = await _mk_course(session, "Quelle")
    await _mk_source_hub(session, source.id)
    target = await _mk_course(session, "Ziel")
    session.add(CourseHub(course_id=target.id, hero_title_html="Schon getippt"))
    await session.commit()

    token = create_access_token(admin.id)
    r = await client.post(
        f"/api/v1/admin/courses/{target.id}/hub/copy-from/{source.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_copy_hub_overwrite_replaces_existing_content(client, session):
    # With ?overwrite=true a non-empty target is replaced by the source's content.
    admin = await _mk_user(session, admin=True)
    source = await _mk_course(session, "Quelle")
    await _mk_source_hub(session, source.id)  # hero "Willkommen" + 1 link "WhatsApp" + ...
    target = await _mk_course(session, "Ziel")
    target_hub = CourseHub(course_id=target.id, hero_title_html="Alter Titel")
    session.add(target_hub)
    await session.flush()
    session.add(HubLink(hub_id=target_hub.id, icon_type="book", label="Alter Link", sort_order=0))
    session.add(HubDownload(
        hub_id=target_hub.id, title="Altes PDF", file_path="/tmp/does-not-exist.pdf",
        file_name="alt.pdf", file_size_kb=1,
    ))
    await session.commit()

    token = create_access_token(admin.id)
    r = await client.post(
        f"/api/v1/admin/courses/{target.id}/hub/copy-from/{source.id}?overwrite=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    # Source content now in place, old content gone
    assert data["hero_title_html"] == "Willkommen"
    assert [l["label"] for l in data["links"]] == ["WhatsApp"]
    assert data["downloads"] == []  # source has none; old download removed


@pytest.mark.asyncio
async def test_copy_hub_rejects_same_course(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session, "Selbst")
    await _mk_source_hub(session, course.id)
    token = create_access_token(admin.id)
    r = await client.post(
        f"/api/v1/admin/courses/{course.id}/hub/copy-from/{course.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_copy_hub_requires_admin(client, session):
    user = await _mk_user(session, admin=False)
    source = await _mk_course(session, "Quelle")
    await _mk_source_hub(session, source.id)
    target = await _mk_course(session, "Ziel")
    session.add(CourseHub(course_id=target.id))
    await session.commit()
    token = create_access_token(user.id)
    r = await client.post(
        f"/api/v1/admin/courses/{target.id}/hub/copy-from/{source.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
