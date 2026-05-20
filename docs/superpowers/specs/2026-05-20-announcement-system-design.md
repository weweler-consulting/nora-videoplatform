# Announcement System – Design Spec

**Date:** 2026-05-20
**Status:** Draft (awaiting review)
**Author:** Justus Weweler (mit Claude)
**Target release:** V1 (sofort-Senden) + V2 (Scheduler) als zwei separate PRs

---

## 1. Goal

Nora soll ihren Teilnehmerinnen mit einem Klick mitteilen können, dass neue Inhalte auf der Plattform verfügbar sind – auf zwei Granularitätsebenen:

- **Modul-Ebene:** „Modul 4 ist jetzt verfügbar"
- **Lektions-Ebene:** „Neue Lektion in Modul 4: Hormonelles Gleichgewicht"

Ziel: Engagement hochhalten, Klientinnen zurück zur Plattform holen.

## 2. Constraints (NICHT verhandelbar)

- **Live-Betrieb:** Plattform läuft produktiv mit zahlenden Teilnehmerinnen. Erste paying Cohort ist seit 2026-04-27 aktiv.
- **Keine Breaking Changes:** Migrationen sind ausschließlich additiv (neue Tabelle, keine Spaltenänderungen an bestehenden Tabellen). Keine bestehende API darf in Signatur oder Verhalten geändert werden. Keine bestehende UI-Route darf verschwinden.
- **Rückwärtskompatibel:** Falls Deployment fehlschlägt oder zurückgerollt werden muss, darf die Plattform weiterhin funktionieren – nur die neuen Features sind dann inaktiv.

## 3. Non-Goals (V1)

Explizit ausgeschlossen aus V1, kommen ggf. später:

- Zeitgesteuertes Senden (Scheduler) → V2
- Rich-Text-Editor / WYSIWYG → V1 nutzt einfache Textareas mit Auto-Vorschlag
- Open-/Click-Tracking → V1 nur Versand-Bestätigung
- Push-Notifications oder In-App-Notifications → nur E-Mail in V1
- Auto-Trigger beim Video-Upload oder Lektion-Publish → V2 Soft-Toast
- Mehrsprachigkeit der Templates → V1 deutsch only
- Ankündigung an einzelne Teilnehmerinnen (Filtering) → V1 sendet an alle aktiv Enrolled

## 4. Datenmodell (additiv)

### Neue Tabelle: `announcements`

```
announcements
├── id                  TEXT PRIMARY KEY (UUID)
├── course_id           TEXT NOT NULL  → FK courses(id) ON DELETE CASCADE
├── target_type         TEXT NOT NULL  → CHECK IN ('module', 'lesson')
├── target_id           TEXT NOT NULL  → FK ist nicht hart erzwungen (target_type entscheidet,
│                                       worauf es zeigt – wir prüfen in Application-Layer)
├── subject             TEXT NOT NULL
├── body                TEXT NOT NULL
├── recipient_count     INTEGER NOT NULL DEFAULT 0  (Snapshot beim Versand)
├── created_by_user_id  TEXT NOT NULL  → FK users(id)
├── sent_at             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
└── created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP

INDEX idx_announcements_course_id ON announcements(course_id, sent_at DESC)
```

**Wichtig:** Keine `ON DELETE CASCADE` von `modules`/`lessons` auf `announcements`, da `target_id` zur Audit-History bestehen bleibt, auch wenn Modul/Lektion später gelöscht wird. Beim Rendern fangen wir „Target gelöscht"-Fall ab.

**V2 wird ergänzen** (Vorschau, NICHT Teil von V1):
- `scheduled_at TIMESTAMP NULL` – falls gesetzt: noch nicht versendet
- `status TEXT DEFAULT 'sent'` – „scheduled" | „sent" | „cancelled"

V1 implementiert das Schema **so**, dass V2 die zwei Spalten additiv ergänzen kann – keine Refactor-Migration nötig.

## 5. Backend-API (alle Endpoints neu, additiv)

Alle Endpoints unterhalb `/api/admin/courses/{course_id}/announcements`. Auth: Admin-Rolle (gleicher Guard wie bestehende Admin-Endpoints).

### `POST /api/admin/courses/{course_id}/announcements`
Erstellt Announcement und sendet sofort.

**Request body:**
```json
{
  "target_type": "module" | "lesson",
  "target_id": "<id>",
  "subject": "string",
  "body": "string"
}
```

**Validierung:**
- `target_id` muss zu `course_id` gehören (Modul gehört zum Kurs, Lektion gehört zu Modul/Section in diesem Kurs)
- `subject` 1–200 Zeichen
- `body` 1–5000 Zeichen
- Mindestens 1 aktive Enrollment muss vorhanden sein (sonst 422 mit klarer Fehlermeldung)

**Verhalten:**
1. Empfänger-Liste ermitteln (alle `Enrollment` mit aktivem Status für `course_id`)
2. `Announcement` Row erstellen mit `recipient_count = N`
3. Synchron versuchen, alle E-Mails zu versenden via bestehendes `app/core/email.py`
4. Antwort: 201 mit dem erzeugten Announcement-Objekt + `delivery_summary` (sent, failed)

**Fehler-Handling:** Wenn einzelne E-Mails fehlschlagen, wird der Versand als „partial" markiert in der Response, aber das Announcement bleibt persistent. Nora sieht das in der Liste.

**Performance-Note:** Aktuelle Kohorten sind klein (<100). Synchroner Versand ist okay. Wird in V2 ggf. asynchron via Background-Job, falls Listen wachsen.

### `GET /api/admin/courses/{course_id}/announcements`
Liste der bisherigen Announcements, neueste zuerst. Paginierung nicht in V1 (Listen sind klein).

**Response (Beispiel):**
```json
{
  "announcements": [
    {
      "id": "...",
      "target_type": "lesson",
      "target_id": "...",
      "target_title": "Hormonelles Gleichgewicht",
      "target_module_title": "Modul 4",
      "subject": "Neue Lektion in Modul 4",
      "body": "...",
      "recipient_count": 47,
      "sent_at": "2026-05-20T18:00:00Z",
      "created_by": { "id": "...", "name": "Nora" }
    }
  ]
}
```

`target_title` und `target_module_title` werden im Backend angereichert – falls Target gelöscht wurde: `target_title = null`, Frontend zeigt „(gelöscht)".

### `GET /api/admin/courses/{course_id}/announcements/preview`
Erzeugt Vorschlag für Subject + Body basierend auf Target.

**Query-Params:** `target_type`, `target_id`

**Response:**
```json
{
  "suggested_subject": "Neue Lektion in Modul 4: Hormonelles Gleichgewicht",
  "suggested_body": "Hallo,\n\nin deinem Kurs ist eine neue Lektion verfügbar: …",
  "recipient_count": 47,
  "target_title": "Hormonelles Gleichgewicht",
  "target_module_title": "Modul 4"
}
```

Wird vom Compose-Modal aufgerufen, wenn Nora ein Target auswählt.

## 6. E-Mail-Versand

**Wiederverwendung:** `app/core/email.py` hat schon `_wrap_in_brand_template`, `_cta_button`, `_send_smtp` und Beispiele wie `send_module_unlocked_email`. Wir bauen `send_announcement_email` analog.

**Funktion (neu):**
```python
def send_announcement_email(
    to_email: str,
    to_name: str,
    subject: str,
    body_text: str,
    cta_url: str,
    unsubscribe_url: str | None = None,
) -> bool
```

- `body_text` ist der Plain-Text von Nora, wird im HTML-Template in `<p>`-Absätze gesplittet
- `cta_url` führt direkt zum Modul oder zur Lektion in der Plattform (`https://kurse.noraweweler.de/...`)
- **CTA-Label ist fest „Jetzt ansehen"** für Modul- und Lektions-Ankündigungen. Keine Variante in V1.
- Plain-Text-Fallback wird automatisch generiert

**Template-Vorschau:** Analog zu `preview-drip-email.html` ergänzen wir ein `preview-announcement-email.html` für lokales Design-Review.

## 7. Frontend

### 7.1 Hub-Seite (neu): `/admin/courses/<id>/announcements`

**Komponenten:**
- Header: „Ankündigungen für [Kursname]"
- Primary Button: „Neue Ankündigung" → öffnet Compose-Modal
- Liste-Tabelle:
  - Datum (relativ: „vor 2 Tagen")
  - Ziel: Modul- oder Lektions-Titel + Kontext („Modul 4 / Lektion: …")
  - Subject (erste Zeile)
  - Empfängerzahl
  - Status-Pill (Sent / Partial / Failed)
- Leerstand: „Noch keine Ankündigungen verschickt."

### 7.2 Compose-Modal (gleicher Code, drei Einstiege)

**Felder:**
1. **Ziel-Picker:** Dropdown mit Modulen, aufklappbar zu Lektionen. Eine Auswahl. Vorausgewählt, wenn aus kontextuellem Shortcut geöffnet.
2. **Subject:** Textfield mit Auto-Vorschlag (aus `/preview`-Endpoint). Editierbar.
3. **Body:** Textarea (~8 Zeilen) mit Auto-Vorschlag. Editierbar.
4. **Empfänger-Hinweis:** „Wird an N Teilnehmerinnen gesendet." (live aus `/preview`)
5. **Vorschau-Button:** Öffnet kleinen Preview-Tab/Iframe mit gerenderter Mail-HTML.
6. **Primary:** „Jetzt senden" – Loading-Spinner während Versand, Toast bei Erfolg, Liste refreshed.

### 7.3 Drei Einstiege zum Modal

| Einstieg | Wo | Pre-Selection |
|---|---|---|
| Hub-Seite Button | `/admin/courses/<id>/announcements` | Kein Target ausgewählt |
| Modul-Edit-Shortcut | Header der Modul-Edit-Seite | `target_type=module, target_id=<id>` |
| Lektions-Edit-Shortcut | Header der Lektions-Edit-Seite | `target_type=lesson, target_id=<id>` |

**Visuell:** Die zwei Shortcuts sind dezent (Icon + Text), rechts im Header neben den anderen Aktionen, nicht primary. Sie ändern nichts an bestehenden Aktionen – sie kommen daneben.

### 7.4 Navigation
- **Pro Kurs** ein Sidebar-Link „Ankündigungen" in der Kurs-Admin-Sektion, zwischen „Inhalte" und „Teilnehmerinnen" (oder analog zur bestehenden Sortierung des Kurs-Admin-Menüs).
- Kein globaler „Ankündigungen"-Hub über alle Kurse hinweg in V1.

## 8. Live-Betrieb-Strategie

### 8.1 Migration

Nur eine additive Migration:
```sql
CREATE TABLE announcements (...);
CREATE INDEX idx_announcements_course_id ON announcements(course_id, sent_at DESC);
```
Idempotent (z. B. `CREATE TABLE IF NOT EXISTS`). Kein Down-Migrations-Risk.

### 8.2 Deployment-Reihenfolge

1. **PR 1 (V1, Backend-First):**
   - Migration
   - Backend-Endpoints + Email-Funktion
   - Frontend-Komponenten
   - Deployen via bestehende GitHub-Actions-Pipeline
2. **Rollback-Plan:** Falls Probleme auftreten, Revert-Commit + Redeploy. Tabelle `announcements` bleibt liegen (kein Schaden). Keine Datenkorruption möglich, da nur additiv.

### 8.3 Feature-Sichtbarkeit
- Sidebar-Link sofort sichtbar nach Deploy.
- **Kein ENV-Flag-Gating.** Die Migration ist additiv, die UI lebt neben bestehenden Flows, Rollback per Revert + Redeploy ist sicher. Ein Flag würde Komplexität für ein Risiko addieren, das durch die Architektur schon ausgeschlossen ist.

### 8.4 Was *nicht* angefasst wird
- `Enrollment`, `Module`, `Lesson`, `Section`, `Course` Modelle: unverändert
- `email.py`: nur neue Funktion `send_announcement_email`, keine bestehenden Funktionen angepasst
- Bestehende Drip-Notification-Mechanik: unangetastet
- Auth-Layer: unverändert, neue Endpoints nutzen bestehenden Admin-Guard

## 9. Tests

- **Unit:** Validierung (Target gehört zum Kurs, Subject/Body-Längen, leere Enrollment-Liste)
- **Integration:** POST erstellt Row, ruft Email-Funktion mit korrekten Argumenten auf, GET liefert Liste
- **Email-Funktion:** Mock SMTP, prüfe Template-Rendering und Plain-Text-Fallback
- **E2E (manuell vor Release):** Echtes Modul + echte Lektion in Staging, an Test-Empfänger senden, Empfang prüfen, CTA-Link prüfen
- Bestehende Test-Suite muss weiterhin grün sein (keine Regressionen).

## 10. V2 Ausblick (separater PR, später)

- **Scheduler:** `scheduled_at` Spalte, Background-Worker (analog `drip_notifier_loop`), „Geplant"-Status in Liste
- **Soft-Guard:** Beim Compose Warnung „Du hast Ziel X vor N Tagen schon angekündigt" (Backend liefert `last_announcement_for_target`)
- **Last-Sent-Badge:** In Modul-/Lektions-Listen kleines „📨 vor 5 Tagen" Indikator
- **Post-Publish-Toast:** Wenn Nora eine Lektion auf published stellt, kleiner nicht-blockierender Hinweis mit „Ankündigen"-Link
- **Tracking (optional, nur wenn echter Bedarf entsteht):** Open- und Click-Tracking via 1×1-Pixel + Redirect-Endpoint

## 11. Getroffene Entscheidungen (2026-05-20)

1. **Sidebar-Link „Ankündigungen" pro Kurs** – integriert in Kurs-Admin-Sidebar, kein globaler Hub in V1.
2. **CTA-Label fix „Jetzt ansehen"** – einheitlich für Modul- und Lektions-Ankündigungen, keine Variante in V1.
3. **Kein ENV-Flag** – Architektur ist additiv, Rollback per Revert reicht aus.
