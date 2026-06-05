# Live-Call-Benennung (Nomenklatur) — damit der Auto-Import den richtigen Kurs trifft

**Warum das wichtig ist:** Der Titel der **Google-Kalender-Serie** wird zum **Meet-Titel**
und damit zum **Namen der Recording-Datei** in Google Drive. Der Live-Call-Auto-Import erkennt
ein Recording über genau diesen Namen und ordnet es dem Kurs zu. Stimmt die Benennung nicht,
landet die Aufzeichnung **im falschen Kurs oder gar nicht**.

---

## Für Nora (beim Anlegen der Kalender-Serie) — die einfache Regel

Benenne die wiederkehrende Live-Call-Serie im Kalender so, dass **klar ist, zu welchem Kurs sie
gehört**, und halte den Namen **pro Kurs eindeutig und stabil**:

- **4-Wochen Glukose Balance Code (läuft durchgehend):**
  → `4-Wochen Glukose Balance Code Live Call`

- **Gruppencoaching (startet quartalsweise, jede Kohorte ist ein eigener Kurs):**
  → `Glukose Balance Live Call (STARTMONAT JAHR)`
  z.B. `Glukose Balance Live Call (September 2026)`
  **Der Monat in Klammern = der Startmonat der Gruppe.** Er bleibt für ALLE Calls dieser Gruppe
  gleich (auch wenn ein einzelner Call im Oktober liegt) — nur das Datum dahinter wechselt
  automatisch.

**Wichtig:**
- Nutze einfache Bindestriche „-", keine Sonderstriche („–"), und keine Tippfehler.
- Jede neue Gruppe/Quartal = ein **neuer, eindeutiger** Serien-Name (neuer Startmonat).

---

## Für die Einrichtung (Justus / Admin)

**Mapping anlegen** (einmal pro Kurs/Kohorte): im Admin den Recording-Prefix mit dem Kurs
verknüpfen. Der Prefix ist **alles vor dem Datum** im Recording-Namen, z.B.
`Glukose Balance Live Call (September 2026)`.

→ **Nicht abtippen:** Die Funktion „Prefix vorschlagen" listet die echten Drive-Recording-Namen
zum Anklicken (vermeidet Tippfehler / Strich-Abweichungen). API: `GET /api/v1/live-calls/suggest-prefixes`.

**Regeln fürs Mapping:**
- 1 Prefix → 1 Kurs (eindeutig).
- Prefixe dürfen sich nicht überlappen (kein Prefix ist Anfang eines anderen).
- Neue Quartals-Kohorte des Gruppencoachings: neuen Kurs anlegen → neue Serie benennen
  (`… (Dezember 2026)`) → neues Mapping. Die alten Recordings bleiben (Dedup), kommen nicht zurück.

**Was die Recording-Dateien tatsächlich heißen (zur Kontrolle):**
Google legt sie als `<Serien-Titel> - YYYY/MM/DD HH:MM <TZ> - Recording` (Video, mp4) im Ordner
„Meet Recordings" ab. Beispiel real:
`Live Call | Glukose Balance - 2026/06/04 19:14 WEST - Recording`. Die getrennten 1:1-Calls
(`… Coaching - Name x Nora …`, `Beratungsgespräch …`) werden durch den Prefix automatisch
ausgeschlossen.

---

## TODO (späterer Komfort)
Die Admin-UI fürs Mapping soll diese Nomenklatur-Regel direkt anzeigen (Inline-Hinweis +
Prefix-Vorschlag-Buttons), damit niemand hier nachschlagen muss.

Referenz-Design: `docs/superpowers/specs/2026-06-05-live-call-auto-import-design.md`.
