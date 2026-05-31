# Hub-Übernahme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Beim Anlegen eines neuen Kurses kann der Admin den Hub (Mitgliederbereich) eines bestehenden Kurses als Vorlage übernehmen, statt ihn manuell neu aufzusetzen.

**Architecture:** Ein neuer Admin-Endpoint kopiert die Hub-Inhalte (Hero, Kontakt-Texte, Links, Live-Calls, Produkt-Texte) von einem Quellkurs in den — bei der Kurs-Erstellung ohnehin automatisch angelegten, leeren — Hub des Zielkurses. Eigene Binär-Assets (Produktbilder, Kontaktfoto, PDF-Downloads) werden bewusst **nicht** kopiert, weil Quelle und Ziel sonst dieselbe Bunny-URL teilen würden und ein späteres Bild-Update am neuen Hub das Bild des alten Kurses löschen würde (`admin_put_hub` löscht verwaiste Bunny-Assets). Diese werden im neuen Hub neu hochgeladen. Das Frontend bekommt im "Neuer Kurs"-Formular ein optionales Dropdown "Hub übernehmen von …".

**Tech Stack:** FastAPI + SQLAlchemy (async) Backend, React + TypeScript Frontend, pytest/httpx Tests.

**Scope-Entscheidungen (bewusst, nicht vergessen):**
- Kopiert werden: alle Hero-Felder, Kontakt-Textfelder, Visibility-Flags, `links`, `live_calls`, `products` (ohne `image_url`).
- **Nicht** kopiert: `contact_photo_url`, `products[].image_url`, `downloads` (alles eigene Binär-Assets) → Nora lädt diese pro Runde neu hoch.
- Übernahme nur in einen **leeren** Ziel-Hub (kein `links`/`live_calls`/`products`) → 409 sonst. Schützt vor versehentlichem Datenverlust und vor dem geteilten-Asset-Problem.
- Live-Call-Termine (`tag`, z.B. `mo-20:00`) werden mitkopiert und müssen pro Runde manuell angepasst werden — Vorlage spart trotzdem den Großteil.

---

### Task 1: Backend — Copy-Hub-Endpoint

**Files:**
- Modify: `app/api/admin_hub.py` (Helper `_load_hub_readonly` hinzufügen + neuer Endpoint am Ende der Datei)
- Test: `tests/test_hub_copy.py` (neu)

Kontext (bereits vorhandene Importe in `app/api/admin_hub.py`, NICHT erneut hinzufügen): `select` (Z. 8), `selectinload` (Z. 108), `HTTPException`/`Depends` (Z. 7), `require_admin` (Z. 11), `CourseHub` (Z. 15), `HubDownload, HubLink, HubLiveCall, HubProduct` (Z. 112), `_hub_to_payload` (Z. 110), `_require_course` (Z. 34), `_load_or_create_hub` (Z. 123).

- [ ] **Step 1: Write the failing tests**

Erstelle `tests/test_hub_copy.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hub_copy.py -v`
Expected: FAIL — alle 4 Tests mit 404 (Route existiert noch nicht) bzw. AssertionError.

- [ ] **Step 3: Add the read-only source-hub loader**

In `app/api/admin_hub.py`, direkt **nach** der Funktion `_load_or_create_hub` (endet Z. 144) einfügen:

```python
async def _load_hub_readonly(db: AsyncSession, course_id: str) -> CourseHub | None:
    """Load a hub with all children for read-only copying. No side effects."""
    result = await db.execute(
        select(CourseHub).where(CourseHub.course_id == course_id).options(
            selectinload(CourseHub.links),
            selectinload(CourseHub.live_calls),
            selectinload(CourseHub.products),
            selectinload(CourseHub.downloads),
        )
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 4: Add the copy endpoint**

In `app/api/admin_hub.py`, am **Ende der Datei** (nach `admin_put_hub`, nach Z. 244) einfügen:

```python
@router.post("/{course_id}/hub/copy-from/{source_course_id}", response_model=HubPayload)
async def copy_hub_from(
    course_id: str,
    source_course_id: str,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Copy a source course's hub (look + structure) into an EMPTY target hub.

    Owned binary assets are intentionally NOT copied (product images, contact
    photo, PDF downloads): source and target would otherwise share one Bunny
    URL, and editing the new hub later would delete the old course's asset.
    Those are re-uploaded per round.
    """
    if course_id == source_course_id:
        raise HTTPException(status_code=400, detail="Quell- und Zielkurs sind identisch")
    await _require_course(db, course_id)
    await _require_course(db, source_course_id)

    target = await _load_or_create_hub(db, course_id)
    if target.links or target.live_calls or target.products:
        raise HTTPException(status_code=409, detail="Ziel-Hub ist nicht leer")

    source = await _load_hub_readonly(db, source_course_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Quellkurs hat keinen Hub")

    # Hero
    target.hero_variant = source.hero_variant
    target.hero_eyebrow = source.hero_eyebrow
    target.hero_title_html = source.hero_title_html
    target.hero_body = source.hero_body
    # Contact (Textfelder; Foto bleibt leer — eigenes Asset)
    target.contact_user_id = source.contact_user_id
    target.contact_name_override = source.contact_name_override
    target.contact_role = source.contact_role
    target.contact_email_override = source.contact_email_override
    target.contact_whatsapp_url = source.contact_whatsapp_url
    # Visibility-Flags
    target.show_contact = source.show_contact
    target.show_live_calls = source.show_live_calls
    target.show_products = source.show_products
    target.show_downloads = source.show_downloads

    for link in source.links:
        target.links.append(HubLink(
            icon_type=link.icon_type, label=link.label, sublabel=link.sublabel,
            url=link.url, sort_order=link.sort_order,
        ))
    for call in source.live_calls:
        target.live_calls.append(HubLiveCall(
            tag=call.tag, title=call.title, body=call.body, sort_order=call.sort_order,
        ))
    for prod in source.products:
        target.products.append(HubProduct(
            label=prod.label, title=prod.title, description=prod.description,
            cta_text=prod.cta_text, url=prod.url, image_url="",  # eigenes Asset
            highlight=prod.highlight, sort_order=prod.sort_order,
        ))
    # downloads bewusst nicht kopiert

    await db.flush()
    await db.refresh(target, attribute_names=["links", "live_calls", "products", "downloads"])
    return _hub_to_payload(target)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_hub_copy.py -v`
Expected: PASS — alle 4 Tests grün.

- [ ] **Step 6: Run the full backend suite (no regressions)**

Run: `python -m pytest -q`
Expected: PASS — alle bestehenden Tests weiterhin grün.

- [ ] **Step 7: Commit**

```bash
git add app/api/admin_hub.py tests/test_hub_copy.py
git commit -m "feat(hub): Hub eines bestehenden Kurses als Vorlage übernehmen (Endpoint)"
```

---

### Task 2: Frontend — API-Methode + Dropdown im "Neuer Kurs"-Formular

**Files:**
- Modify: `frontend/src/lib/api.ts:132` (neue Methode `copyHubFrom` nach `deleteCourse`)
- Modify: `frontend/src/pages/admin/AdminCourses.tsx` (State + Dropdown + Aufruf in `handleCreate`)

- [ ] **Step 1: Add the API method**

In `frontend/src/lib/api.ts`, direkt nach der `deleteCourse`-Methode (Z. 132-133) einfügen:

```typescript
  copyHubFrom: (courseId: string, sourceCourseId: string) =>
    request<unknown>(`/admin/courses/${courseId}/hub/copy-from/${sourceCourseId}`, {
      method: 'POST',
    }),
```

- [ ] **Step 2: Add source-course state**

In `frontend/src/pages/admin/AdminCourses.tsx`, nach Z. 10 (`const [newDesc, setNewDesc] = useState('');`) einfügen:

```typescript
  const [hubSourceId, setHubSourceId] = useState('');
```

- [ ] **Step 3: Use the source in handleCreate**

In `frontend/src/pages/admin/AdminCourses.tsx` die `handleCreate`-Funktion (Z. 18-26) ersetzen durch:

```typescript
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    const { id } = await api.createCourse({ title: newTitle, description: newDesc || undefined });
    if (hubSourceId) {
      await api.copyHubFrom(id, hubSourceId);
    }
    setNewTitle('');
    setNewDesc('');
    setHubSourceId('');
    setShowCreate(false);
    load();
  };
```

- [ ] **Step 4: Add the dropdown to the create form**

In `frontend/src/pages/admin/AdminCourses.tsx` im Create-Formular, direkt **nach** dem Beschreibungs-`<div>` (das `</div>` auf Z. 76) und **vor** dem Button-`<div className="flex gap-3">` (Z. 77) einfügen:

```tsx
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Hub übernehmen von (optional)
            </label>
            <select
              value={hubSourceId}
              onChange={(e) => setHubSourceId(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
            >
              <option value="">Leer starten</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>{c.title}</option>
              ))}
            </select>
            <p className="text-xs text-gray-400 mt-1">
              Übernimmt Hero-Texte, Kontakt, Links, Live-Calls und Produkt-Texte.
              Bilder &amp; PDF-Downloads bitte im neuen Hub neu hochladen.
            </p>
          </div>
```

- [ ] **Step 5: Type-check the frontend**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS — keine Typfehler. (Wichtig: `createCourse` liefert `{ id: string }`, daher ist `const { id } = await ...` typkorrekt.)

- [ ] **Step 6: Build the frontend (catches anything tsc misses)**

Run: `cd frontend && npm run build`
Expected: Build erfolgreich.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/pages/admin/AdminCourses.tsx
git commit -m "feat(hub): Dropdown 'Hub übernehmen von' im Neuer-Kurs-Formular"
```

---

### Task 3: Manuelle Verifikation (lokal)

**Files:** keine (nur Beobachtung)

- [ ] **Step 1: App lokal starten** (Backend + Frontend nach üblichem Projekt-Setup) und als Admin einloggen.

- [ ] **Step 2: Neuen Kurs anlegen mit Hub-Vorlage**

Im Admin → "Kurse verwalten" → "+ Neuer Kurs". Titel z.B. "4-Wochen Glukose Balance Kurs", im Dropdown "Hub übernehmen von" einen bestehenden Kurs (z.B. "Glukose Balance Gruppe April 2026") wählen. Erstellen.

Expected: Kurs erscheint in der Liste, kein Fehler.

- [ ] **Step 3: Hub des neuen Kurses prüfen**

Neuen Kurs → Hub-Editor öffnen.

Expected:
- Hero-Texte, Kontakt-Rolle/-WhatsApp, Links, Live-Calls, Produkt-Texte sind aus der Vorlage übernommen.
- Produktbilder, Kontaktfoto und PDF-Downloads sind **leer** (müssen neu hochgeladen werden).

- [ ] **Step 4: Quell-Hub unverändert prüfen**

Den Quellkurs ("April 2026") Hub-Editor öffnen.

Expected: Quell-Hub ist vollständig unverändert (inkl. Bildern/PDFs) — die Übernahme hat nichts am Original angefasst.

---

## Self-Review

**Spec coverage:**
- "Hub als Grundlage übernehmen" → Task 1 (Endpoint) + Task 2 (UI im Create-Flow). ✓
- "nicht alles manuell neu aufsetzen" → Hero/Kontakt/Links/Live-Calls/Produkte werden kopiert. ✓
- Live-Betrieb / keine Breaking Changes (Memory) → rein additiv: neuer Endpoint, neue UI-Felder, keine Migration, keine geänderten Signaturen. ✓
- Schutz vor stillen Fehlern (geteilte Bunny-Assets, Datenverlust) → eigene Assets nicht kopiert, 409 bei nicht-leerem Ziel-Hub. ✓

**Placeholder scan:** Kein TBD/TODO; alle Code-Schritte vollständig. ✓

**Type consistency:** Endpoint-Pfad `/{course_id}/hub/copy-from/{source_course_id}` identisch in Test (Task 1) und `api.copyHubFrom` (Task 2). `createCourse` Rückgabe `{ id: string }` passt zu `const { id } = ...`. Helper-Namen `_load_hub_readonly`, `_load_or_create_hub`, `_require_course`, `_hub_to_payload` konsistent verwendet. ✓
