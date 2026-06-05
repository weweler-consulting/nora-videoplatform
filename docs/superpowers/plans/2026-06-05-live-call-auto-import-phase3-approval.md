# Live-Call Auto-Import — Phase 3: Freigabe-Flow (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine importierte (versteckte) Live-Call-Lektion wird Nora per **Mail mit 1-Klick-Buttons** gemeldet. „Freigeben & ankündigen" macht die Lektion sichtbar **und** verschickt die Ankündigung an die Kursteilnehmerinnen; „Verwerfen" löscht Lektion + Bunny-Video. Plus Admin-Liste „Anstehende Importe". Damit ist der ganze Flow hands-off.

**Architecture:** Signierter JWT-Token (über `secret_key`) in den Mail-Links → token-authentifizierte GET-Endpoints (HTML-Antwort, kein Login). Kern-Funktionen `_approve`/`_dismiss` (idempotent über `status`). Notify-Step im Loop mailt Nora für `status='imported'` & `notified_at IS NULL`. Ankündigung reuse: `_enrolled_users` + `send_announcement_email` + `Announcement`-Modell.

**Tech Stack:** FastAPI (HTMLResponse), PyJWT, bestehende E-Mail-/Announcement-Infra.

**Baut auf Phase 2** (Branch `feat/live-call-import`). Tabelle `live_call_imports` ist neu/undeployed → `notified_at` braucht KEINE Migration (create_all legt sie mit an).

---

## Task 1: Aktions-Token (JWT, signiert)

**Files:**
- Create: `app/core/live_call_token.py`
- Test: `tests/test_live_call_token.py`

- [ ] **Step 1: Failing Test**

`tests/test_live_call_token.py`:

```python
from app.core.live_call_token import create_action_token, verify_action_token


def test_token_roundtrip():
    tok = create_action_token("imp-1", "approve")
    assert verify_action_token(tok, "approve") == "imp-1"


def test_token_wrong_action_rejected():
    tok = create_action_token("imp-1", "approve")
    assert verify_action_token(tok, "dismiss") is None


def test_token_garbage_rejected():
    assert verify_action_token("nonsense", "approve") is None
```

- [ ] **Step 2: Test fehlschlagen lassen**

Run: `.venv/bin/python -m pytest tests/test_live_call_token.py -q`
Expected: FAIL (Modul fehlt).

- [ ] **Step 3: Implementierung**

`app/core/live_call_token.py`:

```python
"""Signierte 1-Klick-Tokens für die Live-Call-Freigabe (approve/dismiss).
JWT über settings.secret_key — stateless, kein DB-Token nötig. Idempotenz/
Einmaligkeit kommt aus dem Import-Status, nicht aus dem Token."""
from datetime import timedelta

import jwt

from app.core.config import settings
from app.core.time import utc_now

_ALGO = "HS256"
_EXP_DAYS = 30


def create_action_token(import_id: str, action: str) -> str:
    payload = {"lci": import_id, "act": action, "exp": utc_now() + timedelta(days=_EXP_DAYS)}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGO)


def verify_action_token(token: str, expected_action: str) -> str | None:
    """Gibt die import_id zurück, wenn Token gültig + Aktion passt; sonst None."""
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=[_ALGO])
    except jwt.PyJWTError:
        return None
    if data.get("act") != expected_action:
        return None
    return data.get("lci")
```

- [ ] **Step 4: Test bestehen lassen**

Run: `.venv/bin/python -m pytest tests/test_live_call_token.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/core/live_call_token.py tests/test_live_call_token.py
git commit -m "feat(live-call): signierte Aktions-Tokens (JWT) für 1-Klick-Freigabe"
```

---

## Task 2: Generischer Mailversand + Notify-Step + Loop

**Files:**
- Modify: `app/core/email.py` (generisches `send_simple_email`)
- Modify: `app/models/live_call.py` (`notified_at`)
- Modify: `app/core/config.py` (`live_call_notify_email`)
- Create: `app/core/live_call_notify.py`
- Modify: `app/core/live_call_loop.py` (Notify in den Loop)
- Test: `tests/test_live_call_notify.py`

- [ ] **Step 1: `send_simple_email` in `app/core/email.py`** (nach `_send_smtp`, reuse `get_smtp_config`):

```python
def send_simple_email(to_email: str, subject: str, html: str) -> bool:
    """Schlichte interne HTML-Mail (z.B. Live-Call-Freigabe an Nora). True wenn versendet."""
    config = get_smtp_config()
    if not config:
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["from_addr"]
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))
    _send_smtp(config, msg)
    return True
```

- [ ] **Step 2: `notified_at` in `app/models/live_call.py`** (in `LiveCallImport`, nach `published_at`):

```python
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 3: Config in `app/core/config.py`** (bei den anderen Feldern):

```python
    live_call_notify_email: Optional[str] = None  # NORA_LIVE_CALL_NOTIFY_EMAIL
```

- [ ] **Step 4: Failing Test**

`tests/test_live_call_notify.py`:

```python
import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course
from app.models.live_call import LiveCallSeries, LiveCallImport
from app.core import live_call_notify


@pytest.mark.asyncio
async def test_notify_sends_once_and_marks(session, monkeypatch):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="P"); session.add(series); await session.commit()
    imp = LiveCallImport(series_id=series.id, drive_file_id="f1", recording_name="P - 2026/10/02 19:14 WEST - Recording",
                         occurrence_at=datetime(2026, 10, 2, 19, 14), status="imported", lesson_id="les-1")
    session.add(imp); await session.commit()

    sent = []
    monkeypatch.setattr(live_call_notify, "send_simple_email", lambda to, subject, html: sent.append((to, subject, html)) or True)
    monkeypatch.setattr(live_call_notify.settings, "live_call_notify_email", "nora@noraweweler.de", raising=False)

    assert await live_call_notify.notify_pending_imports() == 1
    assert len(sent) == 1 and sent[0][0] == "nora@noraweweler.de"
    assert "approve?import_id=" in sent[0][2] and "dismiss?import_id=" in sent[0][2]

    session.expire_all()
    row = (await session.execute(_select(LiveCallImport).where(LiveCallImport.drive_file_id == "f1"))).scalar_one()
    assert row.notified_at is not None

    # Zweiter Lauf: schon notified → keine zweite Mail
    assert await live_call_notify.notify_pending_imports() == 0
```

- [ ] **Step 5: Test fehlschlagen lassen**

Run: `.venv/bin/python -m pytest tests/test_live_call_notify.py -q`
Expected: FAIL (Modul fehlt).

- [ ] **Step 6: Implementierung `app/core/live_call_notify.py`**

```python
"""Mailt Nora eine 1-Klick-Freigabe-Mail für neu importierte (versteckte)
Live-Call-Lektionen. Sendet einmal pro Import (notified_at), best-effort."""
import logging

from sqlalchemy import select

from app.core import db as db_module
from app.core.config import settings
from app.core.email import send_simple_email
from app.core.live_call_token import create_action_token
from app.core.time import utc_now
from app.models.live_call import LiveCallImport

logger = logging.getLogger(__name__)

PLATFORM_BASE_URL = "https://kurse.noraweweler.de"
_warned = False


def _email_html(imp: LiveCallImport) -> str:
    approve = f"{PLATFORM_BASE_URL}/api/v1/live-calls/approve?import_id={imp.id}&token={create_action_token(imp.id, 'approve')}"
    dismiss = f"{PLATFORM_BASE_URL}/api/v1/live-calls/dismiss?import_id={imp.id}&token={create_action_token(imp.id, 'dismiss')}"
    datum = imp.occurrence_at.strftime("%d.%m.%Y") if imp.occurrence_at else "—"
    return f"""<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;">
  <p style="font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#D47479;">Neue Live-Call-Aufzeichnung</p>
  <h2 style="margin:6px 0;color:#303030;">Live-Call vom {datum}</h2>
  <p style="color:#555;">Die Aufzeichnung ist importiert und liegt als <b>versteckte</b> Lektion bereit.</p>
  <p style="margin:24px 0;">
    <a href="{approve}" style="background:#D47479;color:#fff;text-decoration:none;font-weight:700;padding:12px 22px;border-radius:6px;">Freigeben &amp; ank&uuml;ndigen</a>
    &nbsp;&nbsp;
    <a href="{dismiss}" style="color:#888;text-decoration:underline;font-size:14px;">Verwerfen</a>
  </p>
  <p style="color:#aaa;font-size:12px;">Erst nach „Freigeben" wird die Lektion sichtbar und die Kundinnen-Mail verschickt.</p>
</div>"""


async def notify_pending_imports() -> int:
    """Mailt Nora für status='imported' & notified_at IS NULL. Gibt Anzahl Mails zurück."""
    global _warned
    to = settings.live_call_notify_email
    if not to:
        if not _warned:
            logger.warning("Live-Call-Notify: NORA_LIVE_CALL_NOTIFY_EMAIL nicht gesetzt — keine Freigabe-Mails.")
            _warned = True
        return 0
    sent = 0
    async with db_module.async_session() as db:
        rows = (await db.execute(
            select(LiveCallImport).where(LiveCallImport.status == "imported", LiveCallImport.notified_at.is_(None))
        )).scalars().all()
        for imp in rows:
            try:
                if send_simple_email(to, f"Neue Live-Call-Aufzeichnung vom {imp.occurrence_at.strftime('%d.%m.%Y') if imp.occurrence_at else ''} – freigeben?", _email_html(imp)):
                    imp.notified_at = utc_now()
                    sent += 1
            except Exception as e:
                logger.warning(f"Live-Call-Notify fehlgeschlagen ({imp.recording_name}): {e}")
        if sent:
            await db.commit()
    return sent
```

- [ ] **Step 7: Notify in den Loop** — `app/core/live_call_loop.py`, nach `import_pending()`:

```python
from app.core.live_call_notify import notify_pending_imports
# ... im try-Block nach await import_pending():
                await notify_pending_imports()
```

- [ ] **Step 8: Test + Smoke**

Run: `.venv/bin/python -m pytest tests/test_live_call_notify.py -q`
Expected: PASS.
Run: `NORA_SECRET_KEY=test-secret-key-at-least-32-characters-long-xxxx .venv/bin/python -c "import app.main"`
Expected: ok.

- [ ] **Step 9: Commit**

```bash
git add app/core/email.py app/models/live_call.py app/core/config.py app/core/live_call_notify.py app/core/live_call_loop.py tests/test_live_call_notify.py
git commit -m "feat(live-call): Freigabe-Mail an Nora (Notify-Step, einmalig, im Loop)"
```

---

## Task 3: Approve (Freigeben + Ankündigung)

**Files:**
- Modify: `app/api/live_calls.py` (Approve-Kern + Token-Endpoint + Ankündigungs-Helfer)
- Test: `tests/test_live_call_approval.py`

- [ ] **Step 1: Failing Test**

`tests/test_live_call_approval.py`:

```python
import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course, Module, Section, Lesson, Announcement
from app.models.live_call import LiveCallSeries, LiveCallImport
from app.core.live_call_token import create_action_token
import app.api.live_calls as lc
from tests.test_checkin import _mk_user, _enroll


async def _imported(session):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    module = Module(course_id=course.id, title="Live Call 02.10.2026", sort_order=0); session.add(module); await session.commit()
    section = Section(module_id=module.id, title="Aufzeichnung", sort_order=0); session.add(section); await session.commit()
    lesson = Lesson(section_id=section.id, title="Live-Call 02.10.2026", type="video", video_url="https://iframe.mediadelivery.net/embed/1/v", is_published=False, sort_order=0)
    session.add(lesson); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="P"); session.add(series); await session.commit()
    imp = LiveCallImport(series_id=series.id, drive_file_id="f1", recording_name="P - 2026/10/02 19:14 WEST - Recording",
                         occurrence_at=datetime(2026, 10, 2, 19, 14), status="imported", module_id=module.id, lesson_id=lesson.id)
    session.add(imp); await session.commit()
    return course, lesson, imp


@pytest.mark.asyncio
async def test_approve_publishes_and_announces(client, session, monkeypatch):
    course, lesson, imp = await _imported(session)
    klientin = await _mk_user(session, admin=False); await _enroll(session, klientin.id, course.id)
    sent = []
    monkeypatch.setattr(lc, "send_announcement_email", lambda **k: sent.append(k.get("to_email")) or True)

    tok = create_action_token(imp.id, "approve")
    r = await client.get(f"/api/v1/live-calls/approve?import_id={imp.id}&token={tok}")
    assert r.status_code == 200

    session.expire_all()
    les = (await session.execute(_select(Lesson).where(Lesson.id == lesson.id))).scalar_one()
    assert les.is_published is True
    row = (await session.execute(_select(LiveCallImport).where(LiveCallImport.id == imp.id))).scalar_one()
    assert row.status == "published" and row.published_at is not None
    assert klientin.email in sent
    ann = (await session.execute(_select(Announcement).where(Announcement.target_id == lesson.id))).scalar_one()
    assert ann.target_type == "lesson"

    # Idempotent: erneut → keine zweite Ankündigung
    sent.clear()
    r2 = await client.get(f"/api/v1/live-calls/approve?import_id={imp.id}&token={tok}")
    assert r2.status_code == 200 and sent == []


@pytest.mark.asyncio
async def test_approve_bad_token(client, session):
    _course, _lesson, imp = await _imported(session)
    r = await client.get(f"/api/v1/live-calls/approve?import_id={imp.id}&token=falsch")
    assert r.status_code == 400
```

- [ ] **Step 2: Test fehlschlagen lassen**

Run: `.venv/bin/python -m pytest tests/test_live_call_approval.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementierung** — in `app/api/live_calls.py` ergänzen (Imports + Kern + Endpoint):

```python
# --- zusätzliche Imports oben ---
from fastapi.responses import HTMLResponse
from app.core.email import send_announcement_email
from app.core.time import utc_now
from app.core.live_call_token import verify_action_token
from app.api.announcements import _enrolled_users, PLATFORM_BASE_URL
from app.models.course import Lesson, Announcement
from app.models.live_call import LiveCallImport


def _page(msg: str) -> str:
    return f"<!DOCTYPE html><html lang='de'><body style='font-family:Arial;text-align:center;padding:60px;color:#303030;'><h2>{msg}</h2></body></html>"


async def _send_lesson_announcement(db, course_id: str, lesson_id: str, subject: str, body: str) -> None:
    enrolled = await _enrolled_users(db, course_id)
    db.add(Announcement(course_id=course_id, target_type="lesson", target_id=lesson_id,
                        subject=subject, body=body, recipient_count=len(enrolled), created_by_user_id=None))
    cta_url = f"{PLATFORM_BASE_URL}/course/{course_id}/lesson/{lesson_id}"
    for u in enrolled:
        try:
            send_announcement_email(to_email=u.email, to_name=u.name or "", subject=subject, body_text=body, cta_url=cta_url)
        except Exception:
            pass


async def _approve(db, imp: LiveCallImport) -> None:
    if imp.status == "published":
        return  # idempotent — keine zweite Ankündigung
    if imp.status != "imported":
        raise HTTPException(409, f"Import im Status '{imp.status}' nicht freigebbar")
    series = (await db.execute(select(LiveCallSeries).where(LiveCallSeries.id == imp.series_id))).scalar_one()
    lesson = (await db.execute(select(Lesson).where(Lesson.id == imp.lesson_id))).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(404, "Lektion nicht gefunden")
    lesson.is_published = True
    datum = imp.occurrence_at.strftime("%d.%m.%Y") if imp.occurrence_at else ""
    subject = f"Die Aufzeichnung vom {datum} ist da 💛"
    body = ("Hallo,\n\ndie Aufzeichnung unseres letzten Live-Calls ist jetzt für dich im Kurs verfügbar. "
            "Schau sie dir in Ruhe an – und nutze, was für dich passt.\n\nViel Freude damit!")
    await _send_lesson_announcement(db, series.course_id, imp.lesson_id, subject, body)
    imp.status = "published"
    imp.published_at = utc_now()
    await db.commit()


@router.get("/approve", response_class=HTMLResponse)
async def approve_link(import_id: str, token: str, db: AsyncSession = Depends(get_db)):
    if verify_action_token(token, "approve") != import_id:
        return HTMLResponse(_page("Ungültiger oder abgelaufener Link."), status_code=400)
    imp = (await db.execute(select(LiveCallImport).where(LiveCallImport.id == import_id))).scalar_one_or_none()
    if not imp:
        return HTMLResponse(_page("Import nicht gefunden."), status_code=404)
    await _approve(db, imp)
    return HTMLResponse(_page("Freigegeben & angekündigt ✅ — die Lektion ist jetzt sichtbar."))
```

- [ ] **Step 4: Test bestehen lassen**

Run: `.venv/bin/python -m pytest tests/test_live_call_approval.py -q`
Expected: PASS (publish + announce + idempotenz + bad-token).

- [ ] **Step 5: Commit**

```bash
git add app/api/live_calls.py tests/test_live_call_approval.py
git commit -m "feat(live-call): Approve (Lektion sichtbar + Ankündigung), idempotent"
```

---

## Task 4: Dismiss (Verwerfen)

**Files:**
- Modify: `app/api/live_calls.py` (Dismiss-Kern + Endpoint)
- Test: `tests/test_live_call_dismiss.py`

- [ ] **Step 1: Failing Test**

`tests/test_live_call_dismiss.py`:

```python
import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course, Module, Section, Lesson
from app.models.live_call import LiveCallSeries, LiveCallImport
from app.core.live_call_token import create_action_token
import app.api.live_calls as lc


@pytest.mark.asyncio
async def test_dismiss_deletes_lesson_and_video(client, session, monkeypatch):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    module = Module(course_id=course.id, title="M", sort_order=0); session.add(module); await session.commit()
    section = Section(module_id=module.id, title="S", sort_order=0); session.add(section); await session.commit()
    lesson = Lesson(section_id=section.id, title="L", type="video", video_url="https://iframe.mediadelivery.net/embed/1/v", is_published=False, sort_order=0)
    session.add(lesson); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="P"); session.add(series); await session.commit()
    imp = LiveCallImport(series_id=series.id, drive_file_id="f1", recording_name="P - 2026/10/02 19:14 WEST - Recording",
                         occurrence_at=datetime(2026, 10, 2, 19, 14), status="imported", module_id=module.id, lesson_id=lesson.id)
    session.add(imp); await session.commit()

    deleted = []
    monkeypatch.setattr(lc, "delete_video_by_embed_url", lambda url: deleted.append(url))

    tok = create_action_token(imp.id, "dismiss")
    r = await client.get(f"/api/v1/live-calls/dismiss?import_id={imp.id}&token={tok}")
    assert r.status_code == 200

    session.expire_all()
    assert (await session.execute(_select(Lesson).where(Lesson.id == lesson.id))).scalar_one_or_none() is None
    assert deleted == ["https://iframe.mediadelivery.net/embed/1/v"]
    row = (await session.execute(_select(LiveCallImport).where(LiveCallImport.id == imp.id))).scalar_one()
    assert row.status == "dismissed"
```

- [ ] **Step 2: Test fehlschlagen lassen**

Run: `.venv/bin/python -m pytest tests/test_live_call_dismiss.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementierung** — in `app/api/live_calls.py` ergänzen:

```python
from app.integrations.bunny_stream import delete_video_by_embed_url


async def _dismiss(db, imp: LiveCallImport) -> None:
    if imp.status == "dismissed":
        return
    lesson = (await db.execute(select(Lesson).where(Lesson.id == imp.lesson_id))).scalar_one_or_none() if imp.lesson_id else None
    if lesson is not None:
        if lesson.video_url:
            delete_video_by_embed_url(lesson.video_url)
        await db.delete(lesson)
    imp.status = "dismissed"
    await db.commit()


@router.get("/dismiss", response_class=HTMLResponse)
async def dismiss_link(import_id: str, token: str, db: AsyncSession = Depends(get_db)):
    if verify_action_token(token, "dismiss") != import_id:
        return HTMLResponse(_page("Ungültiger oder abgelaufener Link."), status_code=400)
    imp = (await db.execute(select(LiveCallImport).where(LiveCallImport.id == import_id))).scalar_one_or_none()
    if not imp:
        return HTMLResponse(_page("Import nicht gefunden."), status_code=404)
    await _dismiss(db, imp)
    return HTMLResponse(_page("Verworfen ✅ — Lektion und Video wurden entfernt."))
```

- [ ] **Step 4: Test bestehen lassen**

Run: `.venv/bin/python -m pytest tests/test_live_call_dismiss.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/api/live_calls.py tests/test_live_call_dismiss.py
git commit -m "feat(live-call): Dismiss (Lektion + Bunny-Video löschen)"
```

---

## Task 5: Admin-Liste + Admin-Approve/Dismiss

**Files:**
- Modify: `app/api/live_calls.py` (Admin-Endpoints)
- Test: `tests/test_live_call_admin_list.py`

- [ ] **Step 1: Failing Test**

`tests/test_live_call_admin_list.py`:

```python
import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course, Module, Section, Lesson
from app.models.live_call import LiveCallSeries, LiveCallImport
import app.api.live_calls as lc
from tests.test_checkin import _mk_user, _enroll, _auth


@pytest.mark.asyncio
async def test_admin_list_and_approve(client, session, monkeypatch):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    module = Module(course_id=course.id, title="M", sort_order=0); session.add(module); await session.commit()
    section = Section(module_id=module.id, title="S", sort_order=0); session.add(section); await session.commit()
    lesson = Lesson(section_id=section.id, title="L", type="video", video_url="x", is_published=False, sort_order=0)
    session.add(lesson); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="P"); session.add(series); await session.commit()
    imp = LiveCallImport(series_id=series.id, drive_file_id="f1", recording_name="P - 2026/10/02 19:14 WEST - Recording",
                         occurrence_at=datetime(2026, 10, 2, 19, 14), status="imported", module_id=module.id, lesson_id=lesson.id)
    session.add(imp); await session.commit()

    admin = await _mk_user(session, admin=True)
    klientin = await _mk_user(session, admin=False); await _enroll(session, klientin.id, course.id)
    monkeypatch.setattr(lc, "send_announcement_email", lambda **k: True)

    r = await client.get("/api/v1/live-calls/imports?status=imported", headers=_auth(admin))
    assert r.status_code == 200 and any(i["id"] == imp.id for i in r.json())

    r2 = await client.post(f"/api/v1/live-calls/imports/{imp.id}/approve", headers=_auth(admin))
    assert r2.status_code == 200
    session.expire_all()
    assert (await session.execute(_select(LiveCallImport).where(LiveCallImport.id == imp.id))).scalar_one().status == "published"
```

- [ ] **Step 2: Test fehlschlagen lassen**

Run: `.venv/bin/python -m pytest tests/test_live_call_admin_list.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementierung** — in `app/api/live_calls.py` ergänzen:

```python
class ImportOut(BaseModel):
    id: str
    series_id: str
    recording_name: str
    occurrence_at: datetime | None
    status: str
    module_id: str | None
    lesson_id: str | None


@router.get("/imports", response_model=list[ImportOut])
async def list_imports(status: str | None = None, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    q = select(LiveCallImport).order_by(LiveCallImport.created_at.desc())
    if status:
        q = q.where(LiveCallImport.status == status)
    rows = (await db.execute(q)).scalars().all()
    return [ImportOut(id=r.id, series_id=r.series_id, recording_name=r.recording_name,
                      occurrence_at=r.occurrence_at, status=r.status, module_id=r.module_id, lesson_id=r.lesson_id) for r in rows]


@router.post("/imports/{import_id}/approve")
async def admin_approve(import_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    imp = (await db.execute(select(LiveCallImport).where(LiveCallImport.id == import_id))).scalar_one_or_none()
    if not imp:
        raise HTTPException(404, "Import nicht gefunden")
    await _approve(db, imp)
    return {"ok": True}


@router.post("/imports/{import_id}/dismiss")
async def admin_dismiss(import_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    imp = (await db.execute(select(LiveCallImport).where(LiveCallImport.id == import_id))).scalar_one_or_none()
    if not imp:
        raise HTTPException(404, "Import nicht gefunden")
    await _dismiss(db, imp)
    return {"ok": True}
```

(`datetime` ggf. oben importieren.)

- [ ] **Step 4: Test + volle Suite**

Run: `.venv/bin/python -m pytest tests/test_live_call_admin_list.py -q`
Expected: PASS.
Run: `.venv/bin/python -m pytest -q`
Expected: alle grün.

- [ ] **Step 5: Commit**

```bash
git add app/api/live_calls.py tests/test_live_call_admin_list.py
git commit -m "feat(live-call): Admin-Liste anstehender Importe + Admin-Approve/Dismiss"
```

---

## Self-Review (gegen den Spec)

- **Signierte 1-Klick-Tokens:** Task 1 ✓
- **Freigabe-Mail an Nora (einmalig, im Loop):** Task 2 ✓
- **Approve → Lektion sichtbar + Ankündigung (bestehendes System, idempotent):** Task 3 ✓
- **Dismiss → Lektion + Bunny-Video löschen:** Task 4 ✓
- **Admin-Liste + Admin-Aktionen:** Task 5 ✓
- **Platzhalter:** keine. **Typ-Konsistenz:** `create_action_token`/`verify_action_token`/`_approve`/`_dismiss`/`notify_pending_imports`/`send_simple_email`/`delete_video_by_embed_url` durchgängig.

## Danach

Task 9 aus Phase 2 (echter E2E-Durchstich mit OAuth+Bunny-ENV) + Admin-UI-Frontend (Mapping-Pflege + Pending-Liste) + Merge nach main.
