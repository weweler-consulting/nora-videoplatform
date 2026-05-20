# Announcement System V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nora kann mit einem Klick alle Teilnehmerinnen eines Kurses über ein neues Modul oder eine neue Lektion per E-Mail benachrichtigen. Versand erfolgt sofort.

**Architecture:** Additive Backend-Tabelle `announcements`, drei neue Admin-Endpoints unter `/api/v1/admin/courses/{course_id}/announcements`, neue Funktion `send_announcement_email` in `app/core/email.py`, neue Admin-Seite `/admin/course/:courseId/announcements`, ein Compose-Modal mit drei Einstiegen (Hub-Page, Modul-Header-Shortcut, Lektion-Item-Shortcut). Keine bestehende API, kein bestehendes Model, kein bestehender Route wird verändert.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Pydantic v2 (Backend); React 19 + TypeScript + Tailwind 4 + Radix Dialog (Frontend); pytest-asyncio + httpx AsyncClient (Tests).

**Spec:** `docs/superpowers/specs/2026-05-20-announcement-system-design.md`

**Live-Betrieb-Constraint:** Migration ist additiv (neue Tabelle, kein ALTER). Keine bestehende API-Signatur wird verändert. Rollback per Revert + Redeploy ist sicher.

---

## File Map

**Backend — neu:**
- `app/models/course.py` (modify: Announcement-Klasse hinzufügen am Ende)
- `app/schemas/announcement.py` (neu)
- `app/api/announcements.py` (neu)
- `app/core/email.py` (modify: `send_announcement_email` hinzufügen am Ende)
- `app/main.py` (modify: Router registrieren — eine Zeile)
- `tests/test_announcements.py` (neu)

**Frontend — neu:**
- `frontend/src/pages/admin/AdminCourseAnnouncements.tsx` (neu — Hub-Liste)
- `frontend/src/components/AnnouncementComposeModal.tsx` (neu)
- `frontend/src/App.tsx` (modify: Route hinzufügen)
- `frontend/src/lib/api.ts` (modify: 3 neue API-Methoden + Types)
- `frontend/src/pages/admin/AdminCourseDetail.tsx` (modify: Nav-Link zu Announcements)
- `frontend/src/pages/admin/AdminModuleDetail.tsx` (modify: 2 Shortcut-Buttons – Modul-Header + pro Lektion)

---

## Phase 1: Backend Foundation

### Task 1: Announcement Model

**Files:**
- Modify: `app/models/course.py` (am Ende anhängen)

- [ ] **Step 1: Append Announcement model**

Am Ende von `app/models/course.py` (nach `LessonProgress`-Klasse) hinzufügen:

```python
class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id: Mapped[str] = mapped_column(
        String, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String, nullable=False)  # "module" | "lesson"
    target_id: Mapped[str] = mapped_column(String, nullable=False)  # KEIN FK – Audit bleibt nach Löschung
    subject: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

- [ ] **Step 2: Verify model import path works**

Run: `cd /Users/justus/Developer/nora-videoplatform && python -c "from app.models.course import Announcement; print(Announcement.__tablename__)"`
Expected: `announcements`

- [ ] **Step 3: Commit**

```bash
git add app/models/course.py
git commit -m "feat(announcements): add Announcement model (additive)"
```

---

### Task 2: Pydantic Schemas

**Files:**
- Create: `app/schemas/announcement.py`

- [ ] **Step 1: Create schema file**

```python
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


TargetType = Literal["module", "lesson"]


class AnnouncementCreateRequest(BaseModel):
    target_type: TargetType
    target_id: str = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)


class AnnouncementPreviewResponse(BaseModel):
    suggested_subject: str
    suggested_body: str
    recipient_count: int
    target_title: str
    target_module_title: Optional[str] = None  # None for module-target


class CreatedByInfo(BaseModel):
    id: str
    name: str


class AnnouncementResponse(BaseModel):
    id: str
    course_id: str
    target_type: TargetType
    target_id: str
    target_title: Optional[str]  # None if target wurde gelöscht
    target_module_title: Optional[str]  # nur bei target_type=lesson
    subject: str
    body: str
    recipient_count: int
    sent_at: datetime
    created_by: Optional[CreatedByInfo]


class AnnouncementCreateResponse(BaseModel):
    announcement: AnnouncementResponse
    delivery_summary: dict  # {"sent": int, "failed": int}


class AnnouncementListResponse(BaseModel):
    announcements: list[AnnouncementResponse]
```

- [ ] **Step 2: Verify import works**

Run: `cd /Users/justus/Developer/nora-videoplatform && python -c "from app.schemas.announcement import AnnouncementCreateRequest; print(AnnouncementCreateRequest.model_fields)"`
Expected: Felder-Liste ohne Fehler.

- [ ] **Step 3: Commit**

```bash
git add app/schemas/announcement.py
git commit -m "feat(announcements): add Pydantic schemas"
```

---

### Task 3: Email-Funktion `send_announcement_email`

**Files:**
- Modify: `app/core/email.py` (am Ende anhängen)

- [ ] **Step 1: Append function**

Am Ende von `app/core/email.py`:

```python
def send_announcement_email(
    to_email: str,
    to_name: str,
    subject: str,
    body_text: str,
    cta_url: str,
    unsubscribe_url: str | None = None,
) -> bool:
    """Send an in-course announcement email. Returns True if dispatched."""
    config = get_smtp_config()
    if not config:
        return False

    # Convert body_text to HTML paragraphs (split on double newline = paragraph break,
    # single newline = <br>)
    paragraphs = []
    for para in body_text.split("\n\n"):
        para_clean = para.strip()
        if not para_clean:
            continue
        # HTML-escape minimal + line-breaks within paragraph
        escaped = (para_clean
                   .replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace("\n", "<br>"))
        paragraphs.append(f'<p style="margin: 0 0 16px 0;">{escaped}</p>')
    body_html_inner = "\n".join(paragraphs) if paragraphs else f'<p style="margin: 0 0 16px 0;">{body_text}</p>'

    greeting_html = f'<p style="margin: 0 0 16px 0;">Hallo {to_name},</p>'
    sign_off_html = '<p style="margin: 24px 0 0 0;">Liebe Gr&uuml;&szlig;e<br>Nora</p>'

    body_html = (
        f"{greeting_html}\n"
        f"{body_html_inner}\n"
        f"{_cta_button(cta_url, 'Jetzt ansehen')}\n"
        f'<p style="margin: 0 0 16px 0; color: #888; font-size: 13px;">'
        f'Falls der Button nicht funktioniert: '
        f'<a href="{cta_url}" style="color: #D47479;">{cta_url}</a></p>\n'
        f"{sign_off_html}"
    )
    html = _wrap_in_brand_template(body_html, unsubscribe_url=unsubscribe_url)

    text = f"Hallo {to_name},\n\n{body_text}\n\nJetzt ansehen: {cta_url}\n\nLiebe Gruesse\nNora"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["from_addr"]
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    _send_smtp(config, msg)
    return True
```

- [ ] **Step 2: Verify function imports cleanly**

Run: `cd /Users/justus/Developer/nora-videoplatform && python -c "from app.core.email import send_announcement_email; print(send_announcement_email.__name__)"`
Expected: `send_announcement_email`

- [ ] **Step 3: Commit**

```bash
git add app/core/email.py
git commit -m "feat(announcements): add send_announcement_email function"
```

---

## Phase 2: Backend API

### Task 4: API-Endpoint-Skeleton + Helper

**Files:**
- Create: `app/api/announcements.py`

- [ ] **Step 1: Create router skeleton with helpers**

```python
"""Admin endpoints for course announcements (V1: immediate send)."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.db import get_db
from app.core.email import send_announcement_email
from app.models.course import (
    Announcement,
    Course,
    Enrollment,
    Lesson,
    Module,
    Section,
)
from app.models.user import User
from app.schemas.announcement import (
    AnnouncementCreateRequest,
    AnnouncementCreateResponse,
    AnnouncementListResponse,
    AnnouncementPreviewResponse,
    AnnouncementResponse,
    CreatedByInfo,
)

router = APIRouter()

PLATFORM_BASE_URL = "https://kurse.noraweweler.de"


async def _require_course(db: AsyncSession, course_id: str) -> Course:
    course = (await db.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Kurs nicht gefunden")
    return course


async def _resolve_target(
    db: AsyncSession,
    course_id: str,
    target_type: str,
    target_id: str,
) -> tuple[str, Optional[str], Optional[str]]:
    """Resolve target. Returns (target_title, target_module_title, cta_url).

    Raises 422 if target doesn't belong to course.
    """
    if target_type == "module":
        module = (
            await db.execute(
                select(Module).where(and_(Module.id == target_id, Module.course_id == course_id))
            )
        ).scalar_one_or_none()
        if not module:
            raise HTTPException(
                status_code=422,
                detail="Modul gehört nicht zu diesem Kurs oder existiert nicht",
            )
        cta = f"{PLATFORM_BASE_URL}/course/{course_id}"
        return module.title, None, cta

    if target_type == "lesson":
        result = await db.execute(
            select(Lesson, Section, Module)
            .join(Section, Lesson.section_id == Section.id)
            .join(Module, Section.module_id == Module.id)
            .where(and_(Lesson.id == target_id, Module.course_id == course_id))
        )
        row = result.first()
        if not row:
            raise HTTPException(
                status_code=422,
                detail="Lektion gehört nicht zu diesem Kurs oder existiert nicht",
            )
        lesson, _section, module = row
        cta = f"{PLATFORM_BASE_URL}/course/{course_id}/lesson/{lesson.id}"
        return lesson.title, module.title, cta

    raise HTTPException(status_code=422, detail="Ungültiger target_type")


async def _enrolled_users(db: AsyncSession, course_id: str) -> list[User]:
    result = await db.execute(
        select(User).join(Enrollment, Enrollment.user_id == User.id).where(Enrollment.course_id == course_id)
    )
    return list(result.scalars().all())
```

- [ ] **Step 2: Verify imports**

Run: `cd /Users/justus/Developer/nora-videoplatform && python -c "from app.api.announcements import router; print(len(router.routes))"`
Expected: `0` (noch keine Routen registriert).

- [ ] **Step 3: Commit**

```bash
git add app/api/announcements.py
git commit -m "feat(announcements): api skeleton with helpers"
```

---

### Task 5: GET Preview Endpoint

**Files:**
- Modify: `app/api/announcements.py`

- [ ] **Step 1: Append preview endpoint**

```python
@router.get(
    "/{course_id}/announcements/preview",
    response_model=AnnouncementPreviewResponse,
)
async def preview_announcement(
    course_id: str,
    target_type: str,
    target_id: str,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementPreviewResponse:
    await _require_course(db, course_id)
    target_title, module_title, _cta = await _resolve_target(db, course_id, target_type, target_id)

    if target_type == "module":
        suggested_subject = f"Neues Modul: {target_title}"
        suggested_body = (
            f"in deinem Kurs ist ein neues Modul verfügbar:\n\n"
            f"{target_title}\n\n"
            f"Schau gleich rein und mach weiter."
        )
    else:
        suggested_subject = f"Neue Lektion in {module_title}: {target_title}"
        suggested_body = (
            f"in deinem Kurs ist eine neue Lektion verfügbar:\n\n"
            f"{module_title} – {target_title}\n\n"
            f"Schau gleich rein und mach weiter."
        )

    enrolled = await _enrolled_users(db, course_id)

    return AnnouncementPreviewResponse(
        suggested_subject=suggested_subject,
        suggested_body=suggested_body,
        recipient_count=len(enrolled),
        target_title=target_title,
        target_module_title=module_title,
    )
```

- [ ] **Step 2: Smoke-test import**

Run: `cd /Users/justus/Developer/nora-videoplatform && python -c "from app.api.announcements import router; print([r.path for r in router.routes])"`
Expected: Liste enthält `/{course_id}/announcements/preview`.

- [ ] **Step 3: Commit**

```bash
git add app/api/announcements.py
git commit -m "feat(announcements): GET preview endpoint"
```

---

### Task 6: POST Create + Send Endpoint

**Files:**
- Modify: `app/api/announcements.py`

- [ ] **Step 1: Append create endpoint**

```python
@router.post(
    "/{course_id}/announcements",
    response_model=AnnouncementCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_announcement(
    course_id: str,
    payload: AnnouncementCreateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementCreateResponse:
    course = await _require_course(db, course_id)
    target_title, module_title, cta_url = await _resolve_target(
        db, course_id, payload.target_type, payload.target_id
    )

    enrolled = await _enrolled_users(db, course_id)
    if not enrolled:
        raise HTTPException(
            status_code=422,
            detail="Keine aktiven Teilnehmerinnen für diesen Kurs",
        )

    sent = 0
    failed = 0
    for user in enrolled:
        try:
            ok = send_announcement_email(
                to_email=user.email,
                to_name=user.name or "",
                subject=payload.subject,
                body_text=payload.body,
                cta_url=cta_url,
            )
            if ok:
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    announcement = Announcement(
        course_id=course_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        subject=payload.subject,
        body=payload.body,
        recipient_count=len(enrolled),
        created_by_user_id=admin.id,
    )
    db.add(announcement)
    await db.commit()
    await db.refresh(announcement)

    return AnnouncementCreateResponse(
        announcement=AnnouncementResponse(
            id=announcement.id,
            course_id=announcement.course_id,
            target_type=announcement.target_type,  # type: ignore
            target_id=announcement.target_id,
            target_title=target_title,
            target_module_title=module_title,
            subject=announcement.subject,
            body=announcement.body,
            recipient_count=announcement.recipient_count,
            sent_at=announcement.sent_at,
            created_by=CreatedByInfo(id=admin.id, name=admin.name or ""),
        ),
        delivery_summary={"sent": sent, "failed": failed},
    )
```

- [ ] **Step 2: Commit**

```bash
git add app/api/announcements.py
git commit -m "feat(announcements): POST create+send endpoint"
```

---

### Task 7: GET List Endpoint

**Files:**
- Modify: `app/api/announcements.py`

- [ ] **Step 1: Append list endpoint + target-title enrichment helper**

Über den vorigen Endpoints (vor `_resolve_target` ist okay) den Enrichment-Helper hinzufügen:

```python
async def _enrich_target_titles(
    db: AsyncSession,
    course_id: str,
    rows: list[Announcement],
) -> dict[tuple[str, str], tuple[Optional[str], Optional[str]]]:
    """Liefert {(target_type, target_id): (target_title|None, module_title|None)}.

    Liefert None-Titel falls Target inzwischen gelöscht wurde.
    """
    module_ids = {a.target_id for a in rows if a.target_type == "module"}
    lesson_ids = {a.target_id for a in rows if a.target_type == "lesson"}

    out: dict[tuple[str, str], tuple[Optional[str], Optional[str]]] = {}

    if module_ids:
        result = await db.execute(select(Module).where(Module.id.in_(module_ids)))
        for m in result.scalars():
            out[("module", m.id)] = (m.title, None)

    if lesson_ids:
        result = await db.execute(
            select(Lesson, Module)
            .join(Section, Lesson.section_id == Section.id)
            .join(Module, Section.module_id == Module.id)
            .where(Lesson.id.in_(lesson_ids))
        )
        for lesson, module in result.all():
            out[("lesson", lesson.id)] = (lesson.title, module.title)

    return out
```

Dann am Ende der Datei den GET-List-Endpoint:

```python
@router.get(
    "/{course_id}/announcements",
    response_model=AnnouncementListResponse,
)
async def list_announcements(
    course_id: str,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementListResponse:
    await _require_course(db, course_id)

    result = await db.execute(
        select(Announcement)
        .where(Announcement.course_id == course_id)
        .order_by(Announcement.sent_at.desc())
    )
    rows = list(result.scalars().all())

    title_map = await _enrich_target_titles(db, course_id, rows)

    # Creator names auflösen
    creator_ids = {a.created_by_user_id for a in rows if a.created_by_user_id}
    creators: dict[str, User] = {}
    if creator_ids:
        result = await db.execute(select(User).where(User.id.in_(creator_ids)))
        for u in result.scalars():
            creators[u.id] = u

    items = []
    for a in rows:
        target_title, module_title = title_map.get((a.target_type, a.target_id), (None, None))
        creator = creators.get(a.created_by_user_id) if a.created_by_user_id else None
        items.append(
            AnnouncementResponse(
                id=a.id,
                course_id=a.course_id,
                target_type=a.target_type,  # type: ignore
                target_id=a.target_id,
                target_title=target_title,
                target_module_title=module_title,
                subject=a.subject,
                body=a.body,
                recipient_count=a.recipient_count,
                sent_at=a.sent_at,
                created_by=CreatedByInfo(id=creator.id, name=creator.name or "") if creator else None,
            )
        )

    return AnnouncementListResponse(announcements=items)
```

- [ ] **Step 2: Commit**

```bash
git add app/api/announcements.py
git commit -m "feat(announcements): GET list endpoint with target title enrichment"
```

---

### Task 8: Router-Registrierung

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Find existing router import block**

Suche nach `from app.api import ...` (etwa Zeile 1–40) und Add `announcements` zur Import-Liste:

Vor (Beispiel):
```python
from app.api import (
    admin_hub,
    attachments,
    auth,
    ...
)
```

Nach:
```python
from app.api import (
    admin_hub,
    announcements,
    attachments,
    auth,
    ...
)
```

- [ ] **Step 2: Register router**

Suche `app.include_router(admin_hub.router, prefix="/api/v1/admin/courses", tags=["admin_hub"])` (~Zeile 164) und füge **direkt danach** ein:

```python
app.include_router(announcements.router, prefix="/api/v1/admin/courses", tags=["announcements"])
```

- [ ] **Step 3: Smoke-test the app boots**

Run: `cd /Users/justus/Developer/nora-videoplatform && python -c "from app.main import app; print(sorted({r.path for r in app.routes if '/announcements' in r.path}))"`
Expected:
```
['/api/v1/admin/courses/{course_id}/announcements', '/api/v1/admin/courses/{course_id}/announcements/preview']
```

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat(announcements): wire announcements router into main"
```

---

### Task 9: Backend-Tests

**Files:**
- Create: `tests/test_announcements.py`

- [ ] **Step 1: Add tests covering core paths**

Den Test-Patterns aus `tests/test_hub.py` folgen (gleiche fixtures `client`, `session` aus `conftest.py`). Module/Section/Lesson helper sind in der bestehenden test_hub.py teilweise vorhanden, aber für diesen Test eigene Helper definieren.

```python
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
```

- [ ] **Step 2: Run tests, verify they all pass**

Run: `cd /Users/justus/Developer/nora-videoplatform && python -m pytest tests/test_announcements.py -v`
Expected: alle 7 Tests grün.

- [ ] **Step 3: Run full test suite to catch regressions**

Run: `cd /Users/justus/Developer/nora-videoplatform && python -m pytest -v`
Expected: alle Tests grün (keine bestehenden Tests gebrochen).

- [ ] **Step 4: Commit**

```bash
git add tests/test_announcements.py
git commit -m "test(announcements): cover create/preview/list paths + edge cases"
```

---

## Phase 3: Frontend Foundation

### Task 10: API-Client + TypeScript-Types

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Inspect existing api module shape**

Run: `head -80 /Users/justus/Developer/nora-videoplatform/frontend/src/lib/api.ts` und prüfe das Export-Pattern (vermutlich `export const api = { ... }` mit Methoden + separate `export type ...`).

- [ ] **Step 2: Add types**

Im Type-Block in `frontend/src/lib/api.ts` (oben, neben den anderen Types) hinzufügen:

```ts
export type AnnouncementTargetType = 'module' | 'lesson';

export type AnnouncementItem = {
  id: string;
  course_id: string;
  target_type: AnnouncementTargetType;
  target_id: string;
  target_title: string | null;
  target_module_title: string | null;
  subject: string;
  body: string;
  recipient_count: number;
  sent_at: string;
  created_by: { id: string; name: string } | null;
};

export type AnnouncementPreview = {
  suggested_subject: string;
  suggested_body: string;
  recipient_count: number;
  target_title: string;
  target_module_title: string | null;
};

export type AnnouncementCreateInput = {
  target_type: AnnouncementTargetType;
  target_id: string;
  subject: string;
  body: string;
};

export type AnnouncementCreateResult = {
  announcement: AnnouncementItem;
  delivery_summary: { sent: number; failed: number };
};
```

- [ ] **Step 3: Add API methods**

Im `api` Objekt (gleiche Datei) drei Methoden hinzufügen (analog zu bestehenden `getAdminCourse` / `createModule`):

```ts
async listAnnouncements(courseId: string): Promise<AnnouncementItem[]> {
  const r = await fetchWithAuth(`/api/v1/admin/courses/${courseId}/announcements`);
  if (!r.ok) throw new Error('Konnte Ankündigungen nicht laden');
  const data = await r.json();
  return data.announcements as AnnouncementItem[];
},

async previewAnnouncement(
  courseId: string,
  targetType: AnnouncementTargetType,
  targetId: string,
): Promise<AnnouncementPreview> {
  const params = new URLSearchParams({ target_type: targetType, target_id: targetId });
  const r = await fetchWithAuth(
    `/api/v1/admin/courses/${courseId}/announcements/preview?${params.toString()}`,
  );
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || 'Vorschau fehlgeschlagen');
  }
  return r.json();
},

async createAnnouncement(
  courseId: string,
  input: AnnouncementCreateInput,
): Promise<AnnouncementCreateResult> {
  const r = await fetchWithAuth(`/api/v1/admin/courses/${courseId}/announcements`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || 'Versand fehlgeschlagen');
  }
  return r.json();
},
```

**Hinweis:** `fetchWithAuth` ist der bestehende Helper. Wenn der Name anders ist (z. B. `apiFetch`), entsprechend anpassen. Verify by checking existing methods like `getAdminCourse`.

- [ ] **Step 4: Verify TypeScript build**

Run: `cd /Users/justus/Developer/nora-videoplatform/frontend && npx tsc -b`
Expected: kein Output (= success).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(announcements): add api client methods + types"
```

---

### Task 11: AnnouncementComposeModal Component

**Files:**
- Create: `frontend/src/components/AnnouncementComposeModal.tsx`

- [ ] **Step 1: Inspect a Radix Dialog usage example**

Run: `grep -rn "@radix-ui/react-dialog" /Users/justus/Developer/nora-videoplatform/frontend/src --include="*.tsx" | head -3`

Falls bereits ein Dialog im Code verwendet wird, sein Pattern als Vorlage nutzen. Falls nicht: das Component verwendet `<Dialog.Root>`, `<Dialog.Portal>`, `<Dialog.Overlay>`, `<Dialog.Content>`, `<Dialog.Title>`, `<Dialog.Description>`, `<Dialog.Close>`.

- [ ] **Step 2: Implement the modal**

```tsx
import { useEffect, useMemo, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X, Users } from 'lucide-react';
import {
  api,
  type AnnouncementCreateResult,
  type AnnouncementTargetType,
  type CourseDetail,
} from '../lib/api';

type Props = {
  courseId: string;
  course: CourseDetail; // damit wir Modul/Lektionen für den Picker haben
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSent?: (result: AnnouncementCreateResult) => void;
  preselectTarget?: { type: AnnouncementTargetType; id: string } | null;
};

type FlatTarget =
  | { type: 'module'; id: string; label: string }
  | { type: 'lesson'; id: string; label: string; moduleTitle: string };

function flattenTargets(course: CourseDetail): FlatTarget[] {
  const out: FlatTarget[] = [];
  for (const m of course.modules) {
    out.push({ type: 'module', id: m.id, label: `Modul: ${m.title}` });
    for (const s of m.sections ?? []) {
      for (const l of s.lessons ?? []) {
        out.push({
          type: 'lesson',
          id: l.id,
          label: `   ↳ ${l.title}`,
          moduleTitle: m.title,
        });
      }
    }
  }
  return out;
}

export default function AnnouncementComposeModal({
  courseId,
  course,
  open,
  onOpenChange,
  onSent,
  preselectTarget,
}: Props) {
  const targets = useMemo(() => flattenTargets(course), [course]);

  const initialKey = preselectTarget ? `${preselectTarget.type}:${preselectTarget.id}` : '';
  const [targetKey, setTargetKey] = useState<string>(initialKey);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [recipientCount, setRecipientCount] = useState<number | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset / preselect on open
  useEffect(() => {
    if (!open) return;
    const key = preselectTarget ? `${preselectTarget.type}:${preselectTarget.id}` : '';
    setTargetKey(key);
    setSubject('');
    setBody('');
    setRecipientCount(null);
    setError(null);
  }, [open, preselectTarget]);

  // Fetch preview when targetKey changes
  useEffect(() => {
    if (!open || !targetKey) return;
    const [type, id] = targetKey.split(':') as [AnnouncementTargetType, string];
    setLoadingPreview(true);
    setError(null);
    api
      .previewAnnouncement(courseId, type, id)
      .then((p) => {
        setSubject(p.suggested_subject);
        setBody(p.suggested_body);
        setRecipientCount(p.recipient_count);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoadingPreview(false));
  }, [open, targetKey, courseId]);

  const canSend =
    !!targetKey && subject.trim().length > 0 && body.trim().length > 0 && !sending && (recipientCount ?? 0) > 0;

  const handleSend = async () => {
    if (!canSend) return;
    const [type, id] = targetKey.split(':') as [AnnouncementTargetType, string];
    setSending(true);
    setError(null);
    try {
      const result = await api.createAnnouncement(courseId, {
        target_type: type,
        target_id: id,
        subject: subject.trim(),
        body: body.trim(),
      });
      onSent?.(result);
      onOpenChange(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Versand fehlgeschlagen');
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between p-5 border-b">
            <Dialog.Title className="text-lg font-semibold">Klientinnen informieren</Dialog.Title>
            <Dialog.Close className="text-gray-400 hover:text-gray-600">
              <X size={20} />
            </Dialog.Close>
          </div>

          <div className="p-5 space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Worüber informieren?</label>
              <select
                value={targetKey}
                onChange={(e) => setTargetKey(e.target.value)}
                className="w-full border rounded px-3 py-2"
              >
                <option value="">— bitte wählen —</option>
                {targets.map((t) => (
                  <option key={`${t.type}:${t.id}`} value={`${t.type}:${t.id}`}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Betreff</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                maxLength={200}
                className="w-full border rounded px-3 py-2"
                disabled={loadingPreview}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Nachricht</label>
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                maxLength={5000}
                rows={8}
                className="w-full border rounded px-3 py-2 font-sans"
                disabled={loadingPreview}
              />
              <p className="text-xs text-gray-500 mt-1">
                Klientinnen werden automatisch mit „Hallo [Name]" angesprochen, am Ende kommt die Grußformel. Du
                schreibst nur den Mittelteil.
              </p>
            </div>

            {recipientCount !== null && (
              <p className="text-sm text-gray-600 flex items-center gap-2">
                <Users size={14} />
                Wird an <strong>{recipientCount}</strong>{' '}
                {recipientCount === 1 ? 'Teilnehmerin' : 'Teilnehmerinnen'} gesendet.
              </p>
            )}

            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>

          <div className="flex justify-end gap-2 p-5 border-t bg-gray-50">
            <Dialog.Close className="px-4 py-2 rounded border text-sm">Abbrechen</Dialog.Close>
            <button
              onClick={handleSend}
              disabled={!canSend}
              className="px-4 py-2 rounded bg-[var(--nora-pink)] text-white text-sm font-medium disabled:opacity-50"
            >
              {sending ? 'Wird gesendet…' : 'Jetzt senden'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

**Type-Hinweis:** Falls `CourseDetail` keine `modules[].sections[].lessons[]` Struktur hat, sondern flacher ist, dann die `flattenTargets`-Funktion an die echte Struktur anpassen. Wenn `getAdminCourse` etwas anderes liefert, gleich beim Aufruf in der Hub-Page checken (Task 12).

- [ ] **Step 3: Verify TypeScript build**

Run: `cd /Users/justus/Developer/nora-videoplatform/frontend && npx tsc -b`
Expected: kein Output.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AnnouncementComposeModal.tsx
git commit -m "feat(announcements): compose modal component"
```

---

## Phase 4: Frontend Pages & Shortcuts

### Task 12: Announcements-Hub-Page

**Files:**
- Create: `frontend/src/pages/admin/AdminCourseAnnouncements.tsx`

- [ ] **Step 1: Implement the page**

```tsx
import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api, type AnnouncementItem, type CourseDetail } from '../../lib/api';
import AnnouncementComposeModal from '../../components/AnnouncementComposeModal';

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const diffMs = Date.now() - then;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return 'gerade eben';
  if (minutes < 60) return `vor ${minutes} Min.`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `vor ${hours} Std.`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `vor ${days} ${days === 1 ? 'Tag' : 'Tagen'}`;
  return new Date(iso).toLocaleDateString('de-DE');
}

export default function AdminCourseAnnouncements() {
  const { courseId } = useParams<{ courseId: string }>();
  const [items, setItems] = useState<AnnouncementItem[]>([]);
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [composeOpen, setComposeOpen] = useState(false);

  const load = () => {
    if (!courseId) return;
    setLoading(true);
    Promise.all([api.listAnnouncements(courseId), api.getAdminCourse(courseId)])
      .then(([list, c]) => {
        setItems(list);
        setCourse(c);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, [courseId]);

  if (loading || !course || !courseId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">Ankündigungen</h1>
          <p className="text-sm text-gray-500">
            Kurs:{' '}
            <Link to={`/admin/course/${courseId}`} className="text-[var(--nora-pink)] underline">
              {course.title}
            </Link>
          </p>
        </div>
        <button
          onClick={() => setComposeOpen(true)}
          className="px-4 py-2 bg-[var(--nora-pink)] text-white rounded font-medium text-sm"
        >
          Neue Ankündigung
        </button>
      </div>

      {items.length === 0 ? (
        <div className="bg-white border rounded-lg p-12 text-center text-gray-500">
          Noch keine Ankündigungen verschickt.
        </div>
      ) : (
        <div className="bg-white border rounded-lg divide-y">
          {items.map((a) => (
            <div key={a.id} className="p-5">
              <div className="flex items-start justify-between mb-2">
                <div className="font-medium">{a.subject}</div>
                <div className="text-xs text-gray-500 whitespace-nowrap ml-4">
                  {formatRelative(a.sent_at)}
                </div>
              </div>
              <div className="text-sm text-gray-600 mb-2">
                {a.target_type === 'module'
                  ? `Modul: ${a.target_title ?? '(gelöscht)'}`
                  : `Lektion: ${a.target_module_title ?? '?'} – ${a.target_title ?? '(gelöscht)'}`}
              </div>
              <div className="text-xs text-gray-500">
                Versendet an {a.recipient_count}{' '}
                {a.recipient_count === 1 ? 'Teilnehmerin' : 'Teilnehmerinnen'}
                {a.created_by ? ` · von ${a.created_by.name}` : ''}
              </div>
            </div>
          ))}
        </div>
      )}

      <AnnouncementComposeModal
        courseId={courseId}
        course={course}
        open={composeOpen}
        onOpenChange={setComposeOpen}
        onSent={() => {
          load();
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript build**

Run: `cd /Users/justus/Developer/nora-videoplatform/frontend && npx tsc -b`
Expected: kein Output.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/AdminCourseAnnouncements.tsx
git commit -m "feat(announcements): hub page listing announcements"
```

---

### Task 13: Route + Sidebar/Nav-Link

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/admin/AdminCourseDetail.tsx`

- [ ] **Step 1: Add route in App.tsx**

In `frontend/src/App.tsx` nach der bestehenden Zeile `<Route path="/admin/course/:courseId/hub" element={<AdminCourseHub />} />` (~Zeile 58) eine neue Zeile einfügen:

```tsx
<Route path="/admin/course/:courseId/announcements" element={<AdminCourseAnnouncements />} />
```

Und am Anfang der Datei den Import:

```tsx
import AdminCourseAnnouncements from './pages/admin/AdminCourseAnnouncements';
```

- [ ] **Step 2: Add nav-link to course admin view**

Inspect `AdminCourseDetail.tsx` und finde die Stelle, wo „Hub" / „Inhalte" / „Teilnehmerinnen" als Links/Tabs angezeigt werden (vermutlich oberhalb der Module-Liste). Füge dort einen Link zur neuen Page hinzu:

```tsx
import { Megaphone } from 'lucide-react';

<Link
  to={`/admin/course/${courseId}/announcements`}
  className="text-sm text-[var(--nora-pink)] hover:underline flex items-center gap-1"
>
  <Megaphone size={14} />
  Ankündigungen
</Link>
```

Position: zwischen den bestehenden Course-Admin-Links. Wenn die Struktur ein gemeinsames Nav-Bar-Element ist (z. B. ein `<nav>` mit mehreren `<Link>`-Children), dort einfügen.

- [ ] **Step 3: Verify TypeScript build + manual nav-render**

Run: `cd /Users/justus/Developer/nora-videoplatform/frontend && npx tsc -b`
Expected: kein Output.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages/admin/AdminCourseDetail.tsx
git commit -m "feat(announcements): route + nav link in course admin"
```

---

### Task 14: Shortcut-Buttons in AdminModuleDetail (Modul + pro Lektion)

**Files:**
- Modify: `frontend/src/pages/admin/AdminModuleDetail.tsx`

- [ ] **Step 1: Read current AdminModuleDetail to find module-header and lesson-row locations**

Run: `head -160 /Users/justus/Developer/nora-videoplatform/frontend/src/pages/admin/AdminModuleDetail.tsx`

Identifiziere:
- Wo der **Modul-Header** angezeigt wird (Modul-Titel, ggf. Edit/Delete-Buttons daneben)
- Wo die **Lektionen-Liste** gerendert wird (vermutlich `.map((lesson) => ...)`)

- [ ] **Step 2: Import modal + add state**

Oben in der Datei:

```tsx
import { Megaphone } from 'lucide-react';
import AnnouncementComposeModal from '../../components/AnnouncementComposeModal';
import { type AnnouncementTargetType } from '../../lib/api';
```

In der Komponente (zu den bestehenden useStates dazu):

```tsx
const [announceTarget, setAnnounceTarget] = useState<{ type: AnnouncementTargetType; id: string } | null>(null);
```

- [ ] **Step 3: Add modul-header shortcut**

Im Modul-Header (neben dem Modul-Titel oder bei den Modul-Actions) einen kleinen Button hinzufügen:

```tsx
<button
  onClick={() => setAnnounceTarget({ type: 'module', id: module.id })}
  className="text-xs text-gray-600 hover:text-[var(--nora-pink)] flex items-center gap-1"
  title="Klientinnen über dieses Modul informieren"
>
  <Megaphone size={14} />
  Ankündigen
</button>
```

(`module.id` durch die tatsächliche Variable für die Modul-ID ersetzen – im File evtl. `moduleId` aus useParams oder das `module`-Objekt aus dem State.)

- [ ] **Step 4: Add per-lesson shortcut**

In der Lesson-Map (neben den bestehenden Edit/Delete-Buttons):

```tsx
<button
  onClick={() => setAnnounceTarget({ type: 'lesson', id: lesson.id })}
  className="text-gray-500 hover:text-[var(--nora-pink)]"
  title="Klientinnen über diese Lektion informieren"
  aria-label="Lektion ankündigen"
>
  <Megaphone size={14} />
</button>
```

- [ ] **Step 5: Render modal at bottom of component (before closing JSX)**

```tsx
{course && courseId && (
  <AnnouncementComposeModal
    courseId={courseId}
    course={course}
    open={announceTarget !== null}
    onOpenChange={(open) => !open && setAnnounceTarget(null)}
    preselectTarget={announceTarget}
  />
)}
```

**Hinweis:** Falls die Komponente das vollständige `course`-Objekt nicht im State hat (nur z. B. das einzelne `module`), muss es nachgeladen werden. In dem Fall: in `useEffect` zusätzlich `api.getAdminCourse(courseId).then(setCourse)` und `course`-State ergänzen.

- [ ] **Step 6: Verify TypeScript build**

Run: `cd /Users/justus/Developer/nora-videoplatform/frontend && npx tsc -b`
Expected: kein Output.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/admin/AdminModuleDetail.tsx
git commit -m "feat(announcements): module + per-lesson shortcut buttons"
```

---

## Phase 5: Integration & Verification

### Task 15: End-to-End-Test im lokalen Dev-Stack

**Files:**
- (kein Code-Change, nur Verifikation)

- [ ] **Step 1: Start backend**

Run: `cd /Users/justus/Developer/nora-videoplatform && ./dev.sh` (oder bestehender Dev-Startup)
Erwartet: Backend läuft auf erwarteten Port (typisch 8000), Frontend (Vite) auf 5173.

- [ ] **Step 2: Open admin in browser, navigate to a course**

Open: `http://localhost:5173/admin/courses` → wähle einen Kurs mit mindestens einem Modul, einer Lektion, und mindestens einer enrolled Test-Teilnehmerin.

- [ ] **Step 3: Test 1 – Hub-Page Empty State**

Navigiere zu `/admin/course/<id>/announcements`.
Expected: Leere Liste mit „Noch keine Ankündigungen verschickt." Button „Neue Ankündigung" sichtbar.

- [ ] **Step 4: Test 2 – Compose über Hub**

Klick „Neue Ankündigung" → Modal öffnet → wähle ein Modul → Subject und Body werden auto-befüllt → Empfänger-Count zeigt korrekte Zahl → Klick „Jetzt senden".
Expected: Modal schließt, neuer Eintrag erscheint in der Liste.

- [ ] **Step 5: Test 3 – Modul-Shortcut**

Navigiere zu `/admin/course/<id>/module/<modid>`. Klick auf den „Ankündigen"-Button (Megaphone-Icon) im Header.
Expected: Modal öffnet, das passende Modul ist vorausgewählt.

- [ ] **Step 6: Test 4 – Lektion-Shortcut**

Bei einer Lektion in der Liste das Megaphone-Icon klicken.
Expected: Modal öffnet, die passende Lektion ist vorausgewählt.

- [ ] **Step 7: Test 5 – E-Mail-Empfang**

Lokale SMTP-Konfiguration prüfen (Mailpit/Mailcatcher? oder echter Test-SMTP?). Mail sollte ankommen mit korrektem Subject, Body, CTA-Link führt zur Modul- bzw. Lesson-Page.

- [ ] **Step 8: Test 6 – Regressionen prüfen**

Klick durch die bestehenden Admin-Pages (Kurs-Liste, Modul-Detail, Lektion-Liste, Hub): alle funktionieren wie vorher? Keine Layout-Verschiebungen, keine Konsolen-Fehler.

- [ ] **Step 9: Falls Issues gefunden**

Issues notieren und in separate Fix-Commits beheben (z. B. „fix(announcements): adjust modal width on mobile"). Erst weiter wenn alles 6/6 grün.

---

### Task 16: README / Doc Snippet

**Files:**
- (Optional) Modify: `README.md` oder `docs/` falls Feature-Doku üblich

- [ ] **Step 1: Skip if not standard**

Im Repo gibt's bisher kein zentrales Feature-Dokumentations-Muster. Wenn auch nicht für vergleichbare Features (z. B. Drip-Notifications) eine Doku existiert: skip diesen Task.

Falls doch eines existiert: kurzer Abschnitt in der entsprechenden Doku, mit Verweis auf die Spec.

- [ ] **Step 2: Commit (falls doc geändert)**

```bash
git add <files>
git commit -m "docs(announcements): describe announcement feature"
```

---

### Task 17: Final Sanity-Check vor Deploy

- [ ] **Step 1: Full test suite green**

Run: `cd /Users/justus/Developer/nora-videoplatform && python -m pytest -v`
Expected: alle Tests grün, keine Skips, keine Warnings über deprecated patterns die wir eingeführt haben.

- [ ] **Step 2: Frontend build clean**

Run: `cd /Users/justus/Developer/nora-videoplatform/frontend && npm run build`
Expected: Build success, kein TypeScript-Fehler, keine ESLint-Errors (Warnings okay).

- [ ] **Step 3: Visual diff against main**

Run: `git log --oneline main..HEAD`
Expected: ~15-17 saubere Commits, jeder mit klarer feat/test/fix-Message.

- [ ] **Step 4: Bereit für PR / push**

Wenn alles grün: bereit für Push. Deploy läuft automatisch via GitHub Actions (vgl. `CLAUDE.md`).

---

## Out of Scope (V2 – separater PR)

Diese Punkte sind explizit aus V1 ausgeklammert und werden erst nach Live-Feedback geplant:
- Scheduler (`scheduled_at` Spalte + Background-Worker)
- Post-Publish-Toast nach Lektion-Veröffentlichung
- „Schon vor X Tagen angekündigt"-Soft-Guard
- Last-Sent-Badge in Modul-/Lektions-Listen
- Open-/Click-Tracking
