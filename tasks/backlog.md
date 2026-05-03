# Backlog — Nora Videoplatform

Eine Liste. Hier weitermachen, wenn du Zeit hast. Erledigte Punkte abhaken, nicht löschen — sonst geht die Historie verloren. Neue Punkte unten anhängen.

**Historie / Hintergrund:**
- `tasks/deep-audit.md` — vollständiger Audit nach Go-Live
- `tasks/post-launch.md` — Security/Ops/Compliance-Themen (zum Teil hier konsolidiert)
- `tasks/todo.md` — alter Einladungsflow-Plan (fertig)
- `tasks/crm-integration.md` — CRM-Integration-Plan (fertig)

---

## 📍 Hier morgen weitermachen

**Plattform-Stand:** Live auf `kose.noraweweler.de`. Go-Live-Audit durch. CRM-Anbindung an `crm.noraweweler.de` live, inkl. Status-Sync. Mitgliederbereich-Feature (Hub pro Kurs) seit 2026-04-24 deployed. **2026-04-27 abends: erste zahlende Kundinnen eingeladen.** Nächster Brocken: **B2 Zertifikat** — sobald die erste Kohorte stabil läuft.

**Erstes Cohort-Monitoring (24–48h):**
- Resend-Dashboard: Bounces / Spam-Reports der Invite-Mails prüfen
- Nora kurz mit 1–2 Kundinnen rückkoppeln: Login + erste Lektion erfolgreich? Mitgliederbereich verständlich?
- Server-Logs grep'en: 5xx-Errors, fehlgeschlagene Bunny-Calls, Webhook-Probleme

**Warum B2 als Nächstes:** kleinster sichtbarer Kunden-Effekt pro Aufwand. 2–3 Tage bis deploy-bar. Treiber: Social-Proof (Kundinnen teilen PDF auf Instagram → kostenlose Werbung), plus Abschluss-Motivation (niemand will bei 80 % steckenbleiben).

**Konkrete erste Schritte für B2:**
1. **PDF-Rendering-Weg wählen:** WeasyPrint (Python, HTML+CSS → PDF) vs. Playwright-Headless (mehr Overhead aber pixel-perfekt). Empfehlung: WeasyPrint, passt zum FastAPI-Stack und pip-install reicht.
2. **Template-Entwurf:** einmaliges HTML+CSS-Layout mit Platzhaltern `{{ name }}`, `{{ course_title }}`, `{{ completed_at }}`. Nora braucht eine Unterschrift-Grafik (PNG) — vor Start von ihr anfordern.
3. **Trigger-Punkt:** im `app/api/progress.py`-`mark_complete`: nach Speichern prüfen, ob Kurs jetzt 100 % ist (ähnlich wie Dashboard es berechnet). Wenn ja: PDF generieren + per Resend versenden.
4. **Speicherung:** PDF in `/app/data/certificates/{user_id}/{course_id}.pdf` ablegen, später via Endpoint abrufbar (Accept-Invite-Flow hat schon den Download-Pattern mit Bearer-Auth).
5. **DB:** minimales Feld `Certificate(user_id, course_id, issued_at, file_path)` — damit Zertifikat nicht bei jedem Re-Upload neu erzeugt wird.

**Alternative falls B2 stockt:** B4 Inaktivitäts-Reminder (1–2 Tage), ist rein Backend (neuer `inactivity_loop` analog `drip_notifier_loop`), sofort sichtbare Email-Welle.

**Skip für jetzt:** B1 Resume-Play braucht Player-Integration in Bunny/YouTube/Vimeo — zu breit für einen sauberen Sprint.

---

---

## 🚀 PRIORITÄT — nächste 4 Wochen

Was aus PM-Sicht direkt Umsatz oder Retention bringt. Reihenfolge ist meine Empfehlung (siehe `deep-audit.md` für die Begründung).

- [ ] **B1 · Resume-Play (Video-Position merken)** — 3–5 Tage. Neues Feld `LessonProgress.last_position_seconds`, Auto-Seek beim Player-Load, Update alle 10s. Größter Retention-Hebel.
- [ ] **B2 · Abschluss-Zertifikat als PDF** — 2–3 Tage. Bei 100% Progress Auto-PDF (Name + Kurs + Datum + Unterschrift), Download + Mail. Social-Proof + Motivation.
- [ ] **B3 · Cross-Sell-Mail bei Kurs-Abschluss** — 1–2 Tage. Bei 100% Mail "Dein nächster Kurs: [X] — 15% Rabatt 48h" via Stripe-Coupon.
- [ ] **B4 · Inaktivitäts-Reminder (Win-Back)** — 1–2 Tage. Neuer Loop analog `drip_notifier`. User mit 0 Progress nach 14 Tagen → Erinnerungsmail. Nach 30 Tagen → Admin-Dashboard-Alert.
- [ ] **B5 · Private Notizen pro Lektion** — 3–4 Tage. Model `LessonNote(user_id, lesson_id, text)`, Textarea neben dem Video. Ersetzt das Community-Feature-Bedürfnis ohne Moderationslast.

---

## 🛡️ Refund-Defense (wenn Volumen wächst)

- [ ] **B6 · Drip-Onboarding** — 1 Tag. Modul 2 erst nach 3 Tagen, Modul 3 nach 7. Infrastruktur (`unlock_after_days`) existiert schon — nur Noras Kurse konfigurieren.
- [ ] **B7 · FAQ-Seite in der App** — 1 Tag. Statisches Markdown mit häufigen Fragen, linked aus dem Footer.
- [ ] **B8 · Offline-Download für Lektion 1 einer Sektion** — 2 Tage. Bunny-API für direct MP4, nur für "Einstiegslektionen".

---

## 🟡 Bugs/Hygiene — Mittel (entstanden aus Audit)

- [ ] **A13 · Race-Condition in `AdminUsers.load()`** — `frontend/src/pages/admin/AdminUsers.tsx`. Parallele load-Calls überschreiben sich. Fix: Abort-Controller.
- [ ] **A14 · Dashboard-Error-Handling** — `Dashboard.tsx:11-14`, `AdminDashboard.tsx:41`. `Promise.all().finally()` ohne `.catch()` → infiniter Spinner bei Fehler. Fix: Error-State.
- [ ] **A15 · `alert()` → Toast in AdminUsers** — `AdminUsers.tsx:98,123,132`. Inkonsistent mit Rest der App. Fix: shadcn/ui Toast oder eigene Notification-Component.
- [ ] **A16 · Doppelklick-Schutz auf Admin-Forms** — `AdminCourseDetail.tsx`, `AdminModuleDetail.tsx`, `AdminUsers.tsx`. Submit-Buttons nicht disabled während Request.
- [ ] **A17 · setTimeout-Leak in AdminCourseDetail** — StripeProductInput-Component. `setTimeout(() => setSaved(false), 2000)` ohne Cleanup.
- [ ] **A18 · Migration-Fehler besser loggen** — bereits partiell gefixt in `app/main.py`, nicht-"already exists"-Fehler werden geloggt. Nachprüfen, ob der Check alle Fälle trifft.
- [ ] **A19 · Fehlende Indizes auf heiß-gelesenen FKs** — `user.py:19 reset_token`, `course.py:75,118`. Teilweise bei A3/A4 mitgefixt — nochmal quer-prüfen, ob `ix_users_reset_token` wirklich angelegt wurde.
- [ ] **A20 · StripeProcessedEvent-Retention** — `app/api/stripe_webhook.py:28`. Cleanup-Task in drip_notifier_loop der Events > 90 Tage löscht.
- [ ] **A21 · Bunny delete-video ohne Ownership-Check** — `app/api/upload.py /delete-video`. Aktuell akzeptiert beliebige embed_urls. Fix: Embed-URL gegen Lessons matchen.

---

## 🔗 CRM-Integration — Folge-Hygiene (aus Review 2026-04-21)

- [ ] **R4 · Doppelter API-Call beim Einladen** — `nora-crm/src/lib/actions/courseInvite.ts:94`. `inviteContactToCourseAction` ruft `listCourses()` für den Title und dann `inviteContactToCourse()`. Zwei Roundtrips. Fix: Kurse-API `POST /users/invite` zusätzlich `course_title` zurückgeben lassen oder vom Frontend mitschicken.
- [ ] **R5 · Doppelklick → IntegrityError bei Enrollment** — selten, aber bei Force-Refresh während `sending=true` möglich. Der Unique-Constraint auf `(user_id, course_id)` feuert im Kurse-Backend und gibt 500 zurück. Fix: IntegrityError im `invite_user`-Endpoint abfangen und idempotent als „bereits eingeschrieben" behandeln.
- [ ] **R6 · E-Mail-Änderung im CRM desyncht Status** — Nach Edit der Contact-Email zeigt der Kurs-Lookup dauerhaft „Offen" weil er auf der alten Email in der Kurse-DB liegt. Lösung A: Warn-Dialog im Profil-Edit. Lösung B: automatischer Sync an Kurse-API (aber die Kurse-Seite hat jetzt Verification-Flow, die Email kann nicht stillschweigend geändert werden).
- [ ] **R7 · Gelöschter Kurs → fälschlich „Offen"** — Wenn ein Kurs in der Kurse-App gelöscht wird, cascade-löscht das `Enrollment`, und der CRM-Lookup findet es nicht mehr → Badge dauerhaft „Offen". Randfall, niedrige Priorität. Fix: Löschung weicher machen (`is_archived` flag statt hartes Delete) ODER im CRM-Lookup einen „Kurs existiert nicht mehr"-State einführen.
- [ ] **R8 · Stripe-Direktkäufe unsichtbar im CRM** — Wenn Kontakt direkt via Stripe kauft (kein CRM-Invite), hat die „Kurse"-Sektion im CRM keinen Eintrag, obwohl der Kunde Zugang hat. Fix: die Sektion sollte auch die `enrollments` aus dem Lookup anzeigen, nicht nur CRM-getriggerte Invitations. Synthetische „Historie"-Zeilen mit Typ „Direkt gekauft".

## 🟢 Bugs/Hygiene — Niedrig

- [ ] **A22 · `title/description` ohne `min_length`** — `app/schemas/course.py`. Leere Kurse möglich.
- [ ] **A23 · `sort_order` ohne `ge=0`** — negative Werte führen zu Sortierbugs.
- [ ] **A24 · Umlaute in AdminSettings** — Zeilen 106, 135, 149 (Teile bereits gefixt bei A6). Noch "andern"/"bestatigen" übrig.
- [ ] **A25 · TUS-Upload nicht abbrechen bei Navigation** — `AdminModuleDetail.tsx`. Ressourcen-Waste bei Bunny.
- [ ] **A26 · Attachment-Filename nicht unique pro Lesson** — theoretische Kollisionen.
- [ ] **A27 · Legacy-User ohne `terms_accepted_at`** — DSGVO. Einmalige Migration: `UPDATE users SET terms_accepted_at = created_at WHERE terms_accepted_at IS NULL AND created_at < '2026-04-21'` (Go-Live-Datum).

---

## 🔒 Security-Härtung (aus post-launch.md)

- [ ] **JWT-TTL 7d → 24h + Refresh-Token** — `app/core/config.py:7`. Access-Token 1h, Refresh-Token 30d in HttpOnly-Cookie. Ohne Refresh fliegen Teilnehmerinnen ständig raus.
- [ ] **PBKDF2 → bcrypt oder argon2** — `app/core/auth.py:22-33`. Migration beim nächsten Login.
- [ ] **JWT aus `localStorage` → HttpOnly-Cookie** — braucht CSRF-Token-Handling, größerer Umbau.
- [ ] **Password-Reset-Token als "used" markieren** — `app/api/auth.py`. Defense-in-depth.
- [ ] **Session-Invalidation bei Passwort-Change** — `change_password`-Endpoint. Fix: `token_version` auf User, im JWT-Claim.
- [ ] **Bunny-Upload: File-Type + Size-Validation** — `app/api/upload.py`. Beschränken: nur `video/*`, max N GB.
- [ ] **Bunny Token Authentication für Video-Playback** — Aktuell ist die Bunny-Library auf "Block direct url file access = OFF" weil das auf iOS Safari/Chrome den Stream sonst blockt (siehe Incident 2026-05-03). Folge: jemand mit der CDN-URL kann das Video ohne Login abspielen. Sauberer Fix: signed URLs mit kurzer Ablaufzeit. Ablauf: Backend generiert pro Lektion+User einen Token (HMAC mit `BUNNY_TOKEN_AUTH_KEY`, expires=jetzt+1h, optional IP-Bind), Frontend bekommt embed-URL mit `?token=...&expires=...`. In Bunny dann "Token Authentication" wieder ON. Refresh-Logik klären (langer Video, Token läuft mitten ab).
- [ ] **Security-Header in nginx.conf** — X-Frame-Options, X-Content-Type-Options, CSP. Cloudron setzt nur HSTS.

---

## 📊 Ops / Monitoring

- [ ] **Sentry oder vergleichbares Error-Tracking** — DSN via ENV. 500er werden sonst nie gesehen.
- [ ] **Alembic einführen** — `app/main.py:22-34`. Bevor die DB komplexere Änderungen braucht.
- [ ] **Backup-Strategie für Bunny-Videos** — Postgres wird gebackupped, Bunny-Content nicht.
- [ ] **Vite Source-Maps in Prod deaktivieren** — `frontend/vite.config.ts` `build.sourcemap = false`.
- [ ] **`VITE_API_URL` als Build-Var** — falls Frontend mal getrennt deployed wird.

---

## ⚖️ Compliance / DSGVO

- [ ] **Datenexport-Endpoint** — `GET /api/v1/auth/me/export` → JSON mit allen personenbezogenen Daten.
- [ ] **DSGVO-Löschung / Anonymisierung** — Admin-Delete-User ist heute hart. Alternative: Anonymisierung (Email+Name → Hash), Enrollment/Progress bleibt für Statistik.
- [ ] **Admin-Audit-Log** — Tabelle `admin_audit_log(who, what, when, target)`. Invites, Deaktivierungen, Passwort-Resets.
- [ ] **E-Mail-Verifikation bei Self-Registration** — `/register` (aktuell nicht öffentlich verwendet).

---

## 💡 Nice-to-have (aufheben bis echter Bedarf)

- Password-Strength-Meter im Accept-Invite-Formular
- Resend-Webhook für Bounces/Complaints → User bei hartem Bounce deaktivieren
- Unsubscribe-Header in allen Mails (Deliverability)
- Template-Engine (Jinja2) statt f-Strings für E-Mail-HTML
- Dev-Mode `MAIL_MOCK=true` für lokales Testen ohne echten Versand
- Quiz/Tests, Aufgaben/Submissions, Kommentare pro Lektion — **explizit nicht priorisiert** (siehe deep-audit PM-Kritik). Nur bauen wenn echte Nachfrage aufkommt.
- Admin: Lektionen innerhalb eines Kurses per Drag-and-Drop verschiebbar machen. Datenmodell hat schon `sort_order` (siehe A23) — UI in `AdminCourseDetail.tsx`/`AdminModuleDetail.tsx` plus Bulk-Update-Endpoint, der die neue Reihenfolge persistiert.

---

## Erledigt (Historie)

Go-Live-Block (vor 2026-04-21):
- ✅ Consent-Invite-Flow mit Token + AGB (`9449f52`)
- ✅ Secret-Key-Validation + CORS + Passwort-Min 8 (`d156d21`)
- ✅ Seed-Script neutralisiert + Cloudron-Manifest (`cfdbc4c`)
- ✅ Stripe-Idempotency + Rate-Limiting (`f769bfc`)
- ✅ Brand-Design für alle Mails (`d44d254`)

Deep-Audit-Block (2026-04-21):
- ✅ A1 Progress-Enrollment-Check, A2 JWT-raus-aus-URL, A3 FK-Cascades, A4 Unique-Constraints, A5 Auto-Logout ohne Reload, A6 Passwort-Min 8 überall (`6f3137e`)
- ✅ A7 handleToggleComplete error-handling, A8 Stripe-Refund-Handler, A9 E-Mail-Verification-Flow, A10 Drip-Buffer 48h, A11 Frontend-Admin-Route-Block, A12 `datetime.utcnow` → `utc_now` (`9fc632f`)

CRM ↔ Kurse Integration (2026-04-21):
- ✅ Service-Token-API + Admin-UI (Kurse `e900b5f`)
- ✅ CourseInvitation-Modell + Contact-Kurse-Sektion + Historie (CRM `98dd6d1`)
- ✅ Accept-Status-Sync (Lookup-Endpoint Kurse `9ad58bb` · Status-Pull CRM `d6f5cd3`)
- ✅ R1 Lookup case-insensitive (Kurse `26e4a5f`) · R2 Historie-Label · R3 Copy-Link nur neueste (CRM `520e6fa`)

---

## Session-Notes 2026-04-27

**Milestone:** Erste zahlende Kundinnen eingeladen.

**Pre-Launch-Check (heute Abend):**
- Code-Stand sauber: Auth/Invite-Flow geprüft (`app/api/auth.py`, `app/core/auth.py`, `seed.py`). Kein hardcoded `admin123` mehr — Admin nur via ENV-Vars `NORA_ADMIN_EMAIL`/`NORA_ADMIN_PASSWORD` (min 8 chars). Invite-Token: `secrets.token_urlsafe(32)`, 7d TTL. Forgot-Password resendet Invite wenn noch nicht akzeptiert. Login blockiert solange `invite_token` gesetzt ist.
- Mitgliederbereich-Feature (Merge 2026-04-24) seit 3 Tagen live. Default-Tab nach Login: `Mitgliederbereich`. Hubs für die heute verkauften Kurse befüllt, Bunny-Storage-ENV-Vars (`BUNNY_STORAGE_ZONE/KEY/PULL_ZONE`) gesetzt.
- Cloudron-Operations: Default-Admin / Test-Student bereits entfernt.
- E2E-Test (Invite → Mail → Accept → Lesson) durchgelaufen.
- Stripe-Direktkauf bewusst out-of-scope für diesen Launch (manuelle Invites über Admin-UI).

**Bewusst NICHT vor Launch angefasst** (alles im Backlog, kein akutes Risiko):
- Security-Härtung: JWT-TTL 7d, PBKDF2 → bcrypt, JWT in HttpOnly-Cookie, Reset-Token-„used"-Flag, Session-Invalidation bei Passwort-Change.
- Sentry / Alembic / Source-Maps-aus.
- A13–A27 Bug-Hygiene.

**Nach 24–48h checken:** siehe „Hier morgen weitermachen".

---

## Session-Notes 2026-04-21

**Gestartet mit:** Frage „Können wir live?" — Audit ergab 6 Blocker, 6 hohe Bugs, 27 mittlere.
**Am Ende:** Plattform live, CRM-Integration live, 0 Blocker, 0 hohe Bugs.

**Wichtige Code-Orte, die morgen relevant sein könnten:**
- `app/api/progress.py:mark_complete` — Einstiegspunkt für Zertifikat-Trigger
- `app/core/drip_notifier.py:drip_notifier_loop` — Template für `inactivity_loop` (B4)
- `app/core/email.py:_wrap_in_brand_template` + `_cta_button` — für alle neuen Mails nutzen, damit Branding konsistent bleibt
- `requirements.txt` — wenn PDF-Lib gebraucht: dort ergänzen, wird beim Deploy automatisch installiert

**Cloudron-ENV-Vars, die bereits gesetzt sind (nicht überschreiben):**
- Kurse: `NORA_SECRET_KEY`, `RESEND_API_KEY`, `MAIL_FROM`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `BUNNY_API_KEY`, `BUNNY_LIBRARY_ID`
- CRM: `COURSE_PLATFORM_URL`, `COURSE_PLATFORM_SERVICE_TOKEN` (für Integration — nicht anfassen)

**Offen beim Kunden (Nora):**
- Alten `admin123`-Account-Passwort ändern (Go-Live-Empfehlung)
- Test-Student ggf. löschen
- Unterschrift-Grafik bereitstellen, wenn B2 angefangen wird
