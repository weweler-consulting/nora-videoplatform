# Mitgliederbereich Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a per-course Mitgliederbereich (member area) on kose.noraweweler.de to replace LearningSuite before the LS contract ends 2026-05-16.

**Architecture:** One `CourseHub` row per `Course` with 4 child tables (links, live_calls, products, downloads). Admin edits through a classic form at `/admin/course/:courseId/hub` that PUTs the full payload. Public view lives as the default tab on `/course/:courseId?tab=hub`, with the existing modules moving to `?tab=lessons`. Uploads go to Bunny Storage (images) and the local disk (PDFs).

**Tech Stack:** FastAPI + SQLAlchemy async + asyncpg/aiosqlite · React 18 + React Router v6 + Vite + shadcn/ui · bleach for HTML sanitization · pytest for backend tests · Google Fonts (Almarai + Cormorant Garamond).

**Reference spec:** `docs/superpowers/specs/2026-04-24-mitgliederbereich-design.md`

---

## Spec-to-Plan Corrections

The spec assumed `Integer` primary keys; in this codebase **all IDs are `str` (UUIDs)**. The spec also used `CourseDetail.tsx` — the actual file is `CourseView.tsx`, and routes use the singular `/course/:courseId`. This plan uses the real names.

---

## File Map

### Backend — new files
- `app/models/hub.py` — `CourseHub`, `HubLink`, `HubLiveCall`, `HubProduct`, `HubDownload`.
- `app/schemas/hub.py` — Pydantic `HubPayload` + sub-schemas.
- `app/api/hub.py` — Public GET + download endpoint.
- `app/api/admin_hub.py` — Admin GET/PUT + upload endpoints.
- `app/integrations/__init__.py` — empty marker.
- `app/integrations/bunny_storage.py` — image upload + delete helpers.
- `tests/__init__.py` — empty.
- `tests/conftest.py` — pytest fixtures.
- `tests/test_hub.py` — access control + cleanup + sanitizer tests.

### Backend — modified
- `app/main.py` — register hub routers, backfill loop, ensure storage directories.
- `app/models/course.py` — `Course.hub` relationship.
- `requirements.txt` — add `bleach`, `pytest`, `pytest-asyncio`.

### Frontend — new files
- `frontend/src/lib/api/hub.ts` — hub-specific API client.
- `frontend/src/pages/course/CourseLessons.tsx` — extracted modules view.
- `frontend/src/pages/course/hub/HubView.tsx` — public container.
- `frontend/src/pages/course/hub/HubHero.tsx`
- `frontend/src/pages/course/hub/HubLinks.tsx`
- `frontend/src/pages/course/hub/HubContact.tsx`
- `frontend/src/pages/course/hub/HubLiveCalls.tsx`
- `frontend/src/pages/course/hub/HubProducts.tsx`
- `frontend/src/pages/course/hub/HubDownloads.tsx`
- `frontend/src/pages/admin/AdminCourseHub.tsx` — admin form.
- `frontend/src/pages/admin/hub/HubEditorHero.tsx`
- `frontend/src/pages/admin/hub/HubEditorContact.tsx`
- `frontend/src/pages/admin/hub/HubEditorList.tsx` — generic list editor (reused for links, calls, products, downloads).

### Frontend — modified
- `frontend/src/App.tsx` — new route `/admin/course/:courseId/hub`.
- `frontend/src/pages/CourseView.tsx` — tab bar + hub/lessons switch.
- `frontend/src/pages/admin/AdminCourseDetail.tsx` — "Mitgliederbereich bearbeiten" button.
- `frontend/src/lib/api.ts` — no changes (hub code lives in `lib/api/hub.ts`).
- `frontend/src/index.css` — global design tokens + Google Fonts import.
- `frontend/index.html` — Google Fonts `<link>` for Almarai + Cormorant Garamond.

---

## Task 0: Setup test infrastructure (one-time)

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Add test + sanitizer deps to `requirements.txt`**

Append these three lines at the end of `requirements.txt`:

```
bleach==6.2.0
pytest==8.3.4
pytest-asyncio==0.25.0
```

- [ ] **Step 2: Create empty `tests/__init__.py`**

Just touch the file; empty is fine.

- [ ] **Step 3: Create `tests/conftest.py` with async DB fixtures**

```python
import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Force SQLite in-memory before importing app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-characters-long"
os.environ["NORA_CORS_ORIGINS"] = "http://localhost:5173"

from app.core import db as db_module  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Patch the app's engine + session factory
    db_module.engine = eng
    db_module.AsyncSessionLocal = async_sessionmaker(eng, expire_on_commit=False)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    async with db_module.AsyncSessionLocal() as s:
        yield s


@pytest_asyncio.fixture
async def client(engine, tmp_path, monkeypatch):
    # Redirect file storage under tmp_path so tests are isolated
    monkeypatch.setenv("HUB_STORAGE_DIR", str(tmp_path / "hub"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

- [ ] **Step 4: Install deps locally and smoke-test**

Run: `pip install -r requirements.txt && python -m pytest tests/ -v`
Expected: PASS with "no tests collected" — confirms setup works.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/__init__.py tests/conftest.py
git commit -m "chore: add pytest + bleach deps for hub feature"
```

---

## Task 1: Bunny Storage helper

**Files:**
- Create: `app/integrations/__init__.py` (empty)
- Create: `app/integrations/bunny_storage.py`
- Test: `tests/test_bunny_storage.py`

- [ ] **Step 1: Create empty marker `app/integrations/__init__.py`**

Touch empty file.

- [ ] **Step 2: Write failing test `tests/test_bunny_storage.py`**

```python
import pytest
from unittest.mock import AsyncMock, patch

from app.integrations.bunny_storage import upload_image, BunnyNotConfigured


@pytest.mark.asyncio
async def test_upload_image_raises_when_not_configured(monkeypatch):
    monkeypatch.delenv("BUNNY_STORAGE_ZONE", raising=False)
    monkeypatch.delenv("BUNNY_STORAGE_KEY", raising=False)
    with pytest.raises(BunnyNotConfigured):
        await upload_image(b"x", course_id="c1", kind="product", filename="a.jpg")


@pytest.mark.asyncio
async def test_upload_image_returns_cdn_url(monkeypatch):
    monkeypatch.setenv("BUNNY_STORAGE_ZONE", "test-zone")
    monkeypatch.setenv("BUNNY_STORAGE_KEY", "k")
    monkeypatch.setenv("BUNNY_STORAGE_PULL_ZONE", "https://test.b-cdn.net")

    mock_resp = AsyncMock()
    mock_resp.status_code = 201
    with patch("httpx.AsyncClient.put", return_value=mock_resp):
        url = await upload_image(b"data", course_id="c1", kind="product", filename="x.jpg")
    assert url.startswith("https://test.b-cdn.net/hub/c1/product/")
    assert url.endswith(".jpg")
```

- [ ] **Step 3: Run test to confirm it fails**

Run: `pytest tests/test_bunny_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.integrations.bunny_storage'`

- [ ] **Step 4: Write `app/integrations/bunny_storage.py`**

```python
"""Bunny Storage client for hub uploads (product images, contact photos).

The production Bunny Storage zone is separate from the video streaming zone
used by `app/api/upload.py`. Env vars:
  BUNNY_STORAGE_ZONE      — zone name, e.g. "noraweweler-hub"
  BUNNY_STORAGE_KEY       — storage-zone access key (NOT the stream API key)
  BUNNY_STORAGE_PULL_ZONE — pull-zone URL, e.g. "https://nw-hub.b-cdn.net"

If any of these are unset, BunnyNotConfigured is raised so the API layer can
surface a clean 503 to the admin form.
"""
import os
import uuid
from pathlib import Path

import httpx


class BunnyNotConfigured(RuntimeError):
    pass


def _require_env() -> tuple[str, str, str]:
    zone = os.environ.get("BUNNY_STORAGE_ZONE", "")
    key = os.environ.get("BUNNY_STORAGE_KEY", "")
    pull = os.environ.get("BUNNY_STORAGE_PULL_ZONE", "").rstrip("/")
    if not (zone and key and pull):
        raise BunnyNotConfigured(
            "Bunny Storage not configured. Set BUNNY_STORAGE_ZONE, "
            "BUNNY_STORAGE_KEY, BUNNY_STORAGE_PULL_ZONE."
        )
    return zone, key, pull


async def upload_image(file_bytes: bytes, *, course_id: str, kind: str, filename: str) -> str:
    """Upload bytes to Bunny Storage, return the public CDN URL.

    Path scheme: /hub/{course_id}/{kind}/{uuid}.{ext}
    `kind` is usually "product" or "contact_photo".
    """
    zone, key, pull = _require_env()
    ext = Path(filename).suffix.lower() or ".bin"
    object_path = f"hub/{course_id}/{kind}/{uuid.uuid4().hex}{ext}"
    url = f"https://storage.bunnycdn.com/{zone}/{object_path}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.put(
            url,
            headers={"AccessKey": key, "Content-Type": "application/octet-stream"},
            content=file_bytes,
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Bunny upload failed: {resp.status_code} {resp.text}")

    return f"{pull}/{object_path}"


async def delete_image(cdn_url: str) -> None:
    """Best-effort delete of a previously uploaded image. Errors are swallowed
    because a dangling CDN file is not worth blocking a save."""
    try:
        zone, key, pull = _require_env()
    except BunnyNotConfigured:
        return
    if not cdn_url.startswith(pull + "/"):
        return
    object_path = cdn_url[len(pull) + 1:]
    url = f"https://storage.bunnycdn.com/{zone}/{object_path}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            await client.delete(url, headers={"AccessKey": key})
        except httpx.HTTPError:
            return
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_bunny_storage.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add app/integrations/__init__.py app/integrations/bunny_storage.py tests/test_bunny_storage.py
git commit -m "feat(hub): bunny storage client for image uploads"
```

---

## Task 2: Hub models

**Files:**
- Create: `app/models/hub.py`

- [ ] **Step 1: Write `app/models/hub.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class CourseHub(Base):
    __tablename__ = "course_hubs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id: Mapped[str] = mapped_column(
        String, ForeignKey("courses.id", ondelete="CASCADE"), unique=True, nullable=False, index=True,
    )

    # Hero
    hero_variant: Mapped[str] = mapped_column(String, default="berry", server_default="berry")
    hero_eyebrow: Mapped[str] = mapped_column(String, default="", server_default="")
    hero_title_html: Mapped[str] = mapped_column(Text, default="", server_default="")
    hero_body: Mapped[str] = mapped_column(Text, default="", server_default="")

    # Contact
    contact_user_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    contact_name_override: Mapped[str] = mapped_column(String, default="", server_default="")
    contact_role: Mapped[str] = mapped_column(
        String, default="Kursleitung & Ernährungsberaterin",
        server_default="Kursleitung & Ernährungsberaterin",
    )
    contact_email_override: Mapped[str] = mapped_column(String, default="", server_default="")
    contact_whatsapp_url: Mapped[str] = mapped_column(String, default="", server_default="")
    contact_photo_url: Mapped[str] = mapped_column(String, default="", server_default="")

    # Section visibility
    show_contact: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    show_live_calls: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    show_products: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    show_downloads: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    course = relationship("Course", back_populates="hub")
    links = relationship(
        "HubLink", cascade="all, delete-orphan", order_by="HubLink.sort_order", lazy="selectin",
    )
    live_calls = relationship(
        "HubLiveCall", cascade="all, delete-orphan", order_by="HubLiveCall.sort_order", lazy="selectin",
    )
    products = relationship(
        "HubProduct", cascade="all, delete-orphan", order_by="HubProduct.sort_order", lazy="selectin",
    )
    downloads = relationship(
        "HubDownload", cascade="all, delete-orphan", order_by="HubDownload.sort_order", lazy="selectin",
    )


class HubLink(Base):
    __tablename__ = "hub_links"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id: Mapped[str] = mapped_column(
        String, ForeignKey("course_hubs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    icon_type: Mapped[str] = mapped_column(String, nullable=False)     # book|video|wa|cal|link
    label: Mapped[str] = mapped_column(String, nullable=False)
    sublabel: Mapped[str] = mapped_column(String, default="", server_default="")
    url: Mapped[str] = mapped_column(String, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class HubLiveCall(Base):
    __tablename__ = "hub_live_calls"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id: Mapped[str] = mapped_column(
        String, ForeignKey("course_hubs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    tag: Mapped[str] = mapped_column(String, default="", server_default="")
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class HubProduct(Base):
    __tablename__ = "hub_products"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id: Mapped[str] = mapped_column(
        String, ForeignKey("course_hubs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    label: Mapped[str] = mapped_column(String, default="", server_default="")
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    cta_text: Mapped[str] = mapped_column(String, default="Zum Shop", server_default="Zum Shop")
    url: Mapped[str] = mapped_column(String, default="", server_default="")
    image_url: Mapped[str] = mapped_column(String, default="", server_default="")
    highlight: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class HubDownload(Base):
    __tablename__ = "hub_downloads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id: Mapped[str] = mapped_column(
        String, ForeignKey("course_hubs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_size_kb: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
```

- [ ] **Step 2: Add `hub` relationship on Course**

Edit `app/models/course.py` — inside the `Course` class, add a new line after the `enrollments` relationship (around line 24):

```python
    hub = relationship("CourseHub", uselist=False, cascade="all, delete-orphan",
                       back_populates="course", lazy="selectin")
```

- [ ] **Step 3: Smoke-test that models import cleanly**

Run: `python -c "from app.models.hub import CourseHub, HubLink, HubLiveCall, HubProduct, HubDownload; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add app/models/hub.py app/models/course.py
git commit -m "feat(hub): add CourseHub + 4 sub-tables with Course relationship"
```

---

## Task 3: Hub Pydantic schemas

**Files:**
- Create: `app/schemas/hub.py`

- [ ] **Step 1: Write `app/schemas/hub.py`**

```python
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


IconType = Literal["book", "video", "wa", "cal", "link"]
HeroVariant = Literal["berry", "dark", "pale"]


def _validate_url(v: str) -> str:
    if not v:
        return v
    if not (v.startswith("http://") or v.startswith("https://")):
        raise ValueError("URL must start with http:// or https://")
    return v


class HubLinkSchema(BaseModel):
    id: Optional[str] = None
    icon_type: IconType
    label: str = Field(min_length=1)
    sublabel: str = ""
    url: str = ""
    sort_order: int = 0

    _v_url = field_validator("url")(lambda cls, v: _validate_url(v))


class HubLiveCallSchema(BaseModel):
    id: Optional[str] = None
    tag: str = ""
    title: str = Field(min_length=1)
    body: str = ""
    sort_order: int = 0


class HubProductSchema(BaseModel):
    id: Optional[str] = None
    label: str = ""
    title: str = Field(min_length=1)
    description: str = ""
    cta_text: str = "Zum Shop"
    url: str = ""
    image_url: str = ""
    highlight: bool = False
    sort_order: int = 0

    _v_url = field_validator("url")(lambda cls, v: _validate_url(v))


class HubDownloadSchema(BaseModel):
    id: Optional[str] = None
    title: str = Field(min_length=1)
    description: str = ""
    file_path: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    file_size_kb: int = 0
    sort_order: int = 0


class HubPayload(BaseModel):
    # Hero
    hero_variant: HeroVariant = "berry"
    hero_eyebrow: str = ""
    hero_title_html: str = ""
    hero_body: str = ""

    # Contact
    contact_user_id: Optional[str] = None
    contact_name_override: str = ""
    contact_role: str = "Kursleitung & Ernährungsberaterin"
    contact_email_override: str = ""
    contact_whatsapp_url: str = ""
    contact_photo_url: str = ""

    # Visibility flags
    show_contact: bool = True
    show_live_calls: bool = True
    show_products: bool = True
    show_downloads: bool = True

    # Lists
    links: list[HubLinkSchema] = []
    live_calls: list[HubLiveCallSchema] = []
    products: list[HubProductSchema] = []
    downloads: list[HubDownloadSchema] = []

    _v_whatsapp = field_validator("contact_whatsapp_url")(lambda cls, v: _validate_url(v))

    @field_validator("contact_email_override")
    @classmethod
    def _v_email(cls, v: str) -> str:
        if not v:
            return v
        # Reuse pydantic's EmailStr validation without forcing field type
        try:
            EmailStr._validate(v)
        except Exception:
            raise ValueError("invalid email")
        return v


class UploadImageResponse(BaseModel):
    url: str


class UploadPdfResponse(BaseModel):
    file_path: str
    file_name: str
    file_size_kb: int
```

- [ ] **Step 2: Smoke-test import**

Run: `python -c "from app.schemas.hub import HubPayload; p = HubPayload(); print(p.model_dump())"`
Expected: prints a dict with all defaults.

- [ ] **Step 3: Commit**

```bash
git add app/schemas/hub.py
git commit -m "feat(hub): pydantic schemas for hub payload"
```

---

## Task 4: Migration + backfill in lifespan

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add imports at the top of `app/main.py`**

Right after `from app.api import ...` (line 19), append these two imports on new lines:

```python
from app.models import hub as _hub_models  # noqa: F401 — register Hub tables with Base
from sqlalchemy import select
```

- [ ] **Step 2: Add a storage-dir constant near `_FK_CASCADES`**

Right before the `_FK_CASCADES = [...]` block (around line 23), add:

```python
HUB_DOWNLOADS_DIR = Path(os.environ.get("HUB_STORAGE_DIR", "/app/data/hub_downloads"))
if not HUB_DOWNLOADS_DIR.parent.exists():
    HUB_DOWNLOADS_DIR = Path(__file__).parent.parent / "data" / "hub_downloads"
```

- [ ] **Step 3: Add backfill function**

Right after `_build_migration_statements()` definition (after line 71), add:

```python
async def _backfill_course_hubs() -> None:
    """Ensure every Course has a CourseHub row (idempotent via unique constraint)."""
    from app.models.course import Course
    from app.models.hub import CourseHub
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "INSERT INTO course_hubs (id, course_id, hero_variant, hero_eyebrow, "
                "hero_title_html, hero_body, contact_role, show_contact, show_live_calls, "
                "show_products, show_downloads, updated_at) "
                "SELECT lower(hex(randomblob(16))), c.id, 'berry', '', '', '', "
                "'Kursleitung & Ernährungsberaterin', 1, 1, 1, 1, CURRENT_TIMESTAMP "
                "FROM courses c WHERE NOT EXISTS "
                "(SELECT 1 FROM course_hubs h WHERE h.course_id = c.id)"
            )
            if engine.dialect.name == "sqlite"
            else text(
                "INSERT INTO course_hubs (id, course_id, hero_variant, hero_eyebrow, "
                "hero_title_html, hero_body, contact_role, show_contact, show_live_calls, "
                "show_products, show_downloads, updated_at) "
                "SELECT gen_random_uuid()::text, c.id, 'berry', '', '', '', "
                "'Kursleitung & Ernährungsberaterin', TRUE, TRUE, TRUE, TRUE, NOW() "
                "FROM courses c WHERE NOT EXISTS "
                "(SELECT 1 FROM course_hubs h WHERE h.course_id = c.id)"
            )
        )
        logger.info(f"Hub backfill: {result.rowcount} hubs created")
```

- [ ] **Step 4: Wire backfill + storage-dir setup into lifespan**

Inside the `lifespan` async context (around line 78, after the migration loop and before `asyncio.create_task(drip_notifier_loop())`), add:

```python
    # Ensure hub download storage exists
    HUB_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    # Backfill: every existing Course gets an empty CourseHub
    try:
        await _backfill_course_hubs()
    except Exception as e:
        logger.warning(f"Hub backfill failed: {e}")
```

- [ ] **Step 5: Start server locally and confirm migration runs clean**

Run: `uvicorn app.main:app --reload --port 8000` in one terminal.
Expected (in logs): no ERROR, `Hub backfill: N hubs created` appears.

Stop the server after you see the log line (Ctrl-C).

- [ ] **Step 6: Commit**

```bash
git add app/main.py
git commit -m "feat(hub): migration + backfill + storage directory setup"
```

---

## Task 5: Public Hub API (GET) + first access-control test

**Files:**
- Create: `app/api/hub.py`
- Create: `tests/test_hub.py`

- [ ] **Step 1: Write failing test `tests/test_hub.py`**

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_hub.py -v`
Expected: 3 FAIL — `404 Not Found` because the route doesn't exist yet.

- [ ] **Step 3: Write `app/api/hub.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.course import Course, Enrollment
from app.models.hub import CourseHub
from app.models.user import User
from app.schemas.hub import (
    HubDownloadSchema, HubLinkSchema, HubLiveCallSchema, HubPayload, HubProductSchema,
)

router = APIRouter()


async def _ensure_access(
    course_id: str, user: User, db: AsyncSession, *, admin_only: bool = False,
) -> None:
    if user.is_admin:
        return
    if admin_only:
        raise HTTPException(status_code=403, detail="Admin required")
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == user.id, Enrollment.course_id == course_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not enrolled in this course")


async def _load_hub(db: AsyncSession, course_id: str) -> CourseHub:
    result = await db.execute(
        select(CourseHub).where(CourseHub.course_id == course_id).options(
            selectinload(CourseHub.links),
            selectinload(CourseHub.live_calls),
            selectinload(CourseHub.products),
            selectinload(CourseHub.downloads),
        )
    )
    hub = result.scalar_one_or_none()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")
    return hub


def _hub_to_payload(hub: CourseHub) -> HubPayload:
    return HubPayload(
        hero_variant=hub.hero_variant, hero_eyebrow=hub.hero_eyebrow,
        hero_title_html=hub.hero_title_html, hero_body=hub.hero_body,
        contact_user_id=hub.contact_user_id,
        contact_name_override=hub.contact_name_override, contact_role=hub.contact_role,
        contact_email_override=hub.contact_email_override,
        contact_whatsapp_url=hub.contact_whatsapp_url,
        contact_photo_url=hub.contact_photo_url,
        show_contact=hub.show_contact, show_live_calls=hub.show_live_calls,
        show_products=hub.show_products, show_downloads=hub.show_downloads,
        links=[HubLinkSchema(id=l.id, icon_type=l.icon_type, label=l.label,
                             sublabel=l.sublabel, url=l.url, sort_order=l.sort_order)
               for l in hub.links],
        live_calls=[HubLiveCallSchema(id=c.id, tag=c.tag, title=c.title,
                                      body=c.body, sort_order=c.sort_order)
                    for c in hub.live_calls],
        products=[HubProductSchema(id=p.id, label=p.label, title=p.title,
                                   description=p.description, cta_text=p.cta_text,
                                   url=p.url, image_url=p.image_url,
                                   highlight=p.highlight, sort_order=p.sort_order)
                  for p in hub.products],
        downloads=[HubDownloadSchema(id=d.id, title=d.title, description=d.description,
                                     file_path=d.file_path, file_name=d.file_name,
                                     file_size_kb=d.file_size_kb, sort_order=d.sort_order)
                   for d in hub.downloads],
    )


@router.get("/{course_id}/hub", response_model=HubPayload)
async def get_course_hub(
    course_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify course exists (gives 404 rather than 403 for unknown IDs)
    result = await db.execute(select(Course).where(Course.id == course_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Course not found")
    await _ensure_access(course_id, user, db)
    hub = await _load_hub(db, course_id)
    return _hub_to_payload(hub)
```

- [ ] **Step 4: Register router in `app/main.py`**

In the import block around line 19, add `hub` to the `from app.api import ...` line:

Before: `from app.api import auth, courses, modules, sections, lessons, users, progress, upload, dashboard, stripe_webhook, attachments, integrations`

After: `from app.api import auth, courses, modules, sections, lessons, users, progress, upload, dashboard, stripe_webhook, attachments, integrations, hub`

Then add router registration after the existing `include_router` calls (around line 122), just before the `health` route:

```python
app.include_router(hub.router, prefix="/api/v1/courses", tags=["hub"])
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_hub.py -v`
Expected: all 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add app/api/hub.py app/main.py tests/test_hub.py
git commit -m "feat(hub): public GET /courses/{id}/hub with enrollment check"
```

---

## Task 6: PDF download endpoint

**Files:**
- Modify: `app/api/hub.py`
- Modify: `tests/test_hub.py`

- [ ] **Step 1: Add failing test for download endpoint**

Append to `tests/test_hub.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_hub.py -v`
Expected: 3 new tests FAIL (route missing).

- [ ] **Step 3: Add download endpoint to `app/api/hub.py`**

Append at the bottom:

```python
from fastapi.responses import FileResponse  # add near top with other imports


@router.get("/{course_id}/hub/downloads/{download_id}")
async def download_hub_file(
    course_id: str,
    download_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_access(course_id, user, db)
    result = await db.execute(
        select(HubDownload).join(CourseHub, CourseHub.id == HubDownload.hub_id)
        .where(HubDownload.id == download_id, CourseHub.course_id == course_id)
    )
    download = result.scalar_one_or_none()
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")
    from pathlib import Path
    path = Path(download.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(
        path=str(path), filename=download.file_name, media_type="application/pdf",
    )
```

Also, add the `HubDownload` import near the top with other model imports:

```python
from app.models.hub import CourseHub, HubDownload
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_hub.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/api/hub.py tests/test_hub.py
git commit -m "feat(hub): PDF download endpoint with enrollment + course-id check"
```

---

## Task 7: PDF upload endpoint

**Files:**
- Create: `app/api/admin_hub.py`
- Modify: `app/main.py`
- Modify: `tests/test_hub.py`

- [ ] **Step 1: Add failing upload test**

Append to `tests/test_hub.py`:

```python
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
    # Reimport to pick up env var — admin_hub resolves path lazily
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
```

- [ ] **Step 2: Run tests — confirm fail**

Run: `pytest tests/test_hub.py -v -k upload`
Expected: FAIL 404 (route missing).

- [ ] **Step 3: Create `app/api/admin_hub.py` with upload endpoint**

```python
"""Admin endpoints for CourseHub editing."""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.db import get_db
from app.models.course import Course
from app.models.hub import CourseHub
from app.models.user import User
from app.schemas.hub import UploadPdfResponse


router = APIRouter()


def _hub_storage_dir() -> Path:
    base = Path(os.environ.get("HUB_STORAGE_DIR", "/app/data/hub_downloads"))
    if not base.parent.exists():
        base = Path(__file__).resolve().parent.parent.parent / "data" / "hub_downloads"
    base.mkdir(parents=True, exist_ok=True)
    return base


MAX_PDF_BYTES = 20 * 1024 * 1024


async def _require_course(db: AsyncSession, course_id: str) -> Course:
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.post("/{course_id}/hub/pdf", response_model=UploadPdfResponse)
async def upload_hub_pdf(
    course_id: str,
    file: UploadFile = File(...),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_course(db, course_id)

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="PDF erwartet")

    content = await file.read()
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail="Maximal 20 MB")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Kein gültiges PDF")

    course_dir = _hub_storage_dir() / course_id
    course_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.pdf"
    path = course_dir / filename
    path.write_bytes(content)

    return UploadPdfResponse(
        file_path=str(path),
        file_name=file.filename or "download.pdf",
        file_size_kb=max(1, len(content) // 1024),
    )
```

- [ ] **Step 4: Register admin_hub router in `app/main.py`**

Update the import line added in Task 5 to also include `admin_hub`:

Before: `from app.api import auth, courses, ..., integrations, hub`
After: `from app.api import auth, courses, ..., integrations, hub, admin_hub`

And add registration right after the `hub.router` line:

```python
app.include_router(admin_hub.router, prefix="/api/v1/admin/courses", tags=["admin_hub"])
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_hub.py -v -k upload`
Expected: all 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add app/api/admin_hub.py app/main.py tests/test_hub.py
git commit -m "feat(hub): admin PDF upload endpoint (20MB limit, %PDF magic check)"
```

---

## Task 8: Image upload endpoint (Bunny)

**Files:**
- Modify: `app/api/admin_hub.py`
- Modify: `tests/test_hub.py`

- [ ] **Step 1: Append failing image-upload test**

Append to `tests/test_hub.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm fail**

Run: `pytest tests/test_hub.py -v -k "image_upload"`
Expected: 3 FAIL (route missing).

- [ ] **Step 3: Add image-upload endpoint to `app/api/admin_hub.py`**

Append:

```python
from typing import Literal
from fastapi import Form

from app.integrations.bunny_storage import BunnyNotConfigured, upload_image
from app.schemas.hub import UploadImageResponse


MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/{course_id}/hub/image", response_model=UploadImageResponse)
async def upload_hub_image(
    course_id: str,
    file: UploadFile = File(...),
    kind: Literal["product", "contact_photo"] = Form(...),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_course(db, course_id)

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Nur JPEG, PNG oder WebP")

    content = await file.read()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Maximal 5 MB")

    try:
        url = await upload_image(
            content, course_id=course_id, kind=kind,
            filename=file.filename or "image.bin",
        )
    except BunnyNotConfigured as e:
        raise HTTPException(status_code=503, detail=f"Bunny Storage nicht konfiguriert: {e}")

    return UploadImageResponse(url=url)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_hub.py -v -k "image_upload"`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/api/admin_hub.py tests/test_hub.py
git commit -m "feat(hub): admin image upload via Bunny Storage"
```

---

## Task 9: Admin Hub GET + PUT with dead-file cleanup

**Files:**
- Modify: `app/api/admin_hub.py`
- Modify: `tests/test_hub.py`

- [ ] **Step 1: Append failing PUT tests**

Append to `tests/test_hub.py`:

```python
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
async def test_admin_put_cleans_up_removed_pdfs(client, session, tmp_path):
    admin = await _mk_user(session, admin=True)
    course = await _mk_course(session)
    hub = await _mk_hub(session, course.id)
    pdf = tmp_path / "old.pdf"
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
```

- [ ] **Step 2: Run tests to confirm fail**

Run: `pytest tests/test_hub.py -v -k "admin_put or admin_get"`
Expected: 4 FAIL (routes missing).

- [ ] **Step 3: Extend `app/api/admin_hub.py` with GET + PUT**

Append to the file:

```python
from pathlib import Path as _Path

import bleach
from sqlalchemy.orm import selectinload

from app.api.hub import _hub_to_payload, _load_hub
from app.integrations.bunny_storage import delete_image
from app.models.hub import HubDownload, HubLink, HubLiveCall, HubProduct
from app.schemas.hub import HubPayload


ALLOWED_HTML_TAGS = ["em", "br"]


def _sanitize_html(raw: str) -> str:
    return bleach.clean(raw or "", tags=ALLOWED_HTML_TAGS, attributes={}, strip=True)


@router.get("/{course_id}/hub", response_model=HubPayload)
async def admin_get_hub(
    course_id: str,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_course(db, course_id)
    hub = await _load_hub(db, course_id)
    return _hub_to_payload(hub)


@router.put("/{course_id}/hub", response_model=HubPayload)
async def admin_put_hub(
    course_id: str,
    payload: HubPayload,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_course(db, course_id)
    hub = await _load_hub(db, course_id)

    # Capture old media URLs/paths for cleanup
    old_pdf_paths = {d.file_path for d in hub.downloads}
    old_image_urls = {p.image_url for p in hub.products if p.image_url}
    old_contact_photo = hub.contact_photo_url or ""

    # Hero + Contact
    hub.hero_variant = payload.hero_variant
    hub.hero_eyebrow = payload.hero_eyebrow
    hub.hero_title_html = _sanitize_html(payload.hero_title_html)
    hub.hero_body = payload.hero_body

    hub.contact_user_id = payload.contact_user_id
    hub.contact_name_override = payload.contact_name_override
    hub.contact_role = payload.contact_role
    hub.contact_email_override = payload.contact_email_override
    hub.contact_whatsapp_url = payload.contact_whatsapp_url
    hub.contact_photo_url = payload.contact_photo_url

    hub.show_contact = payload.show_contact
    hub.show_live_calls = payload.show_live_calls
    hub.show_products = payload.show_products
    hub.show_downloads = payload.show_downloads

    # Replace-all for lists
    hub.links.clear()
    hub.live_calls.clear()
    hub.products.clear()
    hub.downloads.clear()
    await db.flush()

    for i, link in enumerate(payload.links):
        hub.links.append(HubLink(
            icon_type=link.icon_type, label=link.label, sublabel=link.sublabel,
            url=link.url, sort_order=link.sort_order or i,
        ))
    for i, call in enumerate(payload.live_calls):
        hub.live_calls.append(HubLiveCall(
            tag=call.tag, title=call.title, body=call.body,
            sort_order=call.sort_order or i,
        ))
    for i, prod in enumerate(payload.products):
        hub.products.append(HubProduct(
            label=prod.label, title=prod.title, description=prod.description,
            cta_text=prod.cta_text, url=prod.url, image_url=prod.image_url,
            highlight=prod.highlight, sort_order=prod.sort_order or i,
        ))
    for i, dl in enumerate(payload.downloads):
        # Path traversal guard: only accept files inside the hub storage dir
        abs_path = _Path(dl.file_path).resolve()
        allowed_root = _hub_storage_dir().resolve()
        if not str(abs_path).startswith(str(allowed_root)):
            raise HTTPException(status_code=400, detail=f"Ungültiger Pfad: {dl.file_path}")
        hub.downloads.append(HubDownload(
            title=dl.title, description=dl.description,
            file_path=dl.file_path, file_name=dl.file_name,
            file_size_kb=dl.file_size_kb, sort_order=dl.sort_order or i,
        ))

    await db.flush()
    await db.refresh(hub, attribute_names=["links", "live_calls", "products", "downloads"])

    # Dead-file cleanup (after successful DB update)
    new_pdf_paths = {d.file_path for d in payload.downloads}
    for stale in old_pdf_paths - new_pdf_paths:
        try:
            _Path(stale).unlink(missing_ok=True)
        except OSError:
            pass

    new_image_urls = {p.image_url for p in payload.products if p.image_url}
    for stale in old_image_urls - new_image_urls:
        await delete_image(stale)

    if old_contact_photo and old_contact_photo != hub.contact_photo_url:
        await delete_image(old_contact_photo)

    return _hub_to_payload(hub)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_hub.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/api/admin_hub.py tests/test_hub.py
git commit -m "feat(hub): admin GET/PUT with html sanitizer + dead-file cleanup"
```

---

## Task 10: Hub TypeScript types + API client

**Files:**
- Create: `frontend/src/lib/api/hub.ts`

- [ ] **Step 1: Write the API client**

```typescript
// frontend/src/lib/api/hub.ts
const API_BASE = '/api/v1';

function getToken(): string | null {
  return localStorage.getItem('token');
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}`, ...extra } : extra;
}

export type IconType = 'book' | 'video' | 'wa' | 'cal' | 'link';
export type HeroVariant = 'berry' | 'dark' | 'pale';

export interface HubLink {
  id?: string;
  icon_type: IconType;
  label: string;
  sublabel: string;
  url: string;
  sort_order: number;
}

export interface HubLiveCall {
  id?: string;
  tag: string;
  title: string;
  body: string;
  sort_order: number;
}

export interface HubProduct {
  id?: string;
  label: string;
  title: string;
  description: string;
  cta_text: string;
  url: string;
  image_url: string;
  highlight: boolean;
  sort_order: number;
}

export interface HubDownload {
  id?: string;
  title: string;
  description: string;
  file_path: string;
  file_name: string;
  file_size_kb: number;
  sort_order: number;
}

export interface HubPayload {
  hero_variant: HeroVariant;
  hero_eyebrow: string;
  hero_title_html: string;
  hero_body: string;
  contact_user_id: string | null;
  contact_name_override: string;
  contact_role: string;
  contact_email_override: string;
  contact_whatsapp_url: string;
  contact_photo_url: string;
  show_contact: boolean;
  show_live_calls: boolean;
  show_products: boolean;
  show_downloads: boolean;
  links: HubLink[];
  live_calls: HubLiveCall[];
  products: HubProduct[];
  downloads: HubDownload[];
}

async function jsonRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(init.headers as Record<string, string> || {}),
    },
  });
  if (res.status === 401) {
    localStorage.removeItem('token');
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const hubApi = {
  getPublic: (courseId: string) =>
    jsonRequest<HubPayload>(`/courses/${courseId}/hub`),

  getAdmin: (courseId: string) =>
    jsonRequest<HubPayload>(`/admin/courses/${courseId}/hub`),

  save: (courseId: string, payload: HubPayload) =>
    jsonRequest<HubPayload>(`/admin/courses/${courseId}/hub`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  uploadPdf: async (courseId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/admin/courses/${courseId}/hub/pdf`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    return res.json() as Promise<{ file_path: string; file_name: string; file_size_kb: number }>;
  },

  uploadImage: async (courseId: string, kind: 'product' | 'contact_photo', file: File) => {
    const form = new FormData();
    form.append('file', file);
    form.append('kind', kind);
    const res = await fetch(`${API_BASE}/admin/courses/${courseId}/hub/image`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    return res.json() as Promise<{ url: string }>;
  },

  downloadUrl: (courseId: string, downloadId: string) =>
    `${API_BASE}/courses/${courseId}/hub/downloads/${downloadId}`,
};

export async function downloadHubFile(courseId: string, downloadId: string, filename: string) {
  const res = await fetch(hubApi.downloadUrl(courseId, downloadId), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Download fehlgeschlagen: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api/hub.ts
git commit -m "feat(hub): frontend api client + types"
```

---

## Task 11: Design tokens + Google Fonts

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Add Google Fonts to `frontend/index.html`**

Locate the `<head>` section. Add these lines immediately before the closing `</head>`:

```html
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Almarai:wght@300;400;700;800&family=Cormorant+Garamond:ital,wght@1,400&display=swap" rel="stylesheet">
```

- [ ] **Step 2: Add tokens to `frontend/src/index.css`**

Prepend the following to the top of `frontend/src/index.css` (before any existing content):

```css
/*
 * Nora Weweler — Design Tokens
 * Source: ZIP prototype colors_and_type.css
 */
:root {
  /* Brand palette */
  --berry:        #D47479;
  --berry-dark:   #b8585d;
  --berry-light:  #e8a0a4;
  --berry-pale:   #f2d0d2;

  --cream:        #fffef5;
  --coco:         #e3e3e3;
  --soy:          #303030;
  --soy-light:    #3d3d3d;
  --white:        #ffffff;

  --green:        #4caf50;
  --green-dark:   #388e3c;

  --color-text-primary:       var(--soy);
  --color-text-secondary:     rgba(48,48,48,0.7);
  --color-text-muted:         rgba(48,48,48,0.45);
  --color-text-on-dark:       rgba(255,255,255,0.9);
  --color-text-on-dark-muted: rgba(255,255,255,0.65);

  --color-bg-default:  var(--white);
  --color-bg-warm:     var(--cream);
  --color-bg-dark:     var(--soy);
  --color-bg-accent:   var(--berry);

  --color-border:      var(--coco);
  --color-accent:      var(--berry);
  --color-accent-hover:var(--berry-dark);

  --gradient-berry: linear-gradient(135deg, #D47479 0%, #c46069 100%);
  --gradient-dark:  linear-gradient(135deg, #303030 0%, #3d3d3d 100%);
  --gradient-pale:  linear-gradient(135deg, #f2d0d2 0%, #e8a0a4 100%);

  --font-sans:  'Almarai', system-ui, -apple-system, sans-serif;
  --font-serif: 'Cormorant Garamond', Georgia, serif;

  --radius-sm:   8px;
  --radius-md:   10px;
  --radius-lg:   12px;
  --radius-xl:   16px;
  --radius-pill: 30px;

  --shadow-card:       0 2px 12px rgba(0,0,0,0.04);
  --shadow-card-hover: 0 12px 40px rgba(0,0,0,0.06);
  --shadow-btn:        0 8px 25px rgba(212,116,121,0.35);
  --shadow-nav:        0 2px 20px rgba(0,0,0,0.06);
}

html, body {
  font-family: var(--font-sans);
  background: var(--cream);
  color: var(--color-text-primary);
  -webkit-font-smoothing: antialiased;
}

.nw-italic {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  text-transform: none;
}
```

- [ ] **Step 3: Start dev server and verify**

Run: `cd frontend && npm run dev` (separate terminal: `uvicorn app.main:app --reload --port 8000`).

Open `http://localhost:5173/login` — login page should render with Almarai font and cream background. Take a quick screenshot to document.

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html frontend/src/index.css
git commit -m "feat(hub): global design tokens + Google Fonts (Almarai, Cormorant)"
```

---

## Task 12: Refactor CourseView into tabs + extract CourseLessons

**Files:**
- Modify: `frontend/src/pages/CourseView.tsx`
- Create: `frontend/src/pages/course/CourseLessons.tsx`

- [ ] **Step 1: Read current CourseView.tsx**

Run: `cat frontend/src/pages/CourseView.tsx`
Take note of the complete JSX and state — you will move most of it into `CourseLessons.tsx` verbatim.

- [ ] **Step 2: Create `frontend/src/pages/course/CourseLessons.tsx`**

Create the file with the following skeleton, then paste the ENTIRE existing `CourseView.tsx` function body (everything between `export default function CourseView() { ... }`) into the new `CourseLessons` component. Rename `CourseView` → `CourseLessons`. Keep all imports that were used.

```typescript
// frontend/src/pages/course/CourseLessons.tsx
// Moved verbatim from src/pages/CourseView.tsx. The outer CourseView now just
// picks this component (lessons tab) or HubView (hub tab) based on ?tab=.
import { useParams } from 'react-router-dom';
// ... (copy remaining imports from CourseView.tsx)

export default function CourseLessons() {
  const { courseId } = useParams();
  // ... (paste body of original CourseView function verbatim)
}
```

Verify the file compiles: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Rewrite `frontend/src/pages/CourseView.tsx` as a tab container**

Replace the entire file with:

```typescript
import { useSearchParams, useParams } from 'react-router-dom';
import CourseLessons from './course/CourseLessons';
import HubView from './course/hub/HubView';

export default function CourseView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { courseId } = useParams();
  const tab = searchParams.get('tab') === 'lessons' ? 'lessons' : 'hub';

  const setTab = (t: 'hub' | 'lessons') => {
    const next = new URLSearchParams(searchParams);
    if (t === 'hub') next.delete('tab'); else next.set('tab', t);
    setSearchParams(next, { replace: false });
  };

  return (
    <div>
      <div
        style={{
          display: 'flex',
          gap: 8,
          borderBottom: '1px solid var(--coco)',
          marginBottom: 24,
        }}
      >
        <TabButton active={tab === 'hub'} onClick={() => setTab('hub')}>
          Mitgliederbereich
        </TabButton>
        <TabButton active={tab === 'lessons'} onClick={() => setTab('lessons')}>
          Inhalte
        </TabButton>
      </div>
      {tab === 'hub' ? (
        <HubView courseId={courseId!} />
      ) : (
        <CourseLessons />
      )}
    </div>
  );
}

function TabButton({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '12px 20px',
        background: 'transparent',
        border: 'none',
        borderBottom: `2px solid ${active ? 'var(--berry)' : 'transparent'}`,
        color: active ? 'var(--berry)' : 'var(--color-text-secondary)',
        fontFamily: 'var(--font-sans)',
        fontSize: 14,
        fontWeight: 700,
        letterSpacing: '0.3px',
        cursor: 'pointer',
        textTransform: 'uppercase',
      }}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 4: Create a placeholder `HubView` (real rendering comes in Task 13)**

Create `frontend/src/pages/course/hub/HubView.tsx`:

```typescript
export default function HubView({ courseId }: { courseId: string }) {
  return <div style={{ padding: 20 }}>Hub für Kurs {courseId} — lädt …</div>;
}
```

- [ ] **Step 5: Verify in browser**

With both dev servers running, log in as an admin, navigate to `/course/<some-course-id>`. You should see a tab bar at top; clicking "Inhalte" shows the original module view, clicking "Mitgliederbereich" shows the placeholder. URL updates with `?tab=lessons` / no param.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/CourseView.tsx frontend/src/pages/course/CourseLessons.tsx frontend/src/pages/course/hub/HubView.tsx
git commit -m "feat(hub): refactor CourseView into tabs + placeholder HubView"
```

---

## Task 13: HubView + public section components

**Files:**
- Modify: `frontend/src/pages/course/hub/HubView.tsx`
- Create: `frontend/src/pages/course/hub/HubHero.tsx`
- Create: `frontend/src/pages/course/hub/HubLinks.tsx`
- Create: `frontend/src/pages/course/hub/HubContact.tsx`
- Create: `frontend/src/pages/course/hub/HubLiveCalls.tsx`
- Create: `frontend/src/pages/course/hub/HubProducts.tsx`
- Create: `frontend/src/pages/course/hub/HubDownloads.tsx`

- [ ] **Step 1: Replace `HubView.tsx` with the real container**

```typescript
import { useEffect, useState } from 'react';
import { hubApi, HubPayload } from '../../../lib/api/hub';
import HubHero from './HubHero';
import HubLinks from './HubLinks';
import HubContact from './HubContact';
import HubLiveCalls from './HubLiveCalls';
import HubProducts from './HubProducts';
import HubDownloads from './HubDownloads';

export default function HubView({ courseId }: { courseId: string }) {
  const [hub, setHub] = useState<HubPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    hubApi.getPublic(courseId).then(setHub).catch((e) => setError(e.message));
  }, [courseId]);

  if (error) return <div style={{ padding: 20, color: 'var(--berry-dark)' }}>{error}</div>;
  if (!hub) return <div style={{ padding: 20 }}>Lädt …</div>;

  const isEmpty =
    !hub.hero_eyebrow && !hub.hero_title_html && !hub.hero_body &&
    hub.links.length === 0 && hub.live_calls.length === 0 &&
    hub.products.length === 0 && hub.downloads.length === 0;

  if (isEmpty) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>
        Dieser Mitgliederbereich wird gerade eingerichtet — schau später nochmal vorbei.
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <h1 style={{
        fontFamily: 'var(--font-sans)', fontWeight: 800, fontSize: 22,
        textTransform: 'uppercase', letterSpacing: '-0.3px',
        color: 'var(--soy)', marginBottom: 28,
      }}>
        Dein Mitgliederbereich
      </h1>
      <HubHero
        variant={hub.hero_variant}
        eyebrow={hub.hero_eyebrow}
        titleHtml={hub.hero_title_html}
        body={hub.hero_body}
        contactName={hub.contact_name_override}
        contactRole={hub.contact_role}
        contactPhotoUrl={hub.contact_photo_url}
      />
      {hub.links.length > 0 && <HubLinks links={hub.links} />}
      {hub.show_contact && <HubContact
        name={hub.contact_name_override} role={hub.contact_role}
        email={hub.contact_email_override} whatsappUrl={hub.contact_whatsapp_url}
        photoUrl={hub.contact_photo_url}
      />}
      {hub.show_live_calls && hub.live_calls.length > 0 && <HubLiveCalls calls={hub.live_calls} />}
      {hub.show_products && hub.products.length > 0 && <HubProducts products={hub.products} />}
      {hub.show_downloads && hub.downloads.length > 0 &&
        <HubDownloads courseId={courseId} downloads={hub.downloads} />}
    </div>
  );
}
```

- [ ] **Step 2: Create `HubHero.tsx`**

```typescript
import { HeroVariant } from '../../../lib/api/hub';

const GRADIENTS: Record<HeroVariant, string> = {
  berry: 'var(--gradient-berry)',
  dark: 'var(--gradient-dark)',
  pale: 'var(--gradient-pale)',
};

export default function HubHero({
  variant, eyebrow, titleHtml, body,
  contactName, contactRole, contactPhotoUrl,
}: {
  variant: HeroVariant;
  eyebrow: string;
  titleHtml: string;
  body: string;
  contactName: string;
  contactRole: string;
  contactPhotoUrl: string;
}) {
  const dark = variant !== 'pale';
  return (
    <div style={{
      background: GRADIENTS[variant],
      borderRadius: 'var(--radius-xl)',
      padding: '32px 36px',
      marginBottom: 36,
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 20,
    }}>
      <div style={{ maxWidth: 520 }}>
        {eyebrow && (
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '3px',
            textTransform: 'uppercase',
            color: dark ? 'rgba(255,255,255,0.65)' : 'var(--berry)',
            marginBottom: 10,
          }}>{eyebrow}</div>
        )}
        {titleHtml && (
          <h2
            style={{
              fontFamily: 'var(--font-sans)', fontWeight: 800, fontSize: 'clamp(18px,2.5vw,28px)',
              textTransform: 'uppercase', letterSpacing: '-0.3px',
              color: dark ? '#fff' : 'var(--soy)',
              lineHeight: 1.15, marginBottom: 12,
            }}
            dangerouslySetInnerHTML={{ __html: titleHtml }}
          />
        )}
        {body && (
          <p style={{
            fontSize: 14, lineHeight: 1.65,
            color: dark ? 'rgba(255,255,255,0.8)' : 'var(--color-text-secondary)',
          }}>{body}</p>
        )}
      </div>
      {(contactName || contactPhotoUrl) && (
        <div style={{
          flexShrink: 0,
          background: dark ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.6)',
          borderRadius: 14, padding: '18px 22px', textAlign: 'center',
          border: `1px solid ${dark ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.9)'}`,
        }}>
          {contactPhotoUrl && (
            <img src={contactPhotoUrl} alt={contactName} style={{
              width: 56, height: 56, borderRadius: '50%', objectFit: 'cover',
            }} />
          )}
          <div style={{
            marginTop: 10, fontWeight: 800, fontSize: 13,
            textTransform: 'uppercase',
            color: dark ? '#fff' : 'var(--soy)',
          }}>{contactName}</div>
          {contactRole && (
            <div style={{
              fontSize: 11, marginTop: 3,
              color: dark ? 'rgba(255,255,255,0.65)' : 'rgba(48,48,48,0.55)',
            }}>{contactRole}</div>
          )}
        </div>
      )}
    </div>
  );
}
```

**SECURITY NOTE:** `dangerouslySetInnerHTML` is safe here because the backend `_sanitize_html` already bleach-cleans on save (see Task 9).

- [ ] **Step 3: Create `HubLinks.tsx`**

```typescript
import { HubLink, IconType } from '../../../lib/api/hub';

function Icon({ type }: { type: IconType }) {
  const c = 'var(--berry)';
  const s = 20;
  const common = {
    width: s, height: s, viewBox: '0 0 24 24',
    fill: 'none', stroke: c, strokeWidth: 1.8,
    strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const,
  };
  if (type === 'book') return (<svg {...common}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>);
  if (type === 'video') return (<svg {...common}><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>);
  if (type === 'cal') return (<svg {...common}><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>);
  if (type === 'wa') return (<svg width={s} height={s} viewBox="0 0 24 24" fill={c}><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413z"/></svg>);
  return (<svg {...common}><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>);
}

export default function HubLinks({ links }: { links: HubLink[] }) {
  return (
    <section style={{ marginBottom: 36 }}>
      <SectionLabel>Wichtige Links für Dich</SectionLabel>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {links.map(link => {
          const disabled = !link.url;
          const content = (
            <div style={{
              flex: '1 1 160px', display: 'flex', flexDirection: 'column',
              alignItems: 'center', gap: 10, padding: '22px 16px',
              background: 'var(--white)',
              border: '1.5px solid var(--coco)',
              borderRadius: 'var(--radius-lg)',
              textAlign: 'center',
              opacity: disabled ? 0.55 : 1,
              boxShadow: 'var(--shadow-card)',
            }}>
              <div style={{
                width: 44, height: 44, borderRadius: 12,
                background: 'var(--berry-pale)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon type={link.icon_type} />
              </div>
              <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--soy)', lineHeight: 1.3 }}>
                {link.label}
              </div>
              {link.sublabel && (
                <div style={{ fontSize: 11.5, color: 'rgba(48,48,48,0.5)', marginTop: 3 }}>
                  {link.sublabel}
                </div>
              )}
            </div>
          );
          return disabled ? (
            <div key={link.id || link.label} title="Link wird vorbereitet"
                 style={{ flex: '1 1 160px' }}>{content}</div>
          ) : (
            <a key={link.id || link.url} href={link.url} target="_blank" rel="noopener"
               style={{ flex: '1 1 160px', textDecoration: 'none' }}>{content}</a>
          );
        })}
      </div>
    </section>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
      letterSpacing: '3px', color: 'var(--berry)', marginBottom: 18,
    }}>{children}</div>
  );
}
```

- [ ] **Step 4: Create `HubContact.tsx`**

```typescript
export default function HubContact({
  name, role, email, whatsappUrl, photoUrl,
}: {
  name: string; role: string; email: string; whatsappUrl: string; photoUrl: string;
}) {
  if (!name && !email && !whatsappUrl) return null;
  return (
    <section style={{ marginBottom: 36 }}>
      <div style={{
        fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '3px', color: 'var(--berry)', marginBottom: 18,
      }}>Deine Ansprechpartnerin</div>
      <div style={{
        background: 'var(--white)', border: '1px solid var(--coco)',
        borderRadius: 'var(--radius-lg)', padding: '20px 22px',
        display: 'flex', alignItems: 'center', gap: 16, maxWidth: 440,
      }}>
        {photoUrl
          ? <img src={photoUrl} alt={name}
                 style={{ width: 50, height: 50, borderRadius: '50%', objectFit: 'cover' }} />
          : <div style={{
              width: 50, height: 50, borderRadius: '50%', background: 'var(--berry)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontWeight: 800,
            }}>{(name || '?').slice(0, 2).toUpperCase()}</div>}
        <div style={{ flex: 1 }}>
          {name && <div style={{
            fontWeight: 800, fontSize: 14, textTransform: 'uppercase',
            color: 'var(--soy)',
          }}>{name}</div>}
          {role && <div style={{
            fontSize: 12, color: 'rgba(48,48,48,0.55)', marginTop: 3, marginBottom: 12,
          }}>{role}</div>}
          <div style={{ display: 'flex', gap: 8 }}>
            {email && <a href={`mailto:${email}`} style={pillStyle}>E-Mail</a>}
            {whatsappUrl && <a href={whatsappUrl} target="_blank" rel="noopener" style={pillStyle}>
              WhatsApp
            </a>}
          </div>
        </div>
      </div>
    </section>
  );
}

const pillStyle = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '7px 16px', borderRadius: 'var(--radius-pill)',
  background: 'transparent', color: 'var(--berry)',
  border: '1px solid var(--berry-pale)',
  fontSize: 12, fontWeight: 700, textDecoration: 'none',
} as const;
```

- [ ] **Step 5: Create `HubLiveCalls.tsx`**

```typescript
import { HubLiveCall } from '../../../lib/api/hub';

export default function HubLiveCalls({ calls }: { calls: HubLiveCall[] }) {
  return (
    <section style={{ marginBottom: 36 }}>
      <div style={{
        fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '3px', color: 'var(--berry)', marginBottom: 18,
      }}>Live Calls</div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {calls.map(call => (
          <div key={call.id || call.title} style={{
            background: 'var(--white)', border: '1px solid var(--coco)',
            borderTop: '3px solid var(--berry)',
            borderRadius: 'var(--radius-lg)', padding: '20px 22px',
            flex: '1 1 260px',
          }}>
            {call.tag && <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: '2.5px',
              color: 'var(--berry)', textTransform: 'uppercase', marginBottom: 8,
            }}>{call.tag}</div>}
            <div style={{ fontWeight: 700, fontSize: 14.5, color: 'var(--soy)', marginBottom: 8 }}>
              {call.title}
            </div>
            {call.body && <div style={{
              fontSize: 13, color: 'rgba(48,48,48,0.65)', lineHeight: 1.65,
              whiteSpace: 'pre-wrap',
            }}>{call.body}</div>}
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 6: Create `HubProducts.tsx`**

```typescript
import { HubProduct } from '../../../lib/api/hub';

export default function HubProducts({ products }: { products: HubProduct[] }) {
  return (
    <section style={{ marginBottom: 36 }}>
      <div style={{
        fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '3px', color: 'var(--berry)', marginBottom: 18,
      }}>Empfehlungen & Zusatzprodukte</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {products.map(p => (
          <div key={p.id || p.title} style={{
            background: p.highlight ? 'var(--gradient-berry)' : 'var(--white)',
            border: `1px solid ${p.highlight ? 'transparent' : 'var(--coco)'}`,
            borderRadius: 'var(--radius-xl)',
            display: 'flex', alignItems: 'stretch', overflow: 'hidden',
          }}>
            <div style={{
              width: 170, flexShrink: 0,
              background: p.highlight ? 'rgba(255,255,255,0.12)' : 'var(--berry-pale)',
              backgroundImage: p.image_url ? `url(${p.image_url})` : 'none',
              backgroundSize: 'cover', backgroundPosition: 'center',
              minHeight: 140,
            }} />
            <div style={{ padding: '22px 28px', flex: 1 }}>
              {p.label && <div style={{
                fontSize: 10, fontWeight: 700, letterSpacing: '2.5px',
                textTransform: 'uppercase',
                color: p.highlight ? 'rgba(255,255,255,0.75)' : 'var(--berry)',
                marginBottom: 6,
              }}>{p.label}</div>}
              <div style={{
                fontWeight: 800, fontSize: 16, textTransform: 'uppercase',
                color: p.highlight ? '#fff' : 'var(--soy)', marginBottom: 8,
              }}>{p.title}</div>
              {p.description && <div style={{
                fontSize: 13.5, lineHeight: 1.6, marginBottom: 14,
                color: p.highlight ? 'rgba(255,255,255,0.82)' : 'rgba(48,48,48,0.65)',
              }}>{p.description}</div>}
              {p.url && (
                <a href={p.url} target="_blank" rel="noopener" style={{
                  display: 'inline-flex', gap: 6, padding: '7px 16px',
                  borderRadius: 'var(--radius-pill)',
                  background: p.highlight ? 'rgba(255,255,255,0.15)' : 'transparent',
                  color: p.highlight ? '#fff' : 'var(--berry)',
                  border: `1px solid ${p.highlight ? 'rgba(255,255,255,0.3)' : 'var(--berry)'}`,
                  fontSize: 12, fontWeight: 700, textDecoration: 'none',
                }}>{p.cta_text}</a>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 7: Create `HubDownloads.tsx`**

```typescript
import { HubDownload } from '../../../lib/api/hub';
import { downloadHubFile } from '../../../lib/api/hub';

export default function HubDownloads({
  courseId, downloads,
}: {
  courseId: string; downloads: HubDownload[];
}) {
  return (
    <section style={{ marginBottom: 36 }}>
      <div style={{
        fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '3px', color: 'var(--berry)', marginBottom: 18,
      }}>Downloads</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {downloads.map(dl => (
          <div key={dl.id || dl.file_name} style={{
            background: 'var(--white)', border: '1px solid var(--coco)',
            borderRadius: 'var(--radius-lg)',
            display: 'flex', alignItems: 'center', gap: 16, padding: '16px 20px',
          }}>
            <div style={{
              width: 52, height: 52, borderRadius: 10,
              background: 'var(--berry-pale)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--berry)', fontWeight: 800, fontSize: 11,
            }}>PDF</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--soy)' }}>{dl.title}</div>
              {dl.description && <div style={{
                fontSize: 12.5, color: 'rgba(48,48,48,0.55)', lineHeight: 1.5,
              }}>{dl.description}</div>}
            </div>
            <button onClick={() => {
              if (dl.id) downloadHubFile(courseId, dl.id, dl.file_name);
            }} style={{
              padding: '7px 16px', borderRadius: 'var(--radius-pill)',
              background: 'transparent', border: '1px solid var(--berry)',
              color: 'var(--berry)', fontWeight: 700, fontSize: 12, cursor: 'pointer',
            }}>Download</button>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 8: Verify in browser**

With dev servers running and an enrolled test user, navigate to `/course/<id>`. Hub tab should render the placeholder empty-state message. With a test admin user, optionally seed a hub row manually via DB console to see the sections appear.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/course/hub/
git commit -m "feat(hub): public HubView + six section components"
```

---

## Task 14: Admin Hub editor — form shell + Hero section

**Files:**
- Create: `frontend/src/pages/admin/AdminCourseHub.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the form shell**

```typescript
// frontend/src/pages/admin/AdminCourseHub.tsx
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { hubApi, HubPayload, HeroVariant } from '../../lib/api/hub';

const EMPTY: HubPayload = {
  hero_variant: 'berry', hero_eyebrow: '', hero_title_html: '', hero_body: '',
  contact_user_id: null, contact_name_override: '',
  contact_role: 'Kursleitung & Ernährungsberaterin',
  contact_email_override: '', contact_whatsapp_url: '', contact_photo_url: '',
  show_contact: true, show_live_calls: true, show_products: true, show_downloads: true,
  links: [], live_calls: [], products: [], downloads: [],
};

export default function AdminCourseHub() {
  const { courseId } = useParams<{ courseId: string }>();
  const nav = useNavigate();
  const [hub, setHub] = useState<HubPayload>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    if (!courseId) return;
    hubApi.getAdmin(courseId).then(setHub).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [courseId]);

  const save = async () => {
    if (!courseId) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await hubApi.save(courseId, hub);
      setHub(saved);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div style={{ padding: 20 }}>Lädt …</div>;

  return (
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <button onClick={() => nav(`/admin/course/${courseId}`)} style={{
          background: 'transparent', border: 'none', color: 'var(--berry)', cursor: 'pointer',
          fontSize: 13, fontWeight: 700,
        }}>← Zurück zum Kurs</button>
        <h1 style={{ fontSize: 18, textTransform: 'uppercase', letterSpacing: '-0.3px' }}>
          Mitgliederbereich bearbeiten
        </h1>
      </div>

      {error && <div style={{
        padding: 12, background: '#fde7e7', color: '#8b0000',
        borderRadius: 8, marginBottom: 16,
      }}>{error}</div>}

      <HeroSection hub={hub} setHub={setHub} />

      {/* Contact, Links, LiveCalls, Products, Downloads come in Task 15 */}

      <div style={{
        display: 'flex', gap: 12, justifyContent: 'flex-end',
        marginTop: 32, position: 'sticky', bottom: 0,
        background: 'var(--cream)', padding: '16px 0', borderTop: '1px solid var(--coco)',
      }}>
        <button onClick={() => nav(`/admin/course/${courseId}`)} disabled={saving} style={{
          padding: '10px 24px', borderRadius: 'var(--radius-pill)',
          background: 'transparent', border: '1.5px solid var(--coco)',
          color: 'var(--soy)', cursor: 'pointer', fontWeight: 700,
        }}>Verwerfen</button>
        <button onClick={save} disabled={saving} style={{
          padding: '10px 24px', borderRadius: 'var(--radius-pill)',
          background: savedFlash ? 'var(--green)' : 'var(--berry)',
          color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 700,
        }}>{saving ? 'Speichert …' : savedFlash ? '✓ Gespeichert' : 'Speichern'}</button>
      </div>
    </div>
  );
}

function HeroSection({
  hub, setHub,
}: { hub: HubPayload; setHub: (h: HubPayload) => void }) {
  const update = <K extends keyof HubPayload>(k: K, v: HubPayload[K]) =>
    setHub({ ...hub, [k]: v });
  return (
    <FormSection title="Hero">
      <Label>Farbvariante</Label>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {(['berry', 'dark', 'pale'] as HeroVariant[]).map(v => (
          <button key={v} onClick={() => update('hero_variant', v)} style={{
            padding: '8px 16px', borderRadius: 'var(--radius-pill)',
            border: `1.5px solid ${hub.hero_variant === v ? 'var(--berry)' : 'var(--coco)'}`,
            background: hub.hero_variant === v ? 'var(--berry-pale)' : 'transparent',
            color: hub.hero_variant === v ? 'var(--berry)' : 'var(--soy)',
            cursor: 'pointer', fontWeight: 700, textTransform: 'uppercase', fontSize: 11,
          }}>
            {v === 'berry' ? 'Berry' : v === 'dark' ? 'Dunkel' : 'Rosé'}
          </button>
        ))}
      </div>
      <Label>Eyebrow</Label>
      <TextInput value={hub.hero_eyebrow} onChange={v => update('hero_eyebrow', v)}
                 placeholder="KURS · GLUKOSE BALANCE APRIL 2026" />
      <Label>Titel (HTML: &lt;em&gt;, &lt;br&gt; erlaubt)</Label>
      <TextArea rows={3} value={hub.hero_title_html} onChange={v => update('hero_title_html', v)}
                placeholder="Willkommen in Deinem<br>persönlichen <em>Mitgliederbereich</em>" />
      <Label>Fließtext</Label>
      <TextArea rows={3} value={hub.hero_body} onChange={v => update('hero_body', v)}
                placeholder="Hier findest Du alle relevanten Links …" />
    </FormSection>
  );
}

// --- Shared tiny form primitives (also used by later sections) ---
export function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{
      background: 'var(--white)', borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--coco)', padding: '20px 24px', marginBottom: 20,
    }}>
      <h2 style={{
        fontSize: 14, textTransform: 'uppercase', letterSpacing: '2px',
        color: 'var(--berry)', fontWeight: 700, marginBottom: 16,
      }}>{title}</h2>
      {children}
    </section>
  );
}

export function Label({ children }: { children: React.ReactNode }) {
  return <div style={{
    fontSize: 11, fontWeight: 700, color: 'rgba(48,48,48,0.6)',
    textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6, marginTop: 4,
  }}>{children}</div>;
}

export function TextInput({ value, onChange, placeholder }:
  { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return <input value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
    style={inputBase} />;
}

export function TextArea({ value, onChange, rows = 3, placeholder }:
  { value: string; onChange: (v: string) => void; rows?: number; placeholder?: string }) {
  return <textarea value={value} onChange={e => onChange(e.target.value)} rows={rows}
    placeholder={placeholder} style={{ ...inputBase, fontFamily: 'inherit', resize: 'vertical' }} />;
}

export function Checkbox({ checked, onChange, label }:
  { checked: boolean; onChange: (b: boolean) => void; label: string }) {
  return (
    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 12 }}>
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
      <span style={{ fontSize: 13 }}>{label}</span>
    </label>
  );
}

const inputBase: React.CSSProperties = {
  width: '100%', padding: '9px 12px', borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--coco)', fontSize: 14, marginBottom: 12,
  background: 'var(--white)', fontFamily: 'var(--font-sans)',
  outline: 'none',
};
```

- [ ] **Step 2: Register route in `App.tsx`**

In `frontend/src/App.tsx`, add an import:

```typescript
import AdminCourseHub from './pages/admin/AdminCourseHub';
```

Inside the nested `<Routes>` block (protected area), add a new line after the `/admin/course/:courseId/module/:moduleId` route:

```tsx
<Route path="/admin/course/:courseId/hub" element={<AdminCourseHub />} />
```

- [ ] **Step 3: Verify in browser**

Navigate to `/admin/course/<some-id>/hub`. The form shell with Hero section should render, Speichern button should work (try changing the eyebrow, click Speichern, reload — value persists).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/admin/AdminCourseHub.tsx frontend/src/App.tsx
git commit -m "feat(hub): admin form shell with Hero section"
```

---

## Task 15: Admin editor — remaining sections

**Files:**
- Modify: `frontend/src/pages/admin/AdminCourseHub.tsx`

- [ ] **Step 1: Add Contact section**

In `AdminCourseHub.tsx`, add this below `HeroSection`:

```typescript
function ContactSection({
  hub, setHub, courseId,
}: { hub: HubPayload; setHub: (h: HubPayload) => void; courseId: string }) {
  const update = <K extends keyof HubPayload>(k: K, v: HubPayload[K]) =>
    setHub({ ...hub, [k]: v });
  const [uploading, setUploading] = useState(false);

  const handlePhotoUpload = async (file: File) => {
    setUploading(true);
    try {
      const { url } = await hubApi.uploadImage(courseId, 'contact_photo', file);
      update('contact_photo_url', url);
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Upload fehlgeschlagen');
    } finally {
      setUploading(false);
    }
  };

  return (
    <FormSection title="Ansprechpartnerin">
      <Checkbox checked={hub.show_contact} onChange={v => update('show_contact', v)} label="Anzeigen" />
      <Label>Name (Override)</Label>
      <TextInput value={hub.contact_name_override}
                 onChange={v => update('contact_name_override', v)}
                 placeholder="Nora Weweler" />
      <Label>Rolle</Label>
      <TextInput value={hub.contact_role} onChange={v => update('contact_role', v)} />
      <Label>E-Mail (Override)</Label>
      <TextInput value={hub.contact_email_override}
                 onChange={v => update('contact_email_override', v)}
                 placeholder="hallo@noraweweler.de" />
      <Label>WhatsApp-URL</Label>
      <TextInput value={hub.contact_whatsapp_url}
                 onChange={v => update('contact_whatsapp_url', v)}
                 placeholder="https://wa.me/49..." />
      <Label>Foto</Label>
      <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
        {hub.contact_photo_url && (
          <img src={hub.contact_photo_url} alt=""
               style={{ width: 60, height: 60, borderRadius: '50%', objectFit: 'cover' }} />
        )}
        <input type="file" accept="image/jpeg,image/png,image/webp"
               disabled={uploading}
               onChange={e => e.target.files?.[0] && handlePhotoUpload(e.target.files[0])} />
        {hub.contact_photo_url && (
          <button onClick={() => update('contact_photo_url', '')} style={smallRmBtn}>entfernen</button>
        )}
      </div>
    </FormSection>
  );
}

const smallRmBtn: React.CSSProperties = {
  background: 'transparent', border: 'none', color: 'var(--berry-dark)',
  cursor: 'pointer', fontSize: 12, textDecoration: 'underline',
};
```

- [ ] **Step 2: Add Links section**

```typescript
import { HubLink as HubLinkType, IconType } from '../../lib/api/hub';

function LinksSection({
  hub, setHub,
}: { hub: HubPayload; setHub: (h: HubPayload) => void }) {
  const update = (idx: number, patch: Partial<HubLinkType>) => {
    const next = hub.links.map((l, i) => i === idx ? { ...l, ...patch } : l);
    setHub({ ...hub, links: next });
  };
  const move = (idx: number, dir: -1 | 1) => {
    const t = idx + dir;
    if (t < 0 || t >= hub.links.length) return;
    const next = [...hub.links];
    [next[idx], next[t]] = [next[t], next[idx]];
    setHub({ ...hub, links: next.map((l, i) => ({ ...l, sort_order: i })) });
  };
  const add = () => setHub({
    ...hub,
    links: [...hub.links, {
      icon_type: 'link' as IconType, label: 'Neuer Link',
      sublabel: '', url: '', sort_order: hub.links.length,
    }],
  });
  const remove = (idx: number) =>
    setHub({ ...hub, links: hub.links.filter((_, i) => i !== idx) });

  return (
    <FormSection title="Wichtige Links">
      {hub.links.map((link, i) => (
        <div key={link.id || i} style={listItemStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => move(i, -1)} style={iconBtn}>↑</button>
              <button onClick={() => move(i, 1)} style={iconBtn}>↓</button>
            </div>
            <button onClick={() => remove(i)} style={smallRmBtn}>entfernen</button>
          </div>
          <Label>Icon</Label>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
            {(['book', 'video', 'wa', 'cal', 'link'] as IconType[]).map(t => (
              <button key={t} onClick={() => update(i, { icon_type: t })} style={{
                padding: '5px 12px', borderRadius: 'var(--radius-pill)',
                border: `1.5px solid ${link.icon_type === t ? 'var(--berry)' : 'var(--coco)'}`,
                background: link.icon_type === t ? 'var(--berry-pale)' : 'transparent',
                color: link.icon_type === t ? 'var(--berry)' : 'var(--soy)',
                cursor: 'pointer', fontWeight: 700, fontSize: 11,
              }}>{t === 'book' ? 'Kurs' : t === 'video' ? 'Live Call' : t === 'wa' ? 'WhatsApp' : t === 'cal' ? 'Kalender' : 'Link'}</button>
            ))}
          </div>
          <Label>Label</Label>
          <TextInput value={link.label} onChange={v => update(i, { label: v })} />
          <Label>Sublabel</Label>
          <TextInput value={link.sublabel} onChange={v => update(i, { sublabel: v })} />
          <Label>URL</Label>
          <TextInput value={link.url} onChange={v => update(i, { url: v })}
                     placeholder="https://..." />
        </div>
      ))}
      <button onClick={add} style={addBtn}>+ Link hinzufügen</button>
    </FormSection>
  );
}

const listItemStyle: React.CSSProperties = {
  border: '1px solid var(--coco)', borderRadius: 'var(--radius-md)',
  padding: '14px 16px', marginBottom: 10, background: 'var(--cream)',
};
const iconBtn: React.CSSProperties = {
  padding: '3px 10px', borderRadius: 8, border: '1px solid var(--coco)',
  background: 'var(--white)', cursor: 'pointer', fontSize: 12,
};
const addBtn: React.CSSProperties = {
  width: '100%', padding: 12, borderRadius: 'var(--radius-md)',
  border: '1.5px dashed var(--berry)', background: 'rgba(212,116,121,0.04)',
  color: 'var(--berry)', fontWeight: 700, cursor: 'pointer',
};
```

- [ ] **Step 3: Add LiveCallsSection, ProductsSection, DownloadsSection**

Append:

```typescript
import { HubLiveCall as LiveCallType, HubProduct as ProductType, HubDownload as DownloadType } from '../../lib/api/hub';

function LiveCallsSection({ hub, setHub }: { hub: HubPayload; setHub: (h: HubPayload) => void }) {
  const set = (next: LiveCallType[]) => setHub({ ...hub, live_calls: next });
  const update = (idx: number, patch: Partial<LiveCallType>) =>
    set(hub.live_calls.map((c, i) => i === idx ? { ...c, ...patch } : c));
  const move = (idx: number, dir: -1 | 1) => {
    const t = idx + dir;
    if (t < 0 || t >= hub.live_calls.length) return;
    const next = [...hub.live_calls];
    [next[idx], next[t]] = [next[t], next[idx]];
    set(next.map((c, i) => ({ ...c, sort_order: i })));
  };
  const add = () => set([...hub.live_calls, {
    tag: '', title: 'Neuer Call', body: '', sort_order: hub.live_calls.length,
  }]);
  const remove = (idx: number) => set(hub.live_calls.filter((_, i) => i !== idx));

  return (
    <FormSection title="Live Calls">
      <Checkbox checked={hub.show_live_calls}
                onChange={v => setHub({ ...hub, show_live_calls: v })} label="Anzeigen" />
      {hub.live_calls.map((c, i) => (
        <div key={c.id || i} style={listItemStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => move(i, -1)} style={iconBtn}>↑</button>
              <button onClick={() => move(i, 1)} style={iconBtn}>↓</button>
            </div>
            <button onClick={() => remove(i)} style={smallRmBtn}>entfernen</button>
          </div>
          <Label>Tag (optional)</Label>
          <TextInput value={c.tag} onChange={v => update(i, { tag: v })}
                     placeholder="LIVE CALLS" />
          <Label>Titel</Label>
          <TextInput value={c.title} onChange={v => update(i, { title: v })} />
          <Label>Body</Label>
          <TextArea rows={4} value={c.body} onChange={v => update(i, { body: v })} />
        </div>
      ))}
      <button onClick={add} style={addBtn}>+ Live Call hinzufügen</button>
    </FormSection>
  );
}

function ProductsSection({
  hub, setHub, courseId,
}: { hub: HubPayload; setHub: (h: HubPayload) => void; courseId: string }) {
  const set = (next: ProductType[]) => setHub({ ...hub, products: next });
  const update = (idx: number, patch: Partial<ProductType>) =>
    set(hub.products.map((p, i) => i === idx ? { ...p, ...patch } : p));
  const move = (idx: number, dir: -1 | 1) => {
    const t = idx + dir;
    if (t < 0 || t >= hub.products.length) return;
    const next = [...hub.products];
    [next[idx], next[t]] = [next[t], next[idx]];
    set(next.map((p, i) => ({ ...p, sort_order: i })));
  };
  const add = () => set([...hub.products, {
    label: '', title: 'Neues Produkt', description: '', cta_text: 'Zum Shop',
    url: '', image_url: '', highlight: false, sort_order: hub.products.length,
  }]);
  const remove = (idx: number) => set(hub.products.filter((_, i) => i !== idx));
  const uploadPhoto = async (idx: number, file: File) => {
    try {
      const { url } = await hubApi.uploadImage(courseId, 'product', file);
      update(idx, { image_url: url });
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Upload fehlgeschlagen');
    }
  };

  return (
    <FormSection title="Produkte">
      <Checkbox checked={hub.show_products}
                onChange={v => setHub({ ...hub, show_products: v })} label="Anzeigen" />
      {hub.products.map((p, i) => (
        <div key={p.id || i} style={listItemStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => move(i, -1)} style={iconBtn}>↑</button>
              <button onClick={() => move(i, 1)} style={iconBtn}>↓</button>
            </div>
            <button onClick={() => remove(i)} style={smallRmBtn}>entfernen</button>
          </div>
          <Label>Label (optional, z.B. Kategorie)</Label>
          <TextInput value={p.label} onChange={v => update(i, { label: v })} />
          <Label>Titel</Label>
          <TextInput value={p.title} onChange={v => update(i, { title: v })} />
          <Label>Beschreibung</Label>
          <TextArea rows={3} value={p.description} onChange={v => update(i, { description: v })} />
          <Label>CTA-Text</Label>
          <TextInput value={p.cta_text} onChange={v => update(i, { cta_text: v })} />
          <Label>URL</Label>
          <TextInput value={p.url} onChange={v => update(i, { url: v })}
                     placeholder="https://..." />
          <Label>Bild</Label>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 12 }}>
            {p.image_url && (
              <img src={p.image_url} alt=""
                   style={{ width: 80, height: 60, objectFit: 'cover', borderRadius: 6 }} />
            )}
            <input type="file" accept="image/jpeg,image/png,image/webp"
                   onChange={e => e.target.files?.[0] && uploadPhoto(i, e.target.files[0])} />
            {p.image_url && (
              <button onClick={() => update(i, { image_url: '' })} style={smallRmBtn}>
                entfernen
              </button>
            )}
          </div>
          <Checkbox checked={p.highlight}
                    onChange={v => update(i, { highlight: v })}
                    label="Als Highlight (berry-gradient) anzeigen" />
        </div>
      ))}
      <button onClick={add} style={addBtn}>+ Produkt hinzufügen</button>
    </FormSection>
  );
}

function DownloadsSection({
  hub, setHub, courseId,
}: { hub: HubPayload; setHub: (h: HubPayload) => void; courseId: string }) {
  const set = (next: DownloadType[]) => setHub({ ...hub, downloads: next });
  const update = (idx: number, patch: Partial<DownloadType>) =>
    set(hub.downloads.map((d, i) => i === idx ? { ...d, ...patch } : d));
  const move = (idx: number, dir: -1 | 1) => {
    const t = idx + dir;
    if (t < 0 || t >= hub.downloads.length) return;
    const next = [...hub.downloads];
    [next[idx], next[t]] = [next[t], next[idx]];
    set(next.map((d, i) => ({ ...d, sort_order: i })));
  };
  const remove = (idx: number) => set(hub.downloads.filter((_, i) => i !== idx));
  const uploadPdf = async (file: File) => {
    try {
      const info = await hubApi.uploadPdf(courseId, file);
      set([...hub.downloads, {
        title: info.file_name.replace(/\.pdf$/i, ''),
        description: '',
        file_path: info.file_path,
        file_name: info.file_name,
        file_size_kb: info.file_size_kb,
        sort_order: hub.downloads.length,
      }]);
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Upload fehlgeschlagen');
    }
  };

  return (
    <FormSection title="Downloads">
      <Checkbox checked={hub.show_downloads}
                onChange={v => setHub({ ...hub, show_downloads: v })} label="Anzeigen" />
      {hub.downloads.map((d, i) => (
        <div key={d.id || i} style={listItemStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => move(i, -1)} style={iconBtn}>↑</button>
              <button onClick={() => move(i, 1)} style={iconBtn}>↓</button>
            </div>
            <button onClick={() => remove(i)} style={smallRmBtn}>entfernen</button>
          </div>
          <Label>Titel</Label>
          <TextInput value={d.title} onChange={v => update(i, { title: v })} />
          <Label>Beschreibung</Label>
          <TextInput value={d.description} onChange={v => update(i, { description: v })} />
          <div style={{ fontSize: 12, color: 'rgba(48,48,48,0.5)' }}>
            Datei: {d.file_name} · {d.file_size_kb} KB
          </div>
        </div>
      ))}
      <label style={{ ...addBtn, display: 'block', textAlign: 'center' }}>
        + PDF hochladen
        <input type="file" accept="application/pdf" style={{ display: 'none' }}
               onChange={e => e.target.files?.[0] && uploadPdf(e.target.files[0])} />
      </label>
    </FormSection>
  );
}
```

- [ ] **Step 4: Wire all sections into the main component**

In the main `AdminCourseHub` component JSX, replace the `{/* Contact, Links, ... */}` comment with:

```tsx
<ContactSection hub={hub} setHub={setHub} courseId={courseId!} />
<LinksSection hub={hub} setHub={setHub} />
<LiveCallsSection hub={hub} setHub={setHub} />
<ProductsSection hub={hub} setHub={setHub} courseId={courseId!} />
<DownloadsSection hub={hub} setHub={setHub} courseId={courseId!} />
```

- [ ] **Step 5: Verify TypeScript**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Verify in browser**

Open `/admin/course/<id>/hub`. All sections render. Add/remove/reorder items, upload a PDF and an image (Bunny must be configured — if 503, that's a known deployment task). Click Speichern → reload → values persist.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/admin/AdminCourseHub.tsx
git commit -m "feat(hub): admin editor — contact, links, live calls, products, downloads"
```

---

## Task 16: Entry-point button on AdminCourseDetail

**Files:**
- Modify: `frontend/src/pages/admin/AdminCourseDetail.tsx`

- [ ] **Step 1: Read current file**

Run: `head -60 frontend/src/pages/admin/AdminCourseDetail.tsx`
Identify the header row (where the page title and existing buttons live).

- [ ] **Step 2: Add the button**

In the header row (adjacent to the existing title/back link), add:

```tsx
<Link to={`/admin/course/${courseId}/hub`} style={{
  padding: '8px 18px', borderRadius: 'var(--radius-pill)',
  background: 'var(--berry)', color: '#fff', textDecoration: 'none',
  fontSize: 13, fontWeight: 700, letterSpacing: '0.3px',
}}>
  Mitgliederbereich bearbeiten
</Link>
```

Ensure `Link` is imported from `react-router-dom` at the top of the file if it isn't already.

- [ ] **Step 3: Verify in browser**

Navigate to `/admin/course/<id>` — button appears; clicking it opens the hub editor.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/admin/AdminCourseDetail.tsx
git commit -m "feat(hub): 'Mitgliederbereich bearbeiten' entry button"
```

---

## Task 17: Smoke-test checklist + fix discovered issues

**Files:** none new — this task is the pre-deploy verification pass.

Each item below is **mandatory** before Task 18 (production deploy). If any fails, open an issue and fix in a new commit before continuing. Take a screenshot of the working state for each.

- [ ] **Step 1: Local end-to-end with seeded hub**

Run locally with a test user enrolled in a test course. Through the admin editor:
- [ ] Add 2 links (one with URL, one without)
- [ ] Add 2 live calls
- [ ] Upload 1 image for a product
- [ ] Upload 1 PDF
- [ ] Save, reload, confirm everything persists

- [ ] **Step 2: Public view as enrolled user**

Switch to the enrolled test user. Navigate to `/course/<id>`:
- [ ] Hub tab is default
- [ ] All populated sections visible
- [ ] Link with URL opens in new tab; link without URL is disabled with tooltip
- [ ] PDF download works (browser downloads file with original name)

- [ ] **Step 3: Public view as non-enrolled user**

Create/use a second test user without enrollment:
- [ ] `GET /course/<id>?tab=hub` → the HubView shows a fetch error (403 from backend)

- [ ] **Step 4: Mobile view**

Chrome DevTools iPhone preset at `/course/<id>`:
- [ ] Links are single-column
- [ ] Products stack without overflow
- [ ] Nothing breaks the viewport

- [ ] **Step 5: Tab URL behaviour**

- [ ] `/course/<id>` → hub shown, no `?tab` param
- [ ] Click "Inhalte" → URL becomes `/course/<id>?tab=lessons`
- [ ] Browser Back button returns to hub
- [ ] Direct bookmark `/course/<id>?tab=lessons` opens Lessons tab

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 7: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: zero errors.

- [ ] **Step 8: Commit any fixes discovered**

For each fix:

```bash
git add <files>
git commit -m "fix(hub): <what>"
```

---

## Task 18: Deploy to production

- [ ] **Step 1: Configure Bunny Storage env vars on Cloudron**

In the Cloudron Env UI for the Nora Videoplatform app, add:
- `BUNNY_STORAGE_ZONE` — name of the hub storage zone (create new in Bunny Dashboard if needed, takes ~5 min)
- `BUNNY_STORAGE_KEY` — the zone's access key (FTP/Storage password)
- `BUNNY_STORAGE_PULL_ZONE` — full URL of the pull zone, e.g. `https://nw-hub.b-cdn.net`

Restart the app from Cloudron UI to pick up new env vars.

- [ ] **Step 2: Confirm CI is green (optional)**

If `.github/workflows/deploy.yml` runs tests, the push triggers them. Otherwise, already run locally in Task 17.

- [ ] **Step 3: Push to main**

```bash
git push
```

Watch the GitHub Actions deploy log.

- [ ] **Step 4: Post-deploy smoke (on production)**

- [ ] Open `https://kose.noraweweler.de/admin/course/<real course id>/hub` as admin
- [ ] Edit one field (e.g., hero_eyebrow), save, reload, confirm persistence
- [ ] Upload one test PDF; download it
- [ ] Upload one test image (confirm Bunny URL)
- [ ] Open course detail as a real enrolled customer account (or impersonated via admin)
- [ ] Confirm Stripe-success-URL `/course/<id>` lands on hub tab (test with a Stripe test-mode checkout if possible)

- [ ] **Step 5: Announce to Nora**

Send her the Admin-URL + a short Loom/screen-recording walkthrough (2–3 minutes) of:
- Where the "Mitgliederbereich bearbeiten" button lives
- How to add/remove/reorder items
- That uploads happen immediately, saving writes the rest
- Where to find: WhatsApp-Gruppen-Link in WhatsApp settings, Meet-Link from Google Calendar event

- [ ] **Step 6: Pre-seed content deadline**

Agree with Nora on a calendar date (target: 2026-04-30 end of day) by which she has all 2–3 courses populated. That unlocks the LS-cancel letter.

---

## Self-review checklist

After writing the plan, verified:

**Spec coverage:**
- Scope per course (spec §2) — Task 2 adds `CourseHub` with `UNIQUE(course_id)`.
- Classic admin form (spec §2) — Tasks 14–15 build `/admin/course/:courseId/hub`.
- All 6 sections (spec §2) — HubLink, HubLiveCall, HubProduct, HubDownload + Hero + Contact fields on CourseHub (Task 2), section components (Task 13), editors (Task 15).
- Bunny image upload (spec §5) — Tasks 1, 8.
- Local PDFs (spec §10) — Tasks 4, 7, 6.
- Tabs navigation (spec §8) — Task 12.
- Global styling + Google Fonts (spec §9) — Task 11.
- Romie → Cormorant Garamond (spec §2) — Task 11 imports Cormorant via Google Fonts.
- Direct prod deploy (spec §2, §12) — Task 18.
- Pytest-minimal access-control (spec §11) — Tasks 5, 6, 7, 8, 9.
- Smoke checklist (spec §11) — Task 17.

**Placeholder scan:** No "TBD"/"TODO"/"implement later". Every code block shows what to write. The "paste body of CourseView" instruction in Task 12 is tracked by the verification step.

**Type consistency:**
- IDs are `str` everywhere (UUIDs).
- `HubPayload` / `HubLink` / `HubProduct` / `HubDownload` / `HubLiveCall` have matching field names between Python models, Pydantic schemas, and TypeScript types.
- `upload_image` / `delete_image` signatures match their usage in `admin_hub.py`.
- `_hub_to_payload` / `_load_hub` / `_ensure_access` are defined in Task 5 and reused in Task 9.

**Risks called out in spec §13:**
- Bunny image zone not configured → handled by `BunnyNotConfigured` with 503 response (Tasks 1, 8) + env-var setup in Task 18.
- Stripe redirect → explicit smoke step in Task 18.
- Direct prod deploy → mandatory smoke checklist in Task 17.

---

**Plan complete. Saved to `docs/superpowers/plans/2026-04-24-mitgliederbereich.md`.**

**Execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach?
