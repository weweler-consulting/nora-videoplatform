# Live-Call Auto-Import — Phase 2: Core-Pipeline (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Erkannte Meet-Recordings automatisch in den richtigen Kurs importieren — als **versteckte** Lektion (hybride Platzierung per Datum), gesteuert über ein Serie→Kurs-Mapping. Ende der Phase: ein neues Recording erscheint von selbst als versteckte „Live-Call"-Lektion im richtigen Kurs. (Die 1-Klick-Freigabe + Ankündigung ist Phase 3.)

**Architecture:** Background-Loop (Muster `crm_sync_loop`) ruft **Detector** (Drive-Poll pro Serie, Prefix+Datum, Dedup) und **Importer** (Datum→Zielmodul, Drive→Bunny-Stream, versteckte Lektion). Mapping `LiveCallSeries(Kurs ↔ Prefix)`, 1:1, im Admin gepflegt mit Prefix-Vorschlag. Versteckte Lektionen via `Lesson.is_published=false` aus der Klientinnen-Auslieferung gefiltert.

**Tech Stack:** Python/FastAPI, SQLAlchemy(async), Bunny Stream, pytest. Drive-Client aus Phase 1 (`app/integrations/google_drive.py`).

**Referenz-Spec:** `docs/superpowers/specs/2026-06-05-live-call-auto-import-design.md`
**Mapping (entschieden):** Prefix `4-Wochen Glukose Balance Code Live Call` (Produkt 3, evergreen, 1 Eintrag) und `Glukose Balance Live Call (September 2026)` (Produkt 4, pro Quartals-Kohorte). Prefix = Teil VOR dem Datum, eindeutig je Zielkurs.

---

## Task 1: Datenmodelle `LiveCallSeries` + `LiveCallImport`

Neue Tabellen → `Base.metadata.create_all` legt sie beim Start an (kein ALTER nötig).

**Files:**
- Create: `app/models/live_call.py`
- Modify: `app/main.py` (Model-Registrierung-Import, analog `_checkin_models`)
- Test: `tests/test_live_call_models.py`

- [ ] **Step 1: Failing Test**

`tests/test_live_call_models.py`:

```python
import pytest
from sqlalchemy import select as _select

from app.models.live_call import LiveCallSeries, LiveCallImport
from app.models.course import Course


@pytest.mark.asyncio
async def test_series_and_import_roundtrip(session):
    course = Course(title="4-Wochen Code", is_active=True)
    session.add(course)
    await session.commit()

    series = LiveCallSeries(course_id=course.id, recording_name_prefix="4-Wochen Glukose Balance Code Live Call")
    session.add(series)
    await session.commit()

    imp = LiveCallImport(
        series_id=series.id, drive_file_id="drive-123",
        recording_name="4-Wochen Glukose Balance Code Live Call - 2026/10/02 19:14 WEST - Recording",
        status="new",
    )
    session.add(imp)
    await session.commit()

    row = (await session.execute(_select(LiveCallImport).where(LiveCallImport.drive_file_id == "drive-123"))).scalar_one()
    assert row.status == "new"
    assert row.series_id == series.id
    assert row.lesson_id is None and row.retry_count == 0
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `.venv/bin/python -m pytest tests/test_live_call_models.py -q`
Expected: FAIL (`No module named 'app.models.live_call'`).

- [ ] **Step 3: Implementierung**

`app/models/live_call.py`:

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.time import utc_now


class LiveCallSeries(Base):
    """Verknüpfung Recording-Namen-Prefix → Kurs (1:1). Einmal pro Kurs/Kohorte
    im Admin gesetzt. Der Prefix ist der Namensteil VOR dem Datum."""
    __tablename__ = "live_call_series"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id: Mapped[str] = mapped_column(String, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    recording_name_prefix: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class LiveCallImport(Base):
    """Ein erkanntes Recording + sein Import-/Freigabe-Zustand. drive_file_id ist
    der Dedup-Schlüssel (ein Recording = eine Zeile, egal wie oft der Loop läuft)."""
    __tablename__ = "live_call_imports"
    __table_args__ = (UniqueConstraint("drive_file_id", name="uq_live_call_drive_file"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id: Mapped[str] = mapped_column(String, ForeignKey("live_call_series.id", ondelete="CASCADE"), nullable=False, index=True)
    drive_file_id: Mapped[str] = mapped_column(String, nullable=False)
    recording_name: Mapped[str] = mapped_column(String, nullable=False)
    occurrence_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    module_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lesson_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # 'new' | 'imported' | 'published' | 'dismissed' | 'failed'
    status: Mapped[str] = mapped_column(String, nullable=False, default="new", server_default="new")
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

In `app/main.py` neben der bestehenden Check-in-Model-Registrierung ergänzen:

```python
from app.models import live_call as _live_call_models  # noqa: F401 — register Live-Call tables with Base
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `.venv/bin/python -m pytest tests/test_live_call_models.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models/live_call.py app/main.py tests/test_live_call_models.py
git commit -m "feat(live-call): Datenmodelle LiveCallSeries + LiveCallImport"
```

---

## Task 2: `Lesson.is_published` + Migration + Klientinnen-Filter

Versteckte Lektionen: neues Bool (Default sichtbar), aus der Klientinnen-Auslieferung gefiltert, im Admin weiter sichtbar.

**Files:**
- Modify: `app/models/course.py:58-75` (Lesson — Feld ergänzen)
- Modify: `app/main.py` (`_build_migration_statements`)
- Modify: `app/api/courses.py:72-80` (Klientinnen-Serving filtern)
- Test: `tests/test_lesson_visibility.py`

- [ ] **Step 1: Failing Test**

`tests/test_lesson_visibility.py`:

```python
import pytest
from app.models.course import Course, Module, Section, Lesson


async def _course_with_hidden_lesson(session):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    module = Module(course_id=course.id, title="M", sort_order=0); session.add(module); await session.commit()
    section = Section(module_id=module.id, title="S", sort_order=0); session.add(section); await session.commit()
    visible = Lesson(section_id=section.id, title="Sichtbar", type="video", is_published=True, sort_order=0)
    hidden = Lesson(section_id=section.id, title="Versteckt", type="video", is_published=False, sort_order=1)
    session.add_all([visible, hidden]); await session.commit()
    return course


@pytest.mark.asyncio
async def test_hidden_lesson_excluded_for_client(client, session):
    from tests.test_checkin import _mk_user, _enroll, _auth
    course = await _course_with_hidden_lesson(session)
    user = await _mk_user(session, admin=False)
    await _enroll(session, user.id, course.id)
    r = await client.get(f"/api/v1/courses/{course.id}", headers=_auth(user))
    titles = [l["title"] for m in r.json()["modules"] for s in m["sections"] for l in s["lessons"]]
    assert "Sichtbar" in titles and "Versteckt" not in titles
```

(Pfad/Response-Form ggf. an den realen Client-Endpoint anpassen — `GET /api/v1/courses/{id}` liefert `modules[].sections[].lessons[]`.)

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `.venv/bin/python -m pytest tests/test_lesson_visibility.py -q`
Expected: FAIL (`is_published` unbekannt bzw. versteckte Lektion erscheint).

- [ ] **Step 3: Implementierung**

In `app/models/course.py` in der `Lesson`-Klasse (nach `type`, ~Zeile 69):

```python
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
```

In `app/main.py` `_build_migration_statements()` zur Liste hinzufügen (gleicher Stil wie `hub_enabled`):

```python
        "ALTER TABLE lessons ADD COLUMN is_published BOOLEAN DEFAULT TRUE NOT NULL",
```

In `app/api/courses.py` dort, wo die Lektionen der Klientin gebaut werden (`for lesson in section.lessons:` ~Zeile 72), die versteckten überspringen:

```python
            for lesson in section.lessons:
                if not getattr(lesson, "is_published", True):
                    continue  # versteckte (auto-importierte, noch nicht freigegebene) Lektion
```

(NUR im Klientinnen-Serving. Der Admin-Endpoint `getAdminCourse` bleibt ungefiltert — er soll versteckte Lektionen zeigen.)

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `.venv/bin/python -m pytest tests/test_lesson_visibility.py -q`
Expected: PASS.

- [ ] **Step 5: Volle Suite (Migration bricht nichts)**

Run: `.venv/bin/python -m pytest -q`
Expected: alle grün.

- [ ] **Step 6: Commit**

```bash
git add app/models/course.py app/main.py app/api/courses.py tests/test_lesson_visibility.py
git commit -m "feat(live-call): Lesson.is_published + Klientinnen-Filter für versteckte Lektionen"
```

---

## Task 3: Detector (Drive-Poll → neue `LiveCallImport`-Zeilen)

**Files:**
- Create: `app/core/live_call_detector.py`
- Test: `tests/test_live_call_detector.py`

- [ ] **Step 1: Failing Test**

`tests/test_live_call_detector.py`:

```python
import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course
from app.models.live_call import LiveCallSeries, LiveCallImport
from app.core import live_call_detector


@pytest.mark.asyncio
async def test_detect_creates_rows_dedup(session, monkeypatch):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="4-Wochen Glukose Balance Code Live Call")
    session.add(series); await session.commit()

    fake = [
        {"id": "f1", "name": "4-Wochen Glukose Balance Code Live Call - 2026/10/02 19:14 WEST - Recording",
         "mimeType": "video/mp4", "modifiedTime": "2026-10-02T17:14:00Z"},
    ]
    monkeypatch.setattr(live_call_detector, "list_video_files", lambda folder, prefix, since: fake)
    monkeypatch.setattr(live_call_detector.settings, "meet_recordings_folder_id", "FOLDER", raising=False)

    n = await live_call_detector.detect_new_recordings()
    assert n == 1
    row = (await session.execute(_select(LiveCallImport).where(LiveCallImport.drive_file_id == "f1"))).scalar_one()
    assert row.status == "new"
    assert row.occurrence_at == datetime(2026, 10, 2, 19, 14)

    # Zweiter Lauf: Dedup über drive_file_id → kein zweiter Eintrag
    assert await live_call_detector.detect_new_recordings() == 0
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `.venv/bin/python -m pytest tests/test_live_call_detector.py -q`
Expected: FAIL (`No module named 'app.core.live_call_detector'`).

- [ ] **Step 3: Implementierung**

`app/core/live_call_detector.py`:

```python
"""Findet neue Meet-Recordings im Drive-Ordner und legt LiveCallImport-Zeilen an.
Dedup über drive_file_id → mehrfaches Laufen erzeugt keine Duplikate."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core import db as db_module
from app.core.config import settings
from app.core.live_call_parser import parse_occurrence_at, is_group_recording
from app.integrations.google_drive import list_video_files
from app.models.live_call import LiveCallSeries, LiveCallImport

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 21


async def detect_new_recordings() -> int:
    """Pro aktiver Serie den Ordner pollen, neue Videos als 'new'-Import anlegen.
    Gibt die Anzahl neu angelegter Zeilen zurück."""
    folder = settings.meet_recordings_folder_id
    if not folder:
        return 0
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    created = 0
    async with db_module.async_session() as db:
        series_rows = (await db.execute(
            select(LiveCallSeries).where(LiveCallSeries.active.is_(True))
        )).scalars().all()
        known = set((await db.execute(select(LiveCallImport.drive_file_id))).scalars().all())

        for series in series_rows:
            try:
                files = list_video_files(folder, series.recording_name_prefix, since)
            except Exception as e:  # Drive/Auth-Fehler → diese Runde überspringen
                logger.warning(f"Live-Call-Detector: Drive-Listing fehlgeschlagen ({series.recording_name_prefix}): {e}")
                continue
            for f in files:
                fid = f["id"]
                if fid in known or not is_group_recording(f["name"], series.recording_name_prefix):
                    continue
                db.add(LiveCallImport(
                    series_id=series.id, drive_file_id=fid, recording_name=f["name"],
                    occurrence_at=parse_occurrence_at(f["name"]), status="new",
                ))
                known.add(fid)
                created += 1
        if created:
            await db.commit()
            logger.info(f"Live-Call-Detector: {created} neue Recording(s) erkannt")
    return created
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `.venv/bin/python -m pytest tests/test_live_call_detector.py -q`
Expected: PASS (2 Assertions: Anlage + Dedup).

- [ ] **Step 5: Commit**

```bash
git add app/core/live_call_detector.py tests/test_live_call_detector.py
git commit -m "feat(live-call): Detector (Drive-Poll, Dedup → LiveCallImport)"
```

---

## Task 4: Hybride Platzierung (Datum → Zielmodul)

**Files:**
- Create: `app/core/live_call_placement.py`
- Test: `tests/test_live_call_placement.py`

- [ ] **Step 1: Failing Test**

`tests/test_live_call_placement.py`:

```python
import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course, Module, Section, Lesson
from app.core.live_call_placement import resolve_target_section


@pytest.mark.asyncio
async def test_fills_dated_placeholder(session):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    placeholder = Module(course_id=course.id, title="Live Call 02.10.2026", sort_order=5)
    session.add(placeholder); await session.commit()

    section_id, module_id = await resolve_target_section(session, course.id, datetime(2026, 10, 2, 19, 14))
    assert module_id == placeholder.id  # Datum traf den Platzhalter
    sec = (await session.execute(_select(Section).where(Section.id == section_id))).scalar_one()
    assert sec.module_id == placeholder.id


@pytest.mark.asyncio
async def test_creates_new_module_when_no_placeholder(session):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    other = Module(course_id=course.id, title="Modul 1", sort_order=0); session.add(other); await session.commit()

    section_id, module_id = await resolve_target_section(session, course.id, datetime(2026, 10, 9, 19, 14))
    new_mod = (await session.execute(_select(Module).where(Module.id == module_id))).scalar_one()
    assert new_mod.title == "Live Call 09.10.2026"
    assert new_mod.sort_order == 1  # max(0)+1


@pytest.mark.asyncio
async def test_placeholder_with_video_lesson_is_not_reused(session):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    mod = Module(course_id=course.id, title="Live Call 02.10.2026", sort_order=0); session.add(mod); await session.commit()
    sec = Section(module_id=mod.id, title="S", sort_order=0); session.add(sec); await session.commit()
    session.add(Lesson(section_id=sec.id, title="schon da", type="video", video_url="x", sort_order=0))
    await session.commit()

    _section_id, module_id = await resolve_target_section(session, course.id, datetime(2026, 10, 2, 19, 14))
    assert module_id != mod.id  # belegter Platzhalter → neues Modul
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `.venv/bin/python -m pytest tests/test_live_call_placement.py -q`
Expected: FAIL (`No module named 'app.core.live_call_placement'`).

- [ ] **Step 3: Implementierung**

`app/core/live_call_placement.py`:

```python
"""Hybride Platzierung: füllt ein dat. 'Live Call <Datum>'-Platzhaltermodul ohne
Video-Lektion, sonst legt es ein neues Modul am Ende an. Gibt (section_id, module_id)."""
from datetime import datetime

from sqlalchemy import select, func

from app.models.course import Module, Section, Lesson


def _date_variants(d: datetime) -> list[str]:
    """DE-Datumsformate, die in Modultiteln vorkommen können."""
    return [
        d.strftime("%d.%m.%Y"),   # 02.10.2026
        d.strftime("%-d.%-m.%Y"), # 2.10.2026
        d.strftime("%d.%m."),     # 02.10.
        d.strftime("%-d.%-m."),   # 2.10.
    ]


async def _find_placeholder(db, course_id: str, occurrence_at: datetime):
    """Ein Modul des Kurses, dessen Titel das Datum enthält und das keine Video-
    Lektion hat. None, wenn keins passt."""
    variants = _date_variants(occurrence_at)
    modules = (await db.execute(select(Module).where(Module.course_id == course_id))).scalars().all()
    for m in modules:
        title = m.title or ""
        if not any(v in title for v in variants):
            continue
        n_videos = (await db.execute(
            select(func.count(Lesson.id))
            .join(Section, Lesson.section_id == Section.id)
            .where(Section.module_id == m.id, Lesson.type == "video")
        )).scalar_one()
        if n_videos == 0:
            return m
    return None


async def _ensure_section(db, module_id: str) -> str:
    sec = (await db.execute(
        select(Section).where(Section.module_id == module_id).order_by(Section.sort_order)
    )).scalars().first()
    if sec:
        return sec.id
    sec = Section(module_id=module_id, title="Aufzeichnung", sort_order=0)
    db.add(sec)
    await db.flush()
    return sec.id


async def resolve_target_section(db, course_id: str, occurrence_at: datetime) -> tuple[str, str]:
    """(section_id, module_id) für die Live-Call-Lektion."""
    placeholder = await _find_placeholder(db, course_id, occurrence_at)
    if placeholder is not None:
        return await _ensure_section(db, placeholder.id), placeholder.id

    next_order = ((await db.execute(
        select(func.max(Module.sort_order)).where(Module.course_id == course_id)
    )).scalar() or 0) + 1
    module = Module(course_id=course_id, title=f"Live Call {occurrence_at.strftime('%d.%m.%Y')}", sort_order=next_order)
    db.add(module)
    await db.flush()
    section_id = await _ensure_section(db, module.id)
    return section_id, module.id
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `.venv/bin/python -m pytest tests/test_live_call_placement.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/core/live_call_placement.py tests/test_live_call_placement.py
git commit -m "feat(live-call): hybride Platzierung (Datum → Platzhalter/neues Modul)"
```

---

## Task 5: Bunny-Server-Upload (Drive-Datei → Bunny)

Erweitert `bunny_storage` um Server-seitigen Upload (kein TUS). Live gegen Bunny — Validierung im Importer-Smoke + bei Phase-2-Abschluss mit einem echten Recording.

**Files:**
- Modify: `app/integrations/bunny_storage.py`

- [ ] **Step 1: Implementierung**

In `app/integrations/bunny_storage.py` ergänzen (Reuse der vorhandenen `BUNNY_API_KEY`/`BUNNY_LIBRARY_ID`-Konfig + des Create-Video-Calls; an die dort vorhandenen Helfer/Namen anpassen):

```python
import os
import httpx

def upload_video_from_file(title: str, file_path: str) -> str:
    """Legt ein Bunny-Video an, lädt die Datei per PUT hoch, gibt die embed_url zurück.
    Server-seitig (für den Live-Call-Auto-Import), streamt die Datei vom Datenträger."""
    library_id = os.environ["BUNNY_LIBRARY_ID"]
    api_key = os.environ["BUNNY_API_KEY"]
    base = f"https://video.bunnycdn.com/library/{library_id}/videos"
    headers = {"AccessKey": api_key}

    # 1. Video-Objekt anlegen
    create = httpx.post(base, headers={**headers, "Content-Type": "application/json"},
                        json={"title": title}, timeout=30.0)
    create.raise_for_status()
    video_id = create.json()["guid"]

    # 2. Datei hochladen (PUT, gestreamt)
    with open(file_path, "rb") as fh:
        up = httpx.put(f"{base}/{video_id}", headers=headers, content=fh, timeout=None)
    up.raise_for_status()

    return f"https://iframe.mediadelivery.net/embed/{library_id}/{video_id}"
```

(Wenn `bunny_storage` bereits eine Create-Video- bzw. Embed-URL-Logik kapselt, diese wiederverwenden statt zu duplizieren — DRY. embed-URL-Format an die bestehende Konvention angleichen.)

- [ ] **Step 2: Import-Smoke-Test**

Run: `.venv/bin/python -c "import app.integrations.bunny_storage as b; print(hasattr(b, 'upload_video_from_file'))"`
Expected: `True`.

- [ ] **Step 3: Commit**

```bash
git add app/integrations/bunny_storage.py
git commit -m "feat(live-call): Bunny-Server-Upload (Datei → Video, embed_url)"
```

---

## Task 6: Importer (versteckte Lektion erzeugen)

**Files:**
- Create: `app/core/live_call_importer.py`
- Test: `tests/test_live_call_importer.py`

- [ ] **Step 1: Failing Test**

`tests/test_live_call_importer.py`:

```python
import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course, Lesson
from app.models.live_call import LiveCallSeries, LiveCallImport
from app.core import live_call_importer


@pytest.mark.asyncio
async def test_import_creates_hidden_lesson(session, monkeypatch, tmp_path):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    series = LiveCallSeries(course_id=course.id, recording_name_prefix="P"); session.add(series); await session.commit()
    imp = LiveCallImport(series_id=series.id, drive_file_id="f1",
                         recording_name="P - 2026/10/02 19:14 WEST - Recording",
                         occurrence_at=datetime(2026, 10, 2, 19, 14), status="new")
    session.add(imp); await session.commit()

    # Drive-Download + Bunny-Upload mocken (kein echtes Netz)
    monkeypatch.setattr(live_call_importer, "download_to_file", lambda fid, path: open(path, "wb").close())
    monkeypatch.setattr(live_call_importer, "upload_video_from_file",
                        lambda title, path: "https://iframe.mediadelivery.net/embed/1/vid")

    await live_call_importer.import_pending()

    session.expire_all()
    row = (await session.execute(_select(LiveCallImport).where(LiveCallImport.drive_file_id == "f1"))).scalar_one()
    assert row.status == "imported" and row.lesson_id is not None and row.module_id is not None
    lesson = (await session.execute(_select(Lesson).where(Lesson.id == row.lesson_id))).scalar_one()
    assert lesson.type == "video" and lesson.is_published is False
    assert lesson.video_url == "https://iframe.mediadelivery.net/embed/1/vid"

    # Idempotent: schon 'imported' → kein zweiter Durchlauf
    await live_call_importer.import_pending()
    rows = (await session.execute(_select(Lesson).where(Lesson.section_id == lesson.section_id))).scalars().all()
    assert len(rows) == 1
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `.venv/bin/python -m pytest tests/test_live_call_importer.py -q`
Expected: FAIL (`No module named 'app.core.live_call_importer'`).

- [ ] **Step 3: Implementierung**

`app/core/live_call_importer.py`:

```python
"""Verarbeitet 'new' LiveCallImport-Zeilen → versteckte Video-Lektion im richtigen
Kurs. Drive→Temp→Bunny gestreamt; jeder Schritt idempotent; Fehler → retry."""
import logging
import os
import tempfile

from sqlalchemy import select

from app.core import db as db_module
from app.core.live_call_placement import resolve_target_section
from app.integrations.google_drive import download_to_file
from app.integrations.bunny_storage import upload_video_from_file
from app.models.course import Lesson
from app.models.live_call import LiveCallSeries, LiveCallImport

logger = logging.getLogger(__name__)

MAX_RETRIES = 5


async def import_pending() -> int:
    """Alle 'new'-Importe verarbeiten. Gibt die Anzahl erfolgreich importierter zurück."""
    done = 0
    async with db_module.async_session() as db:
        rows = (await db.execute(
            select(LiveCallImport).where(
                LiveCallImport.status == "new", LiveCallImport.retry_count < MAX_RETRIES
            )
        )).scalars().all()
        for imp in rows:
            try:
                await _import_one(db, imp)
                done += 1
            except Exception as e:
                imp.retry_count += 1
                imp.last_error = str(e)[:500]
                if imp.retry_count >= MAX_RETRIES:
                    imp.status = "failed"
                    logger.warning(f"Live-Call-Import gibt auf: {imp.recording_name} ({e})")
                await db.commit()
        if done:
            logger.info(f"Live-Call-Importer: {done} Recording(s) importiert (versteckt)")
    return done


async def _import_one(db, imp: LiveCallImport) -> None:
    series = (await db.execute(
        select(LiveCallSeries).where(LiveCallSeries.id == imp.series_id)
    )).scalar_one()
    if imp.occurrence_at is None:
        raise ValueError("kein Datum im Recording-Namen geparst")

    section_id, module_id = await resolve_target_section(db, series.course_id, imp.occurrence_at)
    title = f"Live-Call {imp.occurrence_at.strftime('%d.%m.%Y')}"

    tmp = os.path.join(tempfile.gettempdir(), f"livecall_{imp.drive_file_id}.mp4")
    try:
        download_to_file(imp.drive_file_id, tmp)
        embed_url = upload_video_from_file(title, tmp)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    lesson = Lesson(
        section_id=section_id, title=title, type="video",
        video_url=embed_url, is_published=False, sort_order=0,
    )
    db.add(lesson)
    await db.flush()

    imp.module_id = module_id
    imp.lesson_id = lesson.id
    imp.status = "imported"
    await db.commit()
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `.venv/bin/python -m pytest tests/test_live_call_importer.py -q`
Expected: PASS (versteckte Lektion + Idempotenz).

- [ ] **Step 5: Commit**

```bash
git add app/core/live_call_importer.py tests/test_live_call_importer.py
git commit -m "feat(live-call): Importer (Drive→Bunny→versteckte Lektion, idempotent)"
```

---

## Task 7: Admin-Mapping-Endpoints (CRUD + Prefix-Vorschlag)

Folgt dem bestehenden Admin-Router-Muster (Auth via `require_admin`, wie in `app/api/checkin.py`/`courses.py`).

**Files:**
- Create: `app/api/live_calls.py`
- Modify: `app/main.py` (Router registrieren — analog `checkin`)
- Test: `tests/test_live_call_api.py`

- [ ] **Step 1: Failing Test**

`tests/test_live_call_api.py`:

```python
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
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `.venv/bin/python -m pytest tests/test_live_call_api.py -q`
Expected: FAIL (Endpoint/Modul fehlt).

- [ ] **Step 3: Implementierung**

`app/api/live_calls.py` (Schemas inline; Prefix-Vorschlag leitet aus Drive-Namen den Teil VOR `" - YYYY/..."` ab und filtert bereits gemappte raus):

```python
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.config import settings
from app.core.db import get_db
from app.integrations.google_drive import list_video_files
from app.models.live_call import LiveCallSeries
from app.models.user import User

router = APIRouter(prefix="/api/v1/live-calls", tags=["live-calls"])

_PREFIX_SPLIT = re.compile(r"\s*-\s*\d{4}/\d{2}/\d{2}\s")  # alles vor " - YYYY/MM/DD "


class SeriesCreate(BaseModel):
    course_id: str
    recording_name_prefix: str


class SeriesOut(BaseModel):
    id: str
    course_id: str
    recording_name_prefix: str
    active: bool


def list_all_video_names(folder: str, since: str) -> list[str]:
    """Alle Video-Namen im Ordner (prefixlos), für den Vorschlag."""
    return [f["name"] for f in list_video_files(folder, "", since)]


@router.post("/series", response_model=SeriesOut)
async def create_series(data: SeriesCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    prefix = data.recording_name_prefix.strip()
    if not prefix:
        raise HTTPException(400, "recording_name_prefix erforderlich")
    series = LiveCallSeries(course_id=data.course_id, recording_name_prefix=prefix)
    db.add(series)
    await db.commit()
    return SeriesOut(id=series.id, course_id=series.course_id, recording_name_prefix=series.recording_name_prefix, active=series.active)


@router.get("/series", response_model=list[SeriesOut])
async def list_series(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(LiveCallSeries))).scalars().all()
    return [SeriesOut(id=s.id, course_id=s.course_id, recording_name_prefix=s.recording_name_prefix, active=s.active) for s in rows]


@router.delete("/series/{series_id}")
async def delete_series(series_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(LiveCallSeries).where(LiveCallSeries.id == series_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Serie nicht gefunden")
    await db.delete(s)
    await db.commit()
    return {"ok": True}


@router.get("/suggest-prefixes", response_model=list[str])
async def suggest_prefixes(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Kandidaten-Prefixe aus realen Drive-Namen, die noch zu keiner Serie passen —
    zum Anklicken im Admin (kein Abtippen)."""
    folder = settings.meet_recordings_folder_id
    if not folder:
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = set((await db.execute(select(LiveCallSeries.recording_name_prefix))).scalars().all())
    out: list[str] = []
    for name in list_all_video_names(folder, since):
        prefix = _PREFIX_SPLIT.split(name, maxsplit=1)[0].strip()
        if prefix and prefix not in existing and not any(name.startswith(e) for e in existing) and prefix not in out:
            out.append(prefix)
    return out
```

In `app/main.py` Router registrieren (analog `checkin`):

```python
from app.api import ... , live_calls
app.include_router(live_calls.router)
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `.venv/bin/python -m pytest tests/test_live_call_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/api/live_calls.py app/main.py tests/test_live_call_api.py
git commit -m "feat(live-call): Admin-Mapping-Endpoints (Serie-CRUD + Prefix-Vorschlag)"
```

---

## Task 8: Loop-Verdrahtung

**Files:**
- Create: `app/core/live_call_loop.py`
- Modify: `app/main.py` (lifespan: Task starten/canceln)

- [ ] **Step 1: Implementierung**

`app/core/live_call_loop.py`:

```python
"""Background-Loop: erkennt neue Recordings und importiert sie als versteckte
Lektionen. No-op ohne OAuth-Config oder Ordner-ID."""
import asyncio
import logging

from app.core.config import settings
from app.core.live_call_detector import detect_new_recordings
from app.core.live_call_importer import import_pending

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 20 * 60
_warned = False


async def live_call_loop():
    global _warned
    while True:
        try:
            if settings.google_oauth_configured and settings.meet_recordings_folder_id:
                await detect_new_recordings()
                await import_pending()
            elif not _warned:
                logger.warning("Live-Call-Import nicht konfiguriert (OAuth/Folder-ID) — Loop wartet.")
                _warned = True
        except Exception as e:
            logger.error(f"Live-Call-Loop-Fehler: {e}", exc_info=True)
        await asyncio.sleep(INTERVAL_SECONDS)
```

In `app/main.py` im `lifespan` neben den anderen Tasks:

```python
from app.core.live_call_loop import live_call_loop
# ... in lifespan, bei den create_task-Aufrufen:
live_call_task = asyncio.create_task(live_call_loop())
# ... beim Shutdown:
live_call_task.cancel()
```

- [ ] **Step 2: Smoke + volle Suite**

Run: `NORA_SECRET_KEY=test-secret-key-at-least-32-characters-long-xxxx .venv/bin/python -c "import app.main"`
Expected: kein Fehler.
Run: `.venv/bin/python -m pytest -q`
Expected: alle grün.

- [ ] **Step 3: Commit**

```bash
git add app/core/live_call_loop.py app/main.py
git commit -m "feat(live-call): Import-Loop verdrahtet (detect → import, 20-Min-Intervall)"
```

---

## Task 9: End-to-End-Validierung mit echtem Recording (manuell)

- [ ] **Step 1** Eine `LiveCallSeries` für einen Testkurs anlegen (Prefix `Live Call | Glukose Balance` — die echten Spike-Recordings).
- [ ] **Step 2** Loop einmal manuell triggern (oder `detect_new_recordings()` + `import_pending()` in einem Skript) mit gesetzter OAuth-ENV.
- [ ] **Step 3** Prüfen: versteckte Video-Lektion im Kurs angelegt, Bunny-Embed spielt, in der Klientinnen-Ansicht **nicht** sichtbar, im Admin sichtbar.
- [ ] **Step 4** Findings (Bunny-Upload-Tempo, embed-URL-Format) im Spec-Abschnitt „Spike-Ergebnisse" ergänzen.

---

## Self-Review (gegen den Spec)

- **Datenmodell** (LiveCallSeries/LiveCallImport/Lesson.is_published): Tasks 1–2 ✓
- **Erkennung** (Drive-Poll, Prefix+Datum, Dedup): Task 3 ✓
- **Hybride Platzierung** (Datum → Platzhalter/neu): Task 4 ✓
- **Drive→Bunny streamen + versteckte Lektion** (idempotent): Tasks 5–6 ✓
- **Serie→Kurs-Mapping-Admin + Prefix-Vorschlag** (kein Abtippen): Task 7 ✓
- **Loop** (No-op ohne Config): Task 8 ✓
- **Platzhalter-Scan:** keine — jeder Code-Step vollständig.
- **Typ-Konsistenz:** `detect_new_recordings`/`import_pending`/`resolve_target_section`/`upload_video_from_file`/`download_to_file`/`is_published`/`status`-Werte durchgängig identisch.

## Nicht in diesem Plan (Phase 3)

1-Klick-Freigabe-Mail (signierter Token) → `Lesson.is_published=true` + Ankündigung über das bestehende System; Verwerfen (Lektion + Bunny-Video löschen); Admin-Liste „Anstehende Live-Call-Importe". Default-Ankündigungstext.
