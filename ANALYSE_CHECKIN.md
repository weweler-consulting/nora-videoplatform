# ANALYSE: Check-In-Formulare (4-Wochen Glukose Balance Code)

> Lebende Referenz für das Check-In-Feature. Phase 0 (Analyse + Plan). Kein Code außer dieser Datei.
> Stand: 2026-06-04.

## 1. Repos & Stack

| Repo | Pfad | Stack |
|------|------|-------|
| video-platform | `/Users/justus/Developer/nora-videoplatform` | Python **FastAPI** (`app/`) + **React/Vite** (`frontend/`), SQLAlchemy 2.0 async, **SQLite dev / Postgres prod** |
| nora-crm | `/Users/justus/Developer/nora-crm` | **Next.js + Prisma** (Postgres) |

## 2. Datenmodell video-platform (real)

Hierarchie: **Kurs → Modul → Section → Lektion** (eine Ebene mehr als im Auftrag angenommen).
Quelle: `app/models/course.py`.

- `Course(id, title, description, …, sort_order, hub_enabled)` → `modules` (order_by sort_order)
- `Module(id, course_id FK CASCADE, title, …, unlock_after_days, sort_order)` → `sections`
- `Section(id, module_id FK CASCADE, title, sort_order)` → `lessons`
- `Lesson(id, section_id FK CASCADE, title, description, video_url, duration_minutes, sort_order)`
  - **Kein `type`/`kind`-Discriminator.** Inhalt = `video_url` (+ optional Markdown-`description`).
- `LessonProgress(user_id, lesson_id, completed, completed_at)` — Unique(user_id, lesson_id).
- `User(id, email UNIQUE, name, is_admin, is_active, …)` — Rolle via `is_admin`.

**Wie Nora es real nutzt:** Jede Wocheneinheit = 1 Modul mit genau **1 Lektion** (siehe „Live Call 10.06.2026 · 1 Lektion").

### Reihenfolge / „Drag-and-drop"
- **Kein DnD-Lib** (kein dnd-kit / react-beautiful-dnd installiert).
- **Lektionen:** Hoch/Runter-Pfeile in `AdminModuleDetail.tsx` (`handleMove`), schreibt einzelne `PUT /api/v1/lessons/{id}` mit `sort_order`.
- **Module:** **keine** Reorder-UI auf `AdminCourseDetail.tsx`. `sort_order` wird nur beim Anlegen gesetzt.
- Order = fortlaufende 0-basierte Integers, kein Bulk-Endpoint.

### Migrationen
- **Kein Alembic.** `Base.metadata.create_all` legt neue Tabellen beim Start an (`app/main.py:160`).
- Additive Spalten via `_build_migration_statements()` (`app/main.py:45`), idempotent (`ALTER TABLE … ADD COLUMN …`, „already exists" wird ignoriert).
- → Neue Tabellen = automatisch. Neue Spalte auf `lessons` = ein additives ALTER. Live-sicher.

## 3. Admin-Editor

- `frontend/src/pages/admin/AdminCourseDetail.tsx`: Kurs-Header + Modul-Liste. „+ Neues Modul" (`showCreate`) → `api.createModule` (`POST /modules/`) → danach `api.createSection` (Default „Lektionen"). Löschen via `api.deleteModule`.
- `frontend/src/pages/admin/AdminModuleDetail.tsx`: Lektionen anlegen/bearbeiten/löschen (`LessonForm`), Video-Upload via Bunny (tus), Hoch/Runter-Reorder.
- API-Client: `frontend/src/lib/api.ts` (`Authorization: Bearer <jwt>` aus localStorage).
- Backend-Guards: `require_admin` (`app/core/auth.py`) auf allen Schreib-Endpoints.

## 4. Player (Klientin)

- `frontend/src/pages/LessonView.tsx`: Video im Frame
  `<div className="aspect-video bg-black rounded-2xl …">` innerhalb `max-w-4xl`. **Das ist der Ziel-Rahmen für das Check-In-Formular** (16:9, max 896px).
- „Weiter"-Button ruft `api.completeLesson(id)` → `POST /api/v1/progress/{lesson_id}/complete`.
- Kurs-Navigation: `CourseView.tsx` / `course/CourseLessons.tsx` (Modul→Section→Lektion-Baum, Completion-Badges).
- Zugriff: `GET /courses/{id}` prüft Enrollment; Admin sieht alles entsperrt, Klientin sieht Drip-Restriktionen.

## 5. Auth / Rollen
- JWT (HS256), `sub` = user_id, in localStorage. `get_current_user` / `require_admin` Dependencies.
- Frontend: `ProtectedRoute` + `Layout.tsx` prüft `user.is_admin` für `/admin/*`.

## 6. Verbindung video-platform ↔ nora-crm (real)

- **Richtung heute: CRM → Plattform.** CRM hält `COURSE_PLATFORM_URL` + `COURSE_PLATFORM_SERVICE_TOKEN` (`nora-crm/src/lib/coursePlatform.ts`), ruft Plattform-Endpoints mit Header `X-Service-Token`.
  - Plattform-Seite: `app/api/integrations.py`, `app/models/service_token.py`, Guard `require_admin_or_service` (`app/core/auth.py`).
  - Genutzt: `POST /users/invite` (Einladung+Enrollment), `GET /users/lookup?email=` (Status).
- **Plattform pusht NICHTS ans CRM.** Outbound-Richtung muss neu gebaut werden.
- **Identitäts-Mapping: nur E-Mail** (case-insensitive). Kein `crm_contact_id` auf User, kein `videoPlatformUserId` auf Contact.
  - Bekanntes Risiko (CRM-Backlog R6): E-Mail-Änderung im CRM desyncht Lookup.
- **Async-Pattern vorhanden:** `app/core/drip_notifier.py` = In-Process `asyncio`-Loop (stündlich), Exceptions geloggt, Dedup via Tabelle. **Keine** Outbox/Queue/Retry-Infra bisher → für Check-In-Sync nachbauen.

## 7. CRM-Datenmodell (Contact)

`nora-crm/prisma/schema.prisma`:
- `Contact(id, firstName, lastName, email UNIQUE, …)` + Relationen.
- **Timeline = `FunnelEvent(contactId, type, timestamp, description, metadata Json?)`** — `metadata` wird bereits für strukturierte Formulardaten genutzt (Bewerbung-Webhook).
- `CourseInvitation(contactId, courseId, …)` verknüpft Kontakt↔Kurs.
- Inbound-Webhooks: `freebie`, `bewerbung`, `stripe`. Auth: `X-Webhook-Secret` + `timingSafeEqual` (Pattern A) bzw. `Bearer CRON_SECRET` (Pattern B). Matching: `findFirst({ where: { email, deletedAt: null } })`.

## 8. Konsequenzen für das Design (wichtig)

1. **Render + Fortschritt hängen an der LEKTION**, nicht am Modul. Ein Check-in muss als Lektion existieren, um den Player-Frame und `LessonProgress` wiederzuverwenden.
2. **Die sichtbare „Modulliste"** auf der Kursseite ist, was Nora umsortieren will — aber dafür gibt es **heute keine Reorder-UI** (auch nicht für Video-Module).
3. **„Drag-and-drop" existiert nicht**; bestehender Reorder = Hoch/Runter-Pfeile (Lektionen).
4. **CRM-Sync = neue Outbound-Richtung** (Outbox + Loop + neuer CRM-Webhook), Mapping über E-Mail.

## 9. Empfohlenes Zielmodell (Vorschlag, in Phase 0 zu bestätigen)

**Andockpunkt: Lektions-Ebene.** Ein Check-in = ein Modul (Container) mit genau **einer Lektion vom Typ `checkin`** — exakt das Muster, das Nora für Video-Einheiten schon nutzt. So:
- erscheint der Check-in als **Eintrag in der Modulliste** (mit Badge),
- rendert im **Lektions-Player-Frame**,
- zählt über **`LessonProgress`** in den Fortschritt,
- nutzt für die Reihenfolge dieselbe Logik (siehe offene Entscheidung zu Modul-Reorder).

### Neue Tabellen (video-platform)
- `checkin_template(id, typ ['start'|'laufend'|'ende'], name, created_at)`
- `checkin_step(id, template_id FK, key, typ, frage, hilfetext?, pflichtfeld, optionen JSON?, skala_min, skala_max, skala_labels JSON?, sort_order)`
- `checkin_response(id, user_id, course_id, lesson_id, template_typ, week_index?, answers JSON, status, submitted_at, synced_to_crm bool, created_at)`
- `crm_outbox(id, event_type, user_id, course_id, payload JSON, created_at, synced_at?, retry_count, last_error?)`

### Neue Spalten
- `lessons.type VARCHAR DEFAULT 'video'` (`'video'|'checkin'`)
- `lessons.checkin_template_id` (nullable FK)
- `lessons.checkin_overrides JSON?` (instanz-eigene Frage-Overrides, z. B. wechselnde `umsetzung`-Frage)

### Templates (Inhalt) → in Phase 1 als Seed, im Admin editierbar
- `start`: 11 Schritte (intro, langtext `warum`, mehrfachauswahl `hauptziel`, langtext `ziel_konkret`, skala `energie`, einfachauswahl `nachmittagstief`/`heisshunger`/`fruehstueck_status`, langtext `herausforderung`/`support`, bestaetigung).
- `laufend`: Kern (skala `wohlbefinden`/`energie`, einfachauswahl `heisshunger`) + editierbare `umsetzung` + `kurztext` `win`/`huerde` + `langtext` `frage` (optional) + bestaetigung.
- Stabile Keys über alle Wochen → Vergleichbarkeit. `ende` nur Schema, nicht ausgebaut.

### CRM-Sync (Outbound, neu)
- Submit → `checkin_response` speichern (treibt Player) → `crm_outbox`-Zeile.
- Background-Loop (Muster `drip_notifier`) → `POST` an neuen CRM-Webhook → match by email → speichern (siehe offene Entscheidung: `FunnelEvent.metadata` vs. dediziertes `CheckInResponse`-Modell).
- Nicht-blockierend, Retry über `crm_outbox.retry_count`.

## 10. Entscheidungen (bestätigt 2026-06-04)
1. **Andockpunkt:** ✅ **Lektions-Typ** — Check-in = 1-Lektion-Modul, Lektion `type='checkin'`. Nutzt Player-Frame + `LessonProgress` + Lektions-Reorder.
2. **Reorder:** ✅ **Hoch/Runter-Pfeile für Module** ergänzen (gleiche Mechanik wie Lektionen). Kein dnd-kit.
3. **CRM-Speicherung:** ✅ **Dediziertes `CheckInResponse`-Prisma-Modell** im CRM (stabile Keys + week_index, trend-fähig).
4. **CRM-Transport:** ✅ **Neuer Webhook `POST /api/webhooks/course-checkin`** + Shared Secret `COURSE_CHECKIN_WEBHOOK_SECRET`, Matching by email (R6-Risiko akzeptiert).
