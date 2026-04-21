# CRM ↔ Kurse Integration (Option A: Service-Token API)

## Ziel
Aus `crm.noraweweler.de` heraus einen Contact per Klick zu einem Kurs auf `kurse.noraweweler.de` einladen. CRM zeigt alle verfügbaren Kurse, Nora wählt manuell pro Contact. Automatisierung nach Coaching-Typ kommt später, wenn Kurse systematisiert sind.

## Architektur
- Kurse-App exponiert Admin-API (`GET /courses/admin/all`, `POST /users/invite`) zusätzlich via `X-Service-Token`-Header
- CRM hält Service-Token in ENV, ruft server-to-server
- Jede CRM-initiierte Einladung wird lokal im CRM protokolliert (`CourseInvitation`)

## Block 1 — Kurse-Plattform (dieses Repo)

- [ ] `app/models/service_token.py`: Model `ServiceToken(id, name, token_hash, created_at, last_used_at)`, in `__init__.py` registrieren
- [ ] Migration in `main.py`
- [ ] `app/core/auth.py`: Helper `verify_service_token(raw_token)`, returnt ServiceToken oder None. Hash via sha256 (Token wird beim Create einmal im Klartext gezeigt, danach nur hash)
- [ ] `app/core/auth.py`: Neue Dependency `require_admin_or_service(request, credentials, db) -> User | ServiceToken`. Akzeptiert entweder Bearer-JWT (Admin) oder `X-Service-Token`-Header
- [ ] Betroffene Endpoints umstellen von `require_admin` auf `require_admin_or_service`:
  - `GET /courses/admin/all`
  - `POST /users/invite`
- [ ] Neue Admin-Endpoints `app/api/integrations.py`:
  - `GET /integrations/tokens` → Liste (ohne Klartext)
  - `POST /integrations/tokens {name}` → erzeugt, returnt `{id, name, token}` (einmalig)
  - `DELETE /integrations/tokens/{id}` → revoke
- [ ] Router in `main.py` einhängen
- [ ] Frontend: neue Seite `frontend/src/pages/admin/AdminIntegrations.tsx` — Token-Liste, Create-Dialog mit „einmalig anzeigen + kopieren", Revoke-Button
- [ ] Route in `App.tsx` + Sidebar-Link in `Layout.tsx` (nur für Admins sichtbar)
- [ ] API-Methoden in `frontend/src/lib/api.ts`

## Block 2 — CRM (Repo `nora-crm`)

- [ ] ENV-Vars: `COURSE_PLATFORM_URL`, `COURSE_PLATFORM_SERVICE_TOKEN`
- [ ] Prisma: neues Model `CourseInvitation { id, contactId, courseId, courseTitle, invitedAt, inviteUrl?, emailSent Bool }` + Migration
- [ ] `src/lib/coursePlatform.ts`: kleiner Client (`listCourses()`, `inviteContact(email, name, courseId)`)
- [ ] API-Route `POST /api/contacts/[id]/course-invite` — ruft Client, persistiert `CourseInvitation`, returnt Ergebnis
- [ ] API-Route `GET /api/course-platform/courses` — proxied die Kurs-Liste (zum Client-Fetch ohne Token-Leak)
- [ ] Contact-Detail-Page: neuer Block „Kurse" mit Dropdown der verfügbaren Kurse + „Einladen"-Button + Historie bisheriger Einladungen

## Scope-Klarheit (nicht jetzt)
- Rückrichtung (Progress-Sync Kurse → CRM)
- Auto-Invite bei Purchase mit bestimmtem Product-Type
- Cancellation/Revoke-Flow (Enrollment aus Kurs entfernen, wenn Coaching endet)
