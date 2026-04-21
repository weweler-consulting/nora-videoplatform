# Backlog — Nora Videoplatform

Eine Liste. Hier weitermachen, wenn du Zeit hast. Erledigte Punkte abhaken, nicht löschen — sonst geht die Historie verloren. Neue Punkte unten anhängen.

**Historie / Hintergrund:**
- `tasks/deep-audit.md` — vollständiger Audit nach Go-Live
- `tasks/post-launch.md` — Security/Ops/Compliance-Themen (zum Teil hier konsolidiert)
- `tasks/todo.md` — alter Einladungsflow-Plan (fertig)

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
