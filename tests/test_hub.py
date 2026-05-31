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


from pathlib import Path

from app.models.hub import HubDownload


@pytest.mark.asyncio
async def test_download_requires_enrollment(client, session, tmp_path):
    user = await _mk_user(session)
    course = await _mk_course(session)
    hub = await _mk_hub(session, course.id)

    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content")
    download = HubDownload(
        hub_id=hub.id, title="Einkaufsliste", description="",
        file_path=str(pdf_file), file_name="Einkaufsliste.pdf", file_size_kb=1,
    )
    session.add(download)
    await session.commit()

    token = create_access_token(user.id)
    r = await client.get(
        f"/api/v1/courses/{course.id}/hub/downloads/{download.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_download_returns_file(client, session, tmp_path):
    user = await _mk_user(session)
    course = await _mk_course(session)
    hub = await _mk_hub(session, course.id)
    session.add(Enrollment(user_id=user.id, course_id=course.id))

    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content")
    download = HubDownload(
        hub_id=hub.id, title="Einkaufsliste",
        file_path=str(pdf_file), file_name="Original Name.pdf", file_size_kb=1,
    )
    session.add(download)
    await session.commit()

    token = create_access_token(user.id)
    r = await client.get(
        f"/api/v1/courses/{course.id}/hub/downloads/{download.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "Original Name.pdf" in r.headers.get("content-disposition", "")
    assert r.content == b"%PDF-1.4 fake content"


@pytest.mark.asyncio
async def test_download_rejects_mismatched_course(client, session, tmp_path):
    user = await _mk_user(session)
    course_a = await _mk_course(session)
    course_b = await _mk_course(session)
    hub_b = await _mk_hub(session, course_b.id)
    session.add(Enrollment(user_id=user.id, course_id=course_a.id))

    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"x")
    download = HubDownload(
        hub_id=hub_b.id, title="t", file_path=str(pdf_file), file_name="t.pdf",
    )
    session.add(download)
    await session.commit()

    token = create_access_token(user.id)
    # course_a in path but download belongs to course_b
    r = await client.get(
        f"/api/v1/courses/{course_a.id}/hub/downloads/{download.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_pdf_upload_requires_admin(client, session):
    user = await _mk_user(session, admin=False)
    course = await _mk_course(session)
    await _mk_hub(session, course.id)
    token = create_access_token(user.id)
    r = await client.post(
        f"/api/v1/admin/courses/{course.id}/hub/pdf",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_pdf_upload_saves_file(client, session, tmp_path, monkeypatch):
    monkeypatch.setenv("HUB_STORAGE_DIR", str(tmp_path / "hub"))
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    await _mk_hub(session, course.id)
    token = create_access_token(admin.id)
    r = await client.post(
        f"/api/v1/admin/courses/{course.id}/hub/pdf",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("Einkaufsliste.pdf", b"%PDF-1.4 content", "application/pdf")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["file_name"] == "Einkaufsliste.pdf"
    assert data["file_size_kb"] >= 0
    assert Path(data["file_path"]).exists()


@pytest.mark.asyncio
async def test_pdf_upload_rejects_non_pdf(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    await _mk_hub(session, course.id)
    token = create_access_token(admin.id)
    r = await client.post(
        f"/api/v1/admin/courses/{course.id}/hub/pdf",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("a.exe", b"MZ", "application/x-msdownload")},
    )
    assert r.status_code == 400


from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_image_upload_rejects_non_image(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    await _mk_hub(session, course.id)
    token = create_access_token(admin.id)
    r = await client.post(
        f"/api/v1/admin/courses/{course.id}/hub/image",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("a.pdf", b"%PDF", "application/pdf")},
        data={"kind": "product"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_image_upload_returns_cdn_url(client, session, monkeypatch):
    monkeypatch.setenv("BUNNY_STORAGE_ZONE", "z")
    monkeypatch.setenv("BUNNY_STORAGE_KEY", "k")
    monkeypatch.setenv("BUNNY_STORAGE_PULL_ZONE", "https://cdn.example.com")
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    await _mk_hub(session, course.id)
    token = create_access_token(admin.id)

    mock_resp = AsyncMock()
    mock_resp.status_code = 201
    with patch("httpx.AsyncClient.put", return_value=mock_resp):
        # 8x8 PNG bytes — small but valid enough for header check
        png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        r = await client.post(
            f"/api/v1/admin/courses/{course.id}/hub/image",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("a.png", png, "image/png")},
            data={"kind": "product"},
        )
    assert r.status_code == 200
    assert r.json()["url"].startswith("https://cdn.example.com/hub/")


@pytest.mark.asyncio
async def test_image_upload_when_bunny_not_configured(client, session, monkeypatch):
    monkeypatch.delenv("BUNNY_STORAGE_ZONE", raising=False)
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    await _mk_hub(session, course.id)
    token = create_access_token(admin.id)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    r = await client.post(
        f"/api/v1/admin/courses/{course.id}/hub/image",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("a.png", png, "image/png")},
        data={"kind": "product"},
    )
    assert r.status_code == 503
    assert "Bunny" in r.json().get("detail", "")


@pytest.mark.asyncio
async def test_admin_put_replaces_lists(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    hub = await _mk_hub(session, course.id)
    session.add(HubLink(hub_id=hub.id, icon_type="book", label="Alt"))
    await session.commit()
    token = create_access_token(admin.id)

    payload = {
        "hero_variant": "dark",
        "hero_eyebrow": "New",
        "hero_title_html": "<em>Hi</em><br><script>x</script>",
        "hero_body": "",
        "contact_user_id": None, "contact_name_override": "", "contact_role": "Rolle",
        "contact_email_override": "", "contact_whatsapp_url": "", "contact_photo_url": "",
        "show_contact": True, "show_live_calls": True,
        "show_products": True, "show_downloads": True,
        "links": [
            {"icon_type": "video", "label": "Neu", "sublabel": "s", "url": "", "sort_order": 0}
        ],
        "live_calls": [], "products": [], "downloads": [],
    }
    r = await client.put(
        f"/api/v1/admin/courses/{course.id}/hub",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["hero_variant"] == "dark"
    assert len(data["links"]) == 1
    assert data["links"][0]["label"] == "Neu"
    # Sanitizer strips <script>
    assert "<script>" not in data["hero_title_html"]
    assert "<em>Hi</em>" in data["hero_title_html"]


@pytest.mark.asyncio
async def test_admin_put_requires_admin(client, session):
    user = await _mk_user(session)
    course = await _mk_course(session)
    await _mk_hub(session, course.id)
    token = create_access_token(user.id)
    r = await client.put(
        f"/api/v1/admin/courses/{course.id}/hub",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "hero_variant": "berry", "hero_eyebrow": "", "hero_title_html": "",
            "hero_body": "", "contact_user_id": None, "contact_name_override": "",
            "contact_role": "", "contact_email_override": "", "contact_whatsapp_url": "",
            "contact_photo_url": "", "show_contact": True, "show_live_calls": True,
            "show_products": True, "show_downloads": True,
            "links": [], "live_calls": [], "products": [], "downloads": [],
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_put_cleans_up_removed_pdfs(client, session, tmp_path, monkeypatch):
    monkeypatch.setenv("HUB_STORAGE_DIR", str(tmp_path / "hub"))
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    hub = await _mk_hub(session, course.id)
    # Place PDF under the allowed storage root so the path-traversal guard accepts it
    # when referenced in the payload (here the payload has no downloads so guard isn't hit).
    pdf_root = tmp_path / "hub" / course.id
    pdf_root.mkdir(parents=True, exist_ok=True)
    pdf = pdf_root / "old.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    session.add(HubDownload(
        hub_id=hub.id, title="Old", file_path=str(pdf), file_name="old.pdf",
    ))
    await session.commit()
    assert pdf.exists()
    token = create_access_token(admin.id)

    payload = {
        "hero_variant": "berry", "hero_eyebrow": "", "hero_title_html": "",
        "hero_body": "", "contact_user_id": None, "contact_name_override": "",
        "contact_role": "", "contact_email_override": "", "contact_whatsapp_url": "",
        "contact_photo_url": "", "show_contact": True, "show_live_calls": True,
        "show_products": True, "show_downloads": True,
        "links": [], "live_calls": [], "products": [], "downloads": [],
    }
    r = await client.put(
        f"/api/v1/admin/courses/{course.id}/hub",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert r.status_code == 200
    assert not pdf.exists()


@pytest.mark.asyncio
async def test_admin_get_hub_returns_payload(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    hub = await _mk_hub(session, course.id)
    hub.hero_eyebrow = "From Admin"
    await session.commit()
    token = create_access_token(admin.id)
    r = await client.get(
        f"/api/v1/admin/courses/{course.id}/hub",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["hero_eyebrow"] == "From Admin"


@pytest.mark.asyncio
async def test_admin_get_hub_autocreates_when_missing(client, session):
    # Newly created courses have no hub row yet; the editor must lazily
    # provision one instead of returning 404 "Hub not found".
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    token = create_access_token(admin.id)
    r = await client.get(
        f"/api/v1/admin/courses/{course.id}/hub",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["hero_variant"] == "berry"
    assert data["links"] == []

    # The hub is persisted, so a follow-up read returns the same row.
    result = await session.execute(
        CourseHub.__table__.select().where(CourseHub.course_id == course.id)
    )
    assert result.first() is not None


@pytest.mark.asyncio
async def test_admin_put_hub_autocreates_when_missing(client, session):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    token = create_access_token(admin.id)
    r = await client.put(
        f"/api/v1/admin/courses/{course.id}/hub",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "hero_variant": "dark", "hero_eyebrow": "E", "hero_title_html": "T",
            "hero_body": "", "contact_user_id": None, "contact_name_override": "",
            "contact_role": "", "contact_email_override": "", "contact_whatsapp_url": "",
            "contact_photo_url": "", "show_contact": True, "show_live_calls": True,
            "show_products": True, "show_downloads": True,
            "links": [], "live_calls": [], "products": [], "downloads": [],
        },
    )
    assert r.status_code == 200
    assert r.json()["hero_variant"] == "dark"


@pytest.mark.asyncio
async def test_create_course_provisions_hub(client, session):
    # A freshly created course must already have a hub, so the member area
    # works even before the admin ever opens the editor.
    admin = await _mk_user(session, admin=True)
    token = create_access_token(admin.id)
    r = await client.post(
        "/api/v1/courses/",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Neuer Kurs"},
    )
    assert r.status_code == 200
    course_id = r.json()["id"]

    result = await session.execute(
        CourseHub.__table__.select().where(CourseHub.course_id == course_id)
    )
    assert result.first() is not None
