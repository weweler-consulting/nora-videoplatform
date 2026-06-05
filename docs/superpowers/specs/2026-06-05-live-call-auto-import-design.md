# Live-Call-Recording → Kurs: Automatischer Import (Design)

**Datum:** 2026-06-05
**Status:** Design abgenommen, Spec zur Review
**Repo:** nora-videoplatform (Option A – alles in der Videoplattform)

## Problem & Ziel

Nora moderiert ~2×/Woche Gruppen-Live-Calls (Google Meet) pro Kurs. Die Calls werden
aufgezeichnet und sollen den Klientinnen auf der Video-Kurs-Plattform zur Verfügung stehen.
Heute manuell: warten bis Meet-Processing fertig → Drive-Datei finden → herunterladen →
Videoplattform öffnen → Modul anlegen → Video hochladen → Ankündigung verschicken. Das wird
**vergessen, nachgezogen, bleibt liegen.**

**Ziel:** Das fertige Recording wird automatisch in den **richtigen Kurs** als **versteckte
Lektion** importiert; Nora bekommt **eine Mail mit 1-Klick-Freigabe**; ihr Klick macht die
Lektion sichtbar und verschickt die Ankündigung. Der manuelle Kram UND das Vergessen sind weg,
die Kontrolle vor der Kundinnen-Mail bleibt.

## Scope

**In v1:** Drive-Erkennung, Import (Drive→Bunny→versteckte Lektion), Serie→Kurs-Mapping,
Hybrid-Platzierung, 1-Klick-Freigabe inkl. Ankündigung, Admin-Liste offener Importe.

**Bewusst NICHT in v1 (YAGNI):** CRM-Listing der Live-Calls / Recording-Links im Kontakt;
Auto-Schnitt/Trimmen; Multi-Coach; Import von 1:1-Calls/Beratungsgesprächen.

## Ist-Zustand (vom User bestätigt, 2026-06-05)

- Meet-Recordings landen in **einem** Drive-Ordner **„Meet Recordings"** (Meine Ablage von
  `nora@noraweweler.de`), Folder-ID `1rruYIZ956dNjllrenSGleL4UoZHZuM9h`.
- **Namensschema Gruppen-Live-Call (Video):** `Live Call | <Kurs> - YYYY/MM/DD HH:MM <TZ> - Recording`
  (rotes Video-Icon, mimeType `video/*`, ~0,5–1,1 GB). Dazu ein separates Google-Doc
  `Live Call | <Kurs> – YYYY/MM/DD … – Notizen von …` (klein) – **wird ignoriert**.
- **1:1-Calls/Beratungsgespräche** liegen im selben Ordner, anders benannt
  (`Glukose Balance Coaching – <Name> x Nora`, `Beratungsgespräch – …`) → über den Prefix
  `Live Call | ` ausgeschlossen.
- **Processing-Delay:** Minuten bis ~1 Stunde nach dem Call.
- **Google Workspace** (Domain `noraweweler.de`) → Service-Account + Domain-Wide-Delegation möglich.

## Auth

**OAuth eines Workspace-internen Clients** (User-Type „Intern" → `drive.readonly` ohne Google-
App-Verifizierung). Hintergrund: Die Org-Policy `iam.disableServiceAccountKeyCreation` blockiert
Service-Account-Keys (genau die Wand, an der auch das CRM-Setup scheiterte → das CRM nutzt
deshalb ebenfalls OAuth). Ein Refresh-Token wird **einmalig** per `scripts/google_oauth_setup.py`
(InstalledAppFlow, Browser-Consent als nora@) geholt; Access-Tokens danach automatisch erneuert.

ENV (Prefix `NORA_`):
- `NORA_GOOGLE_OAUTH_CLIENT_ID`
- `NORA_GOOGLE_OAUTH_CLIENT_SECRET`
- `NORA_GOOGLE_OAUTH_REFRESH_TOKEN`
- `NORA_MEET_RECORDINGS_FOLDER_ID` (Default `1rruYIZ956dNjllrenSGleL4UoZHZuM9h`)

Kalender-API wird für die Erkennung **nicht** benötigt (Drive-Name trägt Kurs + Datum). Optional
später, falls reichere Termin-Metadaten gewünscht.

## Datenmodell (additiv, live-sicher)

- **`LiveCallSeries`** (neu): Verknüpfung Recording-Name → Kurs.
  - `id`, `course_id` (FK), `recording_name_prefix` (z.B. `Live Call | Glukose Balance`),
    `drive_folder_id` (Default = Meet-Recordings-Ordner), `active` (bool), `created_at`.
  - Einmalig pro Kurs im Admin gesetzt.
- **`LiveCallImport`** (neu): Dedup + Audit + Freigabe-Zustand.
  - `id`, `series_id` (FK), `drive_file_id` (**unique** – Dedup-Schlüssel), `recording_name`,
    `occurrence_at` (aus Name geparst, nullable), `module_id` (nullable), `lesson_id` (nullable),
    `status` (`imported` | `published` | `dismissed` | `failed`), `retry_count`, `last_error`,
    `created_at`, `published_at`.
- **`Lesson.is_published`** (neues Bool, `default=true`, `server_default='true'`): bestehende
  Lektionen unverändert sichtbar; auto-importierte starten `false` (versteckt) bis zur Freigabe.
  Client-Auslieferung filtert `is_published=false` für Nicht-Admins.

## Erkennung (Background-Loop, ~20 Min – Muster wie `crm_sync_loop`)

Pro aktiver `LiveCallSeries`:
1. Drive: Dateien im `drive_folder_id` listen mit
   `mimeType startsWith 'video/'` **und** `name startsWith recording_name_prefix`
   **und** `modifiedTime` innerhalb Lookback-Fenster (z.B. 14 Tage)
   **und** `drive_file_id` noch nicht in `LiveCallImport`.
   (mimeType ist die maßgebliche Unterscheidung Video vs. Notizen-Doc.)
2. Für jeden neuen Treffer: `occurrence_at` aus dem Namen parsen
   (`… - YYYY/MM/DD HH:MM <TZ> - Recording`) → `LiveCallImport(status='imported')` anlegen.

## Import-Pipeline (pro offener `LiveCallImport`, idempotent pro Schritt)

1. **Ziel-Modul bestimmen (Hybrid-Platzierung):**
   - Suche im Kurs ein Modul, dessen Titel das `occurrence_at`-Datum enthält (DE-Formate tolerieren:
     `04.06.2026`, `4.6.`, `04.06.` …) **und** noch keine Video-Lektion hat → Platzhalter füllen
     (Position + Freischalt-Timing der Kursleiterin bleiben erhalten).
   - Sonst neues Modul `Live Call <DD.MM.YYYY>` am Ende anlegen (`sort_order = max+1`).
   - Section sicherstellen (sonst „Aufzeichnung" anlegen).
2. **Bunny-Video anlegen** (bestehende create-video-Logik wiederverwenden) → `video_id` + `embed_url`.
3. **Drive→Bunny streamen** (server-seitig, **nicht** in RAM): Download in Temp-Datei →
   Upload zu Bunny → Temp-Datei löschen. (`bunny_storage` um Server-Upload-Helfer erweitern.)
4. **Versteckte Lektion anlegen** (`type='video'`, `video_url=embed_url`, `is_published=false`,
   Titel `Live-Call <DD.MM.YYYY>`).
5. `LiveCallImport` updaten: `module_id`, `lesson_id`, `status='imported'`.
6. **Nora anstupsen:** Freigabe-Mail (siehe unten).

**Fehler in einem Schritt:** `retry_count++`, `last_error`, Zeile bleibt offen → nächste Runde
Retry; nach N Versuchen `status='failed'` + einmal laut loggen. Jeder Schritt prüft, ob bereits
erledigt (z.B. Bunny-Video für diesen Import schon angelegt) → keine Doppelarbeit/Doppel-Upload.

## Freigabe-Flow (1 Klick)

- **Signierter HMAC-Token** (`import_id` + Aktion + Secret) in der Mail. Endpunkte:
  `GET /api/v1/live-calls/approve?import_id=…&token=…` und `…/dismiss?…`.
- **Freigeben:** `lesson.is_published=true`; Ankündigung über das **bestehende Announcement-System**
  erstellen+senden (`target_type='lesson'`, Default-Text, editierbar); `status='published'`,
  `published_at`. **Idempotent:** erneuter Klick auf bereits freigegebenen Import = No-op
  (keine zweite Ankündigung).
- **Verwerfen:** versteckte Lektion + Bunny-Video löschen; `status='dismissed'`.
- **Admin-Fallback:** Liste „Anstehende Live-Call-Importe" mit Freigeben/Verwerfen.

**Default-Ankündigung (editierbar):**
Betreff: `Die Aufzeichnung vom <DD.MM.> ist da 💛`
Text: kurzer Default + CTA-Link zur Lektion.

## Komponenten (isoliert, je testbar)

- **`google_drive_client`** – Service-Account-Auth (Impersonation) + Listen/Download. Mockbar.
- **`live_call_detector`** – Ordner-Poll + Name-Parsing → Kandidaten-Zeilen.
- **`live_call_importer`** – Platzierung + Bunny-Upload + versteckte Lektion.
- **`live_call_approval`** – Token erzeugen/prüfen + Freigeben(publish+announce)/Verwerfen.
- **`live_call_loop`** – Orchestrierung (detect → import → mail), Intervall; in `lifespan` gestartet.
- **Admin** – Serie→Kurs-Mapping CRUD + Liste offener Importe.

## Tests

- **Unit:** Name-Parsing (mehrere Formate/TZ), Prefix-Filter (schließt Notizen-Doc + 1:1-Calls aus),
  Datum→Platzhalter-Match, Token sign/verify, Loop-Idempotenz (kein Doppel-Import), Freigabe ohne
  Doppel-Ankündigung, Verwerfen löscht Lektion+Bunny.
- Drive- und Bunny-Clients in Tests **mocken** – keine echten Google/Bunny-Calls.

## Spike VOR dem Vollbau (de-risk)

Mit **einem echten Recording** validieren:
1. Service-Account-Impersonation + Drive-Listing liefert die Datei mit erwarteten Feldern
   (`mimeType`, `name`, `modifiedTime`, `id`).
2. Name-Parsing trifft Kurs-Prefix + Datum.
3. **1-GB-Stream Drive→Bunny** läuft auf dem Cloudron-Container durch (Temp-Disk/Speicher ok).

## Setup-Anforderungen (operativ)

- GCP-Projekt `nora-automation` (Org `noraweweler.de`), Drive-API aktiviert.
- OAuth-Consent-Screen **User-Type „Intern"**; OAuth-Client **Typ Desktop** → Client-ID + Secret.
- Einmalig `scripts/google_oauth_setup.py <client_secret.json>` laufen lassen (Consent als nora@)
  → Refresh-Token. Die drei Werte als ENV setzen (`NORA_GOOGLE_OAUTH_CLIENT_ID/_SECRET/_REFRESH_TOKEN`)
  + `NORA_MEET_RECORDINGS_FOLDER_ID`.
- **Eindeutiger Live-Call-Titel pro Kurs:** Der 2. Kurs darf nicht denselben Prefix
  `Live Call | Glukose Balance` nutzen, sonst Kollision. Beim Setup prüfen/abgrenzen.

## Phasen

1. **Spike** (Auth + Drive-Erkennung + 1-GB-Stream) — Risiko raus.
2. **Core-Pipeline** (detect → import → versteckte Lektion) + Serie→Kurs-Mapping-Admin.
3. **Freigabe** (1-Klick-Mail + Ankündigung) + Admin-Liste.

## Offene Setup-Frage (nicht blockierend)

- Recording-Name-Prefix des 2. Kurses (Eindeutigkeit ggü. `Live Call | Glukose Balance`) → beim
  Setup festlegen.
