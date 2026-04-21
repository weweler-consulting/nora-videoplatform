# Deep-Audit: Bugs, Security, Datenmodell, Features

Vollständiges Audit nach Go-Live-Arbeit. Findings aus vier parallelen Agenten (Backend, Frontend, Datenmodell, Produkt-Manager), von mir konsolidiert + verifiziert. Die bereits im `post-launch.md` stehenden Themen sind hier **nicht** doppelt aufgeführt.

---

# A · Bugs & Sicherheit

## 🔴 Kritisch (sollten zeitnah gefixt werden)

### A1 · Progress-Tracking ohne Enrollment-Check
**`app/api/progress.py:14-44`** — `POST /progress/{lesson_id}/complete` und `/uncomplete` prüfen nicht, ob der User im Kurs eingeschrieben ist. Folge: Eingeloggte User können Progress auf Lektionen markieren, zu denen sie keinen Zugang haben. Verfälscht Noras Admin-Analytics (Durchschnitts-Fortschritt, inaktive Kunden) und lässt sich trivial scripten.
**Fix:** Join über `Lesson → Section → Module → Course → Enrollment` prüfen, wie es `attachments.py:91-100` bereits macht.

### A2 · JWT als Query-Parameter in Download-URLs
**`frontend/src/pages/LessonView.tsx:161`** — Token wird in `<a href>` eingebettet: `/api/v1/attachments/{id}/download?token=...`. Browser-History, Referer-Header und Server-Logs leaken den Token. Backend (`attachments.py:64-75`) akzeptiert das absichtlich via `Query`-Parameter.
**Fix:** Download über JavaScript-Fetch mit `Authorization`-Header + Blob-URL. ODER: kurzlebige Signed-URLs (Endpoint gibt One-Time-Download-Token mit 5 Min Gültigkeit aus).

### A3 · FK-Constraints ohne `ondelete`-Cascade
**`app/models/course.py:30,46,58,75,76,87,88,96,97`** — alle `ForeignKey(...)` ohne `ondelete="CASCADE"`. ORM-Cascade (`cascade="all, delete-orphan"`) greift nur über Session — direkte SQL-Deletes oder abgebrochene Cascades hinterlassen Orphans. Insbesondere: wenn ein Modul hart per SQL gelöscht wird, bleiben `DripNotification`- und `ModuleUnlock`-Zeilen zurück.
**Fix:** Überall `ondelete="CASCADE"` zur FK-Definition ergänzen + Migration `ALTER TABLE ... DROP CONSTRAINT ... ADD CONSTRAINT ... ON DELETE CASCADE`.

### A4 · Fehlende Unique-Constraints
**`app/models/course.py`** — kein UniqueConstraint auf:
- `Enrollment(user_id, course_id)`
- `DripNotification(user_id, module_id)`
- `ModuleUnlock(user_id, module_id)`
- `LessonProgress(user_id, lesson_id)`

App-seitig werden Dubletten geprüft, aber Race Conditions können Duplikate erzeugen (zwei parallele Requests beim Einschreiben). Beim Drip-Notifier besonders heikel: bei doppeltem `DripNotification`-Insert crasht nur die zweite Insertion, aber die Mail wurde schon zweimal verschickt.
**Fix:** `UniqueConstraint` per `__table_args__` auf jedes Model + Migration.

### A5 · Auto-Logout killt aktiven State
**`frontend/src/lib/api.ts:31-34`** — Bei 401 macht `window.location.href = '/login'` einen Full-Reload. Während Upload oder Formular geht alles verloren, keine Warnung. Besonders problematisch bei Video-Upload, der minutenlang läuft.
**Fix:** State via CustomEvent in Layout propagieren → Toast "Sitzung abgelaufen" + React-Router-Navigation.

### A6 · Passwort-Mindestlänge-Inkonsistenz
**`frontend/src/pages/admin/AdminSettings.tsx:45-46`** — Prüft noch auf 6 Zeichen, restlicher Code auf 8. Das Backend (`auth.py:74-75` change_password) nutzt auch noch 6 als Mindestlänge — der Go-Live-Fix war dort unvollständig, nur `reset-password` und `invite-accept` wurden migriert. Widerspruch zwischen Pydantic-Schema-Minlänge und inline-Check.
**Fix:** Frontend + Backend (auch `auth.py:74-75`) auf 8 angleichen.

---

## 🟠 Hoch (sollte in den nächsten 2 Wochen)

### A7 · `LessonView.handleNext` ignoriert API-Fehler
**`frontend/src/pages/LessonView.tsx` (handleNext)** — `api.completeLesson()` ohne try/catch. Navigiert auch wenn Save fehlgeschlagen → User denkt, alles ist erledigt, Fortschritt geht verloren.
**Fix:** try/catch mit Error-Toast, Navigation erst nach erfolgreichem Save.

### A8 · Stripe-Webhook handhabt keine Refunds / Payment-Failures
**`app/api/stripe_webhook.py:51-53`** — nur `checkout.session.completed`. `charge.refunded`, `payment_intent.payment_failed`, `customer.subscription.deleted` werden ignoriert. Folge: Refunded-Kundinnen behalten Kurs-Zugang.
**Fix:** Handler für `charge.refunded` → `Enrollment` entfernen, ggf. E-Mail an Admin.

### A9 · E-Mail-Änderung ohne Verifikation
**`app/api/auth.py:112-122`** `update_profile` — E-Mail kann ohne Verifikation geändert werden. Kein Account-Takeover-Risk (DB unique check blockt), aber: (a) Kundin vertippt sich → locked out, (b) Phishing-Szenarien möglich.
**Fix:** E-Mail-Änderung triggert Verification-Link an neue Adresse, bestätigen vor Wechsel.

### A10 · Drip-Notifier 2h-Buffer zu kurz
**`app/core/drip_notifier.py:45-46`** — Verpasste Unlocks (App >2h offline) werden **nie** benachrichtigt. Bei Cloudron-Wartung, Deploy-Downtime, Container-Restart durchaus realistisch.
**Fix:** Buffer auf 48h erweitern + Verwendung von `DripNotification`-Tabelle als Dedup-Garantie (existiert schon) — dann kann der Buffer risikofrei groß sein.

### A11 · Admin-Routes im Frontend nicht enforced
**`frontend/src/App.tsx:17-19`** — `ProtectedRoute` prüft nur Token, nicht `is_admin`. Backend schützt zwar alles, aber das UI lässt einen Student in `/admin`-Routen laufen und crasht dort, statt sauber zu redirecten.
**Fix:** `AdminRoute` Wrapper, der `api.me()` cached checkt.

### A12 · `datetime.utcnow()` deprecated in Python 3.12+
**25 Stellen** in `app/` — Deprecated, wird in Python 3.13 entfernt. Cloudron-Python ist 3.12.
**Fix:** Global `datetime.now(timezone.utc)` + `DateTime(timezone=True)` in den Models (Breaking Change für bestehende naive Timestamps — muss migriert werden).

---

## 🟡 Mittel

### A13 · Race Condition in `AdminUsers.load()`
**`frontend/src/pages/admin/AdminUsers.tsx`** — parallele `load()`-Calls können sich überschreiben. Bei schnellen Enrollment-Änderungen alte Daten sichtbar.
**Fix:** Abort-Controller ODER Request-ID-Pattern.

### A14 · Dashboard / AdminDashboard ohne Error-State
**`Dashboard.tsx:11-14`, `AdminDashboard.tsx:41`** — `Promise.all().finally()` ohne `.catch()`. Bei Fehler infiniter Spinner, nie ein Fehler-UI.
**Fix:** `.catch(err => setError(err.message))` + Fehler-Component.

### A15 · `alert()` statt Toast in `AdminUsers`
**`AdminUsers.tsx:98,123,132`** — blocking, unstyled, inkonsistent zum Rest der App.
**Fix:** shadcn/ui Toast oder einfache eigene Notification-Component.

### A16 · Doppelklick-Schutz fehlt auf Admin-Forms
**`AdminCourseDetail.tsx`, `AdminModuleDetail.tsx`, `AdminUsers.tsx`** — Submit-Buttons werden nicht disabled während Request läuft → doppelte Erstellung möglich.
**Fix:** `disabled={submitting}` + lokalen State.

### A17 · setTimeout-Leak in `AdminCourseDetail` StripeProductInput
**`AdminCourseDetail.tsx:~202`** — ohne Cleanup in `useEffect`. Bei schnellem Unmount React-Warning.
**Fix:** Timer in `useEffect` mit Cleanup-Return.

### A18 · Migration-Fehler verschluckt Nicht-"already-exists"-Fälle
**`app/main.py:35-39`** — `except Exception: pass` fängt zu breit. FK-Konflikte, Permission-Fehler werden stumm ignoriert.
**Fix:** In `except` den Fehlertext prüfen, alles außer "already exists" loggen.

### A19 · Fehlende Indizes auf heiß-gelesenen FKs
**`user.py:19 reset_token`, `course.py:75-76 Enrollment FKs`, `course.py:118-119 LessonProgress FKs`** — ohne Index. `WHERE reset_token = ?` full-table-scan ab paar Tausend Usern, Progress-Queries im Dashboard langsam.
**Fix:** `index=True` auf die genannten Felder.

### A20 · StripeProcessedEvent wächst unbegrenzt
**`app/api/stripe_webhook.py:28-32`** — keine Retention-Policy. In 2 Jahren Millionen Zeilen.
**Fix:** Cleanup-Task (zusammen mit drip_notifier_loop) der Events > 90 Tage löscht.

### A21 · Admin-Löschung von Bunny-Videos ohne Ownership-Check
**`app/api/upload.py` `/delete-video`** — nimmt embed_url entgegen, löscht bei Bunny. Kein Check, ob die URL zu einer Lesson im System gehört. Admin könnte theoretisch jedes Video im Bunny-Account löschen.
**Fix:** Embed-URL gegen vorhandene Lessons matchen, nur Löschen wenn Zuordnung existiert.

---

## 🟢 Niedrig

- **A22**: `title/description` ohne `min_length` in Pydantic-Schemas (`app/schemas/course.py`) — leere Kurse möglich.
- **A23**: `sort_order` ohne `ge=0` Validation — negative Werte führen zu Sortierbugs.
- **A24**: Umlaute in `AdminSettings.tsx` (Zeilen 42, 46, 51, 106, 135, 149) fehlerhaft ("Passworter", "bestatigen"). Encoding-Verlust.
- **A25**: TUS-Upload wird nicht abgebrochen bei Navigation (ressourcenverbrauch bei Bunny).
- **A26**: Attachment-Filename nicht unique pro Lesson — theoretische Kollisionen möglich.
- **A27**: Legacy-User ohne `terms_accepted_at` — DSGVO: bestehende Kundinnen wurden nie ausdrücklich eingeholt, sie haben aber die Plattform genutzt. Backfill mit `created_at` als pragmatische Annahme.

---

# B · Feature-Backlog aus PM-Sicht

Sortiert nach **Umsatz-Impact × Aufwand**. Alle Punkte referenzieren die Zielgruppe (Ernährungs-Coach-Kundinnen, nicht tech-affin).

## 🚀 Umsatz-Bringer (in dieser Reihenfolge bauen)

### B1 · Video-Position merken (Resume-Play)
- **Effort:** 3–5 Tage
- **Warum:** Größter Pain-Punkt — Internet bricht ab, Video fängt von vorne an → Kundin gibt auf. Konkret: neues Feld `LessonProgress.last_position_seconds`, Auto-Seek beim Player-Load, Update alle 10s.
- **Umsatz-Wirkung:** Reduziert Drop-Off massiv, ist der stärkste Retention-Hebel. Ohne das bauen alle Kurs-Profis nichts.

### B2 · Abschluss-Zertifikat als PDF
- **Effort:** 2–3 Tage
- **Warum:** Bei 100% Progress auto-generiertes PDF mit Name + Kurs + Datum + Unterschrift-Scan. Download + Mail. Kundinnen teilen auf Instagram = kostenlose Werbung. Gleichzeitig psychologisch: "Ich will das PDF" motiviert bis zum Ende.
- **Umsatz-Wirkung:** Social Proof + Completion-Rate. Bestandsmaterial (Zertifikat-Template) braucht Nora sowieso.

### B3 · Cross-Sell-Mail bei Kurs-Abschluss
- **Effort:** 1–2 Tage (Template + Trigger im Progress-Endpoint)
- **Warum:** Nach 100% automatisch Mail "Du hast geschafft! Dein nächster Schritt: [Kurs 2] — für dich 15% Rabatt (48h)." Rabatt-Code via Stripe Coupon.
- **Umsatz-Wirkung:** Conversion auf Bestandskundin ist 5–10× billiger als Neuakquise. Pflicht-Feature.

### B4 · Inaktivitäts-Reminder (Win-Back)
- **Effort:** 1–2 Tage (neuer Loop analog `drip_notifier`)
- **Warum:** User mit 0 Progress seit 14 Tagen → freundliche Erinnerungs-Mail. Bei 30 Tagen kein Progress → Nora persönlich Bescheid geben (Admin-Dashboard-Alert).
- **Umsatz-Wirkung:** 5% Reactivation ist realistisch = reiner Zusatzumsatz ohne Akquisekosten.

### B5 · Private Notizen pro Lektion
- **Effort:** 3–4 Tage
- **Warum:** Kundinnen wollen sich Sachen merken (persönliche Reflexion bei Ernährung stark). Kein Community-Feature, nur persönliche Notizen — keine Moderations-Last für Nora. Neues Model `LessonNote(user_id, lesson_id, text)`, einfaches Textarea neben Video.
- **Umsatz-Wirkung:** Erhöht Perceived Value, Reduziert Refunds, Tie-in zum nächsten Kurs.

---

## 🛡️ Refund-Defense (wenn Volumen wächst)

### B6 · Drip-Onboarding: nicht alle Module sofort offen
- **Effort:** 1 Tag
- Modul 1 sofort. Modul 2 nach 3 Tagen. Modul 3 nach 7 Tagen. (Drip-Infrastruktur existiert schon — Noras Kurse müssen nur `unlock_after_days` gesetzt bekommen.)
- **Nutzen:** "Ich schaff das nie alles" → "Ich mache nur heute Lektion 1". Drastisch weniger Refund-Anträge bei Überwältigung.

### B7 · FAQ-Seite in der App
- **Effort:** 1 Tag (statisches Markdown)
- "Ich kann das Video nicht öffnen?" / "Wie speichere ich meinen Platz?" / "Kann ich offline schauen?" — beantwortet 80% der Kundinnen-Anfragen, bevor sie Nora nerven.

### B8 · Offline-Download für Lektion 1 einer Kurs-Sektion
- **Effort:** 2 Tage (Bunny-API für direct MP4-Download, nur für bestimmte Lektionen)
- Reduziert "Netz war schlecht"-Refunds. Nur für die ersten Lektionen, wegen DRM-Risiko.

---

## ⚖️ Roadmap-Kritik

Aktuelle Roadmap priorisiert m. E. falsch. Vorschlag:

| Aktuell | Neu |
|---|---|
| **1. Zertifikat** Hoch/Mittel | **1. Resume-Play** Hoch/Mittel (wichtiger) |
| **2. E-Mail-Automationen** Hoch/Groß | **2. Zertifikat** Hoch/Klein |
| **3. Kommentare** Mittel/Mittel | **3. Cross-Sell + Inaktivität** Hoch/Klein |
| **4. Quiz/Tests** Mittel/Mittel | **4. Private Notizen** Mittel/Mittel |
| **5. Aufgaben/Submissions** Mittel/Groß | **5. Drip-Onboarding** Hoch/Minimal |
| **6. Gruppen** Niedrig/Mittel | **6. FAQ + Offline** Niedrig/Klein |

**Wegstreichen aus Roadmap:**
- **Quiz/Tests**: Zielgruppe kauft nicht wegen Quiz. Busywork. Nicht priorisieren bis echte Nachfrage.
- **Aufgaben/Submissions**: Erzeugt Support-Last für Nora, nicht für dich. Wenn automatisiertes Feedback → reden wir drüber. Sonst: nein.
- **Kommentare pro Lektion**: Community-Feature, das Nora moderieren müsste. Ersetzen durch *private Notizen* (siehe B5) — löst dasselbe Kundinnen-Bedürfnis ohne Moderations-Overhead.
- **Gruppen/Kohorten**: Erst ab ~100 gleichzeitigen Teilnehmerinnen relevant. Nicht jetzt.

---

## Vorschlag nächste 4 Wochen

**Woche 1:** A1 (Progress-IDOR) + A2 (Token-URL) + A6 (Password-Minlänge) + A4/A3 (Constraints & Cascade) — der Security-Block.
**Woche 2:** B1 (Resume-Play) — das wichtigste Produkt-Feature.
**Woche 3:** B2 (Zertifikat) + B3 (Cross-Sell-Mail).
**Woche 4:** B4 (Inaktivität) + B6 (Drip-Onboarding).

Summe: 4 Wochen. Sicherheit geflickt, Plattform spürbar upgegraded, direkter Umsatzhebel drin.
