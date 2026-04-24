# Mitgliederbereich — Design-Spec

**Datum:** 2026-04-24
**Autor:** Justus + Claude (Brainstorming-Session)
**Ziel-Go-Live:** 2026-04-30 (7 Tage)
**Hartes Deadline-Motiv:** LearningSuite-Vertrag endet 2026-05-16 — ohne Mitgliederbereich auf `kose.noraweweler.de` kann Nora LS nicht kündigen.

---

## 1. Ziel

Ein Mitgliederbereich pro Kurs (auf der bestehenden Videoplattform `kose.noraweweler.de`), der die in LearningSuite genutzten Hub-Features ersetzt: Willkommens-Hero, wichtige Links (Kurs, Live Call, WhatsApp, Kalender), Ansprechpartnerin, Live-Call-News, Produkt-Empfehlungen und PDF-Downloads. Verwaltet über das bestehende Admin-Panel mit einem klassischen Formular. Eingebettet als Default-Tab auf der Kurs-Detailseite, sodass eingeschriebene Kunden beim Öffnen eines Kurses zuerst den Hub sehen.

Nach dem Deployment kann Nora den LS-Vertrag per 2026-05-16 kündigen.

## 2. Grundsatzentscheidungen (finalisiert)

| Frage | Entscheidung |
|-------|--------------|
| Scope-Einheit | **Pro Kurs** (1:1 `Course`↔`CourseHub`). Keine Kohorten-Modellierung. |
| Edit-Modell | **Klassisches Admin-Formular** unter `/admin/courses/{id}/hub`. Kein Inline-Edit. |
| Sektionen | **Alle 6** (Hero, Links, Ansprechpartnerin, Live Calls, Produkte, Downloads). |
| Produktbilder | **Upload via Bunny-Storage.** |
| PDFs | Lokal unter `/app/data/hub_downloads/{course_id}/{uuid}.pdf`. |
| Navigation | **Tabs auf `/courses/{id}`**: `?tab=hub` (Default) und `?tab=lessons`. |
| Styling-Scope | **Global** — Berry-Tokens + Almarai-Font für die gesamte App. |
| Serif-Akzent-Font | **Google-Fonts-Fallback** (`Cormorant Garamond` oder `Playfair Display`). Kein Romie wegen unklarer Web-Lizenz. |
| Deployment | **Direkt auf Prod** via `git push`. Kein Staging. Sorgfältige lokale Prüfung vor Push. |

## 3. Architektur-Überblick

### Backend (`app/`)

Neue Datei-Struktur:
```
app/
  models/hub.py              (neu — CourseHub + 4 Sub-Tabellen)
  schemas/hub.py             (neu — Pydantic-Schemas, inkl. kombiniertes HubPayload)
  api/hub.py                 (neu — Public-GET, Download-Endpoint)
  api/admin_hub.py           (neu — Admin PUT, Uploads)
  integrations/bunny.py      (erweitert — upload_bunny_image())
  main.py                    (erweitert — Migration-Calls, Router-Registrierung)
  models/course.py           (erweitert — hub-Relationship)
```

### Frontend (`frontend/src/`)

Neue/geänderte Dateien:
```
src/
  index.css                  (erweitert — Design-Tokens global)
  App.tsx                    (erweitert — neue Route /admin/courses/:id/hub)
  lib/api/hub.ts             (neu — API-Client)
  pages/CourseDetail.tsx     (refactored — Tab-Bar einführen)
  pages/course/
    CourseLessons.tsx        (neu — ausgelagerter bestehender Modul-Code)
    hub/
      HubView.tsx            (neu — Container)
      HubHero.tsx            (neu)
      HubLinks.tsx           (neu)
      HubContact.tsx         (neu)
      HubLiveCalls.tsx       (neu)
      HubProducts.tsx        (neu)
      HubDownloads.tsx       (neu)
  pages/admin/
    AdminCourseDetail.tsx    (erweitert — "Mitgliederbereich bearbeiten"-Button)
    AdminCourseHub.tsx       (neu — Admin-Formular)
public/fonts/                (entfällt — Google Fonts statt lokaler Romie)
```

## 4. Datenmodell

### `CourseHub` (1:1 zu `Course`)

```python
class CourseHub(Base):
    __tablename__ = "course_hubs"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"),
                       unique=True, nullable=False)

    # Hero
    hero_variant = Column(String, default="berry")         # "berry" | "dark" | "pale"
    hero_eyebrow = Column(String, default="")
    hero_title_html = Column(String, default="")          # bleach-sanitized, <em>+<br> erlaubt
    hero_body = Column(Text, default="")

    # Kontakt
    contact_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"),
                             nullable=True)
    contact_name_override = Column(String, default="")     # leer → user.name
    contact_role = Column(String, default="Kursleitung & Ernährungsberaterin")
    contact_email_override = Column(String, default="")
    contact_whatsapp_url = Column(String, default="")
    contact_photo_url = Column(String, default="")          # Bunny-CDN-URL

    # Sichtbarkeits-Flags
    show_contact = Column(Boolean, default=True)
    show_live_calls = Column(Boolean, default=True)
    show_products = Column(Boolean, default=True)
    show_downloads = Column(Boolean, default=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    course = relationship("Course", back_populates="hub")
    links = relationship("HubLink", cascade="all, delete-orphan",
                         order_by="HubLink.sort_order")
    live_calls = relationship("HubLiveCall", cascade="all, delete-orphan",
                              order_by="HubLiveCall.sort_order")
    products = relationship("HubProduct", cascade="all, delete-orphan",
                            order_by="HubProduct.sort_order")
    downloads = relationship("HubDownload", cascade="all, delete-orphan",
                             order_by="HubDownload.sort_order")
```

### Sub-Tabellen

```python
class HubLink(Base):
    __tablename__ = "hub_links"
    id = Column(Integer, primary_key=True)
    hub_id = Column(Integer, ForeignKey("course_hubs.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    icon_type = Column(String, nullable=False)     # "book" | "video" | "wa" | "cal" | "link"
    label = Column(String, nullable=False)
    sublabel = Column(String, default="")
    url = Column(String, default="")
    sort_order = Column(Integer, default=0)

class HubLiveCall(Base):
    __tablename__ = "hub_live_calls"
    id = Column(Integer, primary_key=True)
    hub_id = Column(Integer, ForeignKey("course_hubs.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    tag = Column(String, default="")
    title = Column(String, nullable=False)
    body = Column(Text, default="")
    sort_order = Column(Integer, default=0)

class HubProduct(Base):
    __tablename__ = "hub_products"
    id = Column(Integer, primary_key=True)
    hub_id = Column(Integer, ForeignKey("course_hubs.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    label = Column(String, default="")              # Kategorie-Tag
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    cta_text = Column(String, default="Zum Shop")
    url = Column(String, default="")
    image_url = Column(String, default="")           # Bunny-CDN-URL
    highlight = Column(Boolean, default=False)       # berry-gradient statt weiß
    sort_order = Column(Integer, default=0)

class HubDownload(Base):
    __tablename__ = "hub_downloads"
    id = Column(Integer, primary_key=True)
    hub_id = Column(Integer, ForeignKey("course_hubs.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    file_path = Column(String, nullable=False)       # /app/data/hub_downloads/{course_id}/{uuid}.pdf
    file_name = Column(String, nullable=False)       # Original-Name für Content-Disposition
    file_size_kb = Column(Integer, default=0)
    sort_order = Column(Integer, default=0)
```

### Relationship auf `Course`

In `app/models/course.py` ergänzen:
```python
hub = relationship("CourseHub", uselist=False,
                   cascade="all, delete-orphan", back_populates="course")
```

### Migration + Backfill

In `app/main.py` beim Boot (existierendes „CREATE TABLE IF NOT EXISTS"-Pattern):
1. Alle 5 Tabellen anlegen (inkl. Indizes auf `hub_id`).
2. Backfill: Für jeden `Course` ohne `CourseHub`-Zeile eine leere Zeile mit Defaults anlegen (idempotent dank `UNIQUE(course_id)`).
3. `Path("/app/data/hub_downloads").mkdir(parents=True, exist_ok=True)`.

## 5. API

### Public (eingeschriebene User)

**`GET /api/v1/courses/{course_id}/hub`**
- Auth: Bearer-Token, User muss aktives `Enrollment(user_id, course_id)` haben oder Admin sein. Sonst 403.
- Response: Das komplette Hub-Payload (`HubPayload`-Schema, siehe unten).

**`GET /api/v1/courses/{course_id}/hub/downloads/{download_id}`**
- Auth wie oben.
- Response: FileStream mit `Content-Disposition: attachment; filename="{file_name}"`.
- Validiert, dass `download.hub.course_id == course_id`.

### Admin

**`GET /api/v1/admin/courses/{course_id}/hub`**
- Auth: `current_user.is_admin`.
- Response: `HubPayload`.

**`PUT /api/v1/admin/courses/{course_id}/hub`**
- Body: Komplettes `HubPayload`.
- Semantik: Replace-All für die 4 List-Typen (Links/Calls/Products/Downloads) in einer Transaktion.
- Dead-File-Cleanup: vor dem Commit alte `file_path`/`image_url`-Werte, die im neuen Payload nicht mehr vorkommen, von Disk/Bunny löschen.
- Validierung (siehe Abschnitt 6).

**`POST /api/v1/admin/courses/{course_id}/hub/image`**
- Multipart-Upload (Feld `file`, plus `kind` = `product` | `contact_photo`).
- Body: max 5 MB, `image/jpeg` | `image/png` | `image/webp`.
- Response: `{ "url": "https://cdn.bunny.net/..." }`.
- Frontend nimmt die URL in den Form-State.

**`POST /api/v1/admin/courses/{course_id}/hub/pdf`**
- Multipart-Upload, Feld `file`, max 20 MB, `application/pdf`.
- Speichert unter `/app/data/hub_downloads/{course_id}/{uuid}.pdf`.
- Response: `{ "file_path": "...", "file_name": "Einkaufsliste.pdf", "file_size_kb": 145 }`.

### Pydantic-Schemas

```python
# app/schemas/hub.py
class HubLinkSchema(BaseModel):
    id: int | None = None
    icon_type: Literal["book", "video", "wa", "cal", "link"]
    label: str
    sublabel: str = ""
    url: str = ""
    sort_order: int = 0

class HubLiveCallSchema(BaseModel):
    id: int | None = None
    tag: str = ""
    title: str
    body: str = ""
    sort_order: int = 0

class HubProductSchema(BaseModel):
    id: int | None = None
    label: str = ""
    title: str
    description: str = ""
    cta_text: str = "Zum Shop"
    url: str = ""
    image_url: str = ""
    highlight: bool = False
    sort_order: int = 0

class HubDownloadSchema(BaseModel):
    id: int | None = None
    title: str
    description: str = ""
    file_path: str
    file_name: str
    file_size_kb: int = 0
    sort_order: int = 0

class HubPayload(BaseModel):
    hero_variant: Literal["berry", "dark", "pale"] = "berry"
    hero_eyebrow: str = ""
    hero_title_html: str = ""
    hero_body: str = ""
    contact_user_id: int | None = None
    contact_name_override: str = ""
    contact_role: str = "Kursleitung & Ernährungsberaterin"
    contact_email_override: str = ""
    contact_whatsapp_url: str = ""
    contact_photo_url: str = ""
    show_contact: bool = True
    show_live_calls: bool = True
    show_products: bool = True
    show_downloads: bool = True
    links: list[HubLinkSchema] = []
    live_calls: list[HubLiveCallSchema] = []
    products: list[HubProductSchema] = []
    downloads: list[HubDownloadSchema] = []
```

## 6. Validation-Regeln

- `hero_title_html` wird mit `bleach` sanitized, Allowlist: `<em>`, `<br>`. Alles andere gestrippt.
- URLs (`HubLink.url`, `HubProduct.url`, `contact_whatsapp_url`): wenn nicht leer, muss mit `http://` oder `https://` beginnen. Sonst 422.
- `HubLink.icon_type`: muss im Enum sein (schon durch `Literal` erzwungen).
- `HubDownload.file_path`: darf nur Pfade unter `/app/data/hub_downloads/{course_id}/` akzeptieren — Path-Traversal-Schutz im PUT-Endpoint.
- `contact_email_override`: wenn nicht leer, muss Email-Format haben (`EmailStr`).
- Upload-Limits (serverseitig durchgesetzt):
  - Bilder: max 5 MB, MIME `image/jpeg|png|webp`
  - PDFs: max 20 MB, MIME `application/pdf`

## 7. Admin-Flow (UI-Struktur)

Route: `/admin/courses/{course_id}/hub`

Sektionen von oben nach unten, jede kollabierbar:

1. **Hero** — Farbvariante (Radio), Eyebrow (Input), Titel (Textarea mit Hint zu `<em>`/`<br>`), Fließtext (Textarea).
2. **Ansprechpartner** — Toggle „anzeigen", User-Dropdown (alle Admins), Name-Override, Rolle, E-Mail-Override, WhatsApp-URL, Foto-Upload-Feld mit Vorschau.
3. **Wichtige Links** — Liste mit Items (Add-Button unten, Remove-X + Up/Down pro Item). Pro Item: Icon-Type (Radio), Label, Sublabel, URL.
4. **Live Calls** — Toggle, Liste mit Items (Tag, Titel, Body).
5. **Produkte** — Toggle, Liste mit Items (Label, Titel, Description, CTA-Text, URL, Bild-Upload, Highlight-Toggle).
6. **Downloads** — Toggle, Liste mit Items (Titel, Description, PDF-Upload mit Vorschau des Dateinamens+Größe).

Button-Leiste unten: `[Verwerfen]` (zurück ohne Speichern), `[Speichern]` (PUT-Request).

Feedback:
- Nach erfolgreichem Speichern: Toast-Notification (via existierendem Pattern oder simple UI-Message) + State-Update.
- Bei Fehler: Fehlermeldung oberhalb der Button-Leiste, Form bleibt ausgefüllt.

Reorder: Up/Down-Pfeile pro Item (kein Drag&Drop).

Zweiter Einstiegs-Link: In `AdminCourseDetail.tsx` oben rechts Button „Mitgliederbereich bearbeiten" → navigiert zu obiger Route.

## 8. Public-Flow (UI-Struktur)

Route: `/courses/{course_id}` mit `?tab=hub` (Default) oder `?tab=lessons`.

Tab-Bar über dem bisherigen Kurs-Header:
```
[ Mitgliederbereich ]  [ Inhalte ]
```
- Aktiver Tab unterstrichen mit Berry-Farbe.
- `useSearchParams` für Tab-State. Browser-Zurück funktioniert.
- Deep-Link auf `/courses/{id}` ohne Param → Default `tab=hub`.

Hub-Rendering (`HubView.tsx`):
1. Breadcrumb
2. H1 „Dein Mitgliederbereich"
3. `HubHero` (je nach `hero_variant` unterschiedlicher Gradient)
4. `HubLinks` (Tile-Grid, 4 Spalten Desktop / 2 Mobile)
5. `HubContact` (bedingt, 1 Karte max 440px)
6. `HubLiveCalls` (bedingt, Flex-Wrap mit Text-Kacheln)
7. `HubProducts` (bedingt, vertikale Liste mit Bild links)
8. `HubDownloads` (bedingt, vertikale Liste mit PDF-Icon + Download-Button)

Leerzustände:
- **Komplett leerer Hub**: Platzhalter „Dieser Mitgliederbereich wird gerade eingerichtet — schau später nochmal vorbei."
- **Einzelne Sektion leer** (auch bei `show_*=true`): Sektion wird ausgeblendet.
- **Link-Tile ohne URL**: grau/disabled mit Tooltip „Link wird vorbereitet".

Interaktion:
- Alle externen Links: `target="_blank" rel="noopener"`.
- Download-Buttons: GET an `/courses/{id}/hub/downloads/{id}` mit Bearer-Auth (gleiches Pattern wie Accept-Invite-Download in der bestehenden App).

Responsives Verhalten: Breakpoint 768px; Mobile: alles einspaltig, Hero-Foto-Karte unter Text.

## 9. Styling

### Design-Tokens (global, in `frontend/src/index.css`)

Tokens aus `colors_and_type.css` übernehmen:
- Farbpalette: `--berry`, `--berry-dark`, `--berry-light`, `--berry-pale`, `--cream`, `--coco`, `--soy`.
- Semantic-Aliases (`--color-text-primary` etc.).
- Fonts: `--font-sans: 'Almarai', system-ui, sans-serif;`, `--font-serif: 'Cormorant Garamond', Georgia, serif;` (Google-Fonts-Import im `index.html` bzw. `index.css`).
- Radii, Shadows, Gap-System wie im CSS.

### Globale Auswirkungen

Die komplette App (inkl. `/admin`, `/login`, `/courses`) bekommt den Nora-Look:
- Body-Font = Almarai
- Primär-Akzent = Berry
- Hintergrund = Cream

Das ist beabsichtigt. Die bestehende App ist visuell generisch; der LS-Exit ist der natürliche Moment für Brand-Konsistenz.

### Fonts

- **Almarai** (Sans): Google Fonts — `family=Almarai:wght@300;400;700;800`.
- **Cormorant Garamond** (Serif-Akzent) oder **Playfair Display**: Google Fonts. Finale Wahl beim Styling-Pass anhand Optik — Design-Tokens vorerst auf `Cormorant Garamond` setzen, bei Nicht-Gefallen auf Playfair wechseln.
- Romie wird **nicht** eingebunden (unklare Web-Lizenz).

## 10. Storage / Integration

### Bunny (Bilder)

Erweitere `app/integrations/bunny.py`:
```python
def upload_bunny_image(file_bytes: bytes, course_id: int, kind: str,
                      filename: str) -> str:
    """Lädt Bild in Bunny Storage hoch, returniert Pull-Zone-URL.
    Pfad-Schema: /hub/{course_id}/{kind}/{uuid}.{ext}
    """
```
Nutzt dieselbe Storage-Zone wie Videos. Falls die Zone Bilder ablehnt (zu klären während Tag 2), wird eine zweite Zone konfiguriert — Admin-Aufwand ~30 Minuten im Bunny-Dashboard.

Cleanup: `delete_bunny_file(url: str)` — Delete-Request gegen Storage-API.

### Lokale PDFs

Pfad: `/app/data/hub_downloads/{course_id}/{uuid}.pdf`.
- Originalname in DB (`HubDownload.file_name`), auf Disk UUID — verhindert Pfad-Kollisionen und Enumeration.
- Download-Endpoint streamt die Datei mit korrektem `Content-Disposition`.
- Beim Löschen/Ersetzen eines `HubDownload` wird die alte Datei von Disk entfernt.

### Dead-File-Cleanup im PUT-Hub

Vor dem Commit:
1. Alte Downloads aus DB laden → `old_paths = {d.file_path for d in old}`.
2. Neues Payload parsen → `new_paths = {d.file_path for d in payload.downloads}`.
3. Zu löschen: `old_paths - new_paths` → von Disk entfernen.
4. Analog für `image_url` bei Products und `contact_photo_url` — via Bunny-Delete.

## 11. Testing

### Pytest-Minimal (neue Datei `tests/test_hub.py`)

Fokus auf kritische Pfade:
- `GET /courses/{id}/hub` ohne Enrollment → 403
- `GET /courses/{id}/hub` mit Enrollment → 200 + erwartetes Payload-Schema
- `PUT /admin/courses/{id}/hub` als non-Admin → 403
- `PUT /admin/courses/{id}/hub` als Admin: Links werden ersetzt, alte IDs verschwinden
- Dead-File-Cleanup: PDF wird von Disk entfernt, wenn es aus dem Payload raus ist
- HTML-Sanitizer: `<script>` in `hero_title_html` wird gestrippt
- Download-Endpoint: Content-Disposition enthält den Original-Dateinamen
- Download-Endpoint mit fremder Course-ID im Pfad → 404

Kein Frontend-Test (keine existierende Test-Infrastruktur, würde Projekt sprengen). Stattdessen manuelle Smoke-Checkliste vor Deploy.

### Smoke-Checkliste vor Go-Live

1. Admin legt je 2 Links, Calls, Produkte, Downloads an → speichern → reload zeigt alles korrekt.
2. PDF + Bild hochladen → erscheinen in Public-View.
3. Public-View als Enrolled-User: alle Sektionen sichtbar, Links öffnen neuen Tab.
4. Public-View als Nicht-Enrolled: 403.
5. Mobile-View (Chrome DevTools, iPhone-Preset): einspaltig, nichts bricht.
6. Tab-Wechsel setzt URL-Param; Deep-Link mit `?tab=lessons` öffnet Modul-View direkt.
7. Stripe-Test-Kauf: Redirect landet auf `/courses/{id}?tab=hub` (oder ohne Param → Default Hub).

### Content-Seed (manuell durch Nora)

- Keine LS-Import-Pipeline.
- Nora sammelt parallel zur Entwicklung: PDFs, Produktbilder (Original-Auflösung), Live-Call-Texte, WhatsApp-/Meet-Links pro Kurs.
- Eingabe per Admin-Panel, Aufwand ~20–30 min pro Kurs.

## 12. Timeline (7 Tage)

| Tag | Datum | Arbeit |
|-----|-------|--------|
| 1 | Fr 2026-04-25 | Backend: Models, Migration, Hub-API (GET/PUT ohne Upload). |
| 2 | Sa 2026-04-26 | Backend: Bunny-Bild-Upload, PDF-Upload, Download-Endpoint, Pytest. |
| 3 | So 2026-04-27 | Frontend: `AdminCourseHub.tsx` komplett (alle Sektionen, Add/Remove/Reorder). |
| 4 | Mo 2026-04-28 | Frontend: `HubView.tsx` + Sektions-Komponenten, Tab-Integration in `CourseDetail.tsx`. |
| 5 | Di 2026-04-29 | Globale Styles + Font-Integration, Responsive-Pass. Nora sammelt parallel Content. |
| 6 | Mi 2026-04-30 | Nora seedet Content in Prod. Claude fixt Live-Bugs und Micro-Copy. **Go-Live-Tag.** |
| 7 | Do 2026-05-01 | Puffer / LS-Kündigungsvorbereitung. |

**Deadline-Puffer bis LS-Ende 2026-05-16:** 16 Tage nach Go-Live. Sicherheitsnetz für Nacharbeit, kein Slack.

## 13. Risiken

1. **Bunny-Storage-Zone akzeptiert Bilder nicht** — Fallback: zweite Zone im Bunny-Dashboard konfigurieren, ~30 min. Kein Blocker.
2. **Stripe-Redirect bricht nach Tab-Umbau** — nach Deploy Test-Kauf durchführen, bei Fehler Query-Param entfernen und auf Route-Default setzen.
3. **Nora hat Content nicht rechtzeitig bereit** — Content-Sammel-Liste am Tag 1 raus geben; Parallel-Arbeit möglich.
4. **Direktes Prod-Deploy ohne Staging** — Mitigation: ausgiebige lokale Prüfung (Smoke-Checkliste), Deploy während Off-Peak, Rollback via `git revert + push` vorbereitet.

## 14. Out-of-Scope (bewusst nicht gebaut)

- Kohorten-Modell (siehe Entscheidungs-Tabelle oben).
- Inline-Edit-Modus wie im HTML-Prototyp.
- Mehrsprachigkeit.
- Benutzerdefinierte Icons für Links (nur 5 feste Typen).
- Drag&Drop-Reorder.
- Revisionshistorie / Versionierung des Hubs.
- LS-Auto-Import.
- Preview-Mode (Admin sieht Hub so, wie Kundin ihn sieht, ohne Impersonation).
- Feature-Flags — Hub ist für alle Kurse sofort aktiv.

## 15. Offene Detail-Entscheidungen (während Implementation zu klären)

- Finale Serif-Font-Wahl (Cormorant vs. Playfair) — am Tag 5 anhand Optik entscheiden.
- Bunny-Image-Storage-Zone (nutzt existierende oder separate).
- Genaues Layout der Admin-Formular-Sektionen (Details im Code, folgt etabliertem Pattern aus `AdminCourseDetail.tsx`).

---

*Implementation-Plan folgt via `writing-plans` nach Freigabe dieser Spec.*
