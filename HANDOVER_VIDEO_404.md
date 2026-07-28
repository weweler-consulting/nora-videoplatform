# Übergabe: Videos zeigen 404 / „kein Video vorhanden"

## Ziel dieser Sitzung
Das eigentliche Problem fixen: **Teilnehmerinnen können Kurs-Videos nicht mehr
öffnen** — sie sehen entweder eine **404-Fehlermeldung** oder den Hinweis
**„Kein Video vorhanden"**.

## Ausgangslage / Kundenmeldung
- Kundin (Uta, `UB-Boehm@t-online.de`) meldet für den **Frühstückskurs**:
  „ich kann die Videos … nicht (mehr) öffnen, bekomme entweder die Fehlermeldung
  404 oder den Hinweis kein Video vorhanden." Sie konnte die Videos früher
  einmal ansehen.
- Das deutet auf ein **Daten-/Bunny-Problem** hin (Video war da, ist jetzt weg),
  nicht auf einen generischen Code-Bug — bitte zuerst reproduzieren, nicht raten.

## Was in der letzten Sitzung schon gebaut wurde (Debug-Werkzeug)
Feature **„Einloggen aus Kundensicht"** (Impersonation) ist fertig, gemerged auf
`main` und deployed. Damit lässt sich dieses Problem **aus Utas Sicht**
reproduzieren:
- Admin → **Nutzer verwalten** → Teilnehmerin öffnen → Button
  **„Aus Kundensicht einloggen"**. Gelber Banner + „Zurück zu Admin".
- Backend: `POST /users/{id}/impersonate` (Commit `47947b8`, Merge `e53e89b`).

**Erster Schritt der neuen Sitzung:** als Uta einloggen, den Frühstückskurs
öffnen, die betroffene Lektion aufrufen und schauen, welcher der beiden Fälle
eintritt.

## Die zwei Fehlerbilder — exakt im Code verortet

Der Video-Player lebt in `frontend/src/pages/LessonView.tsx` (ab Zeile 199):

```tsx
{currentLesson.video_url ? (
  <iframe src={withPlayerParams(currentLesson.video_url)} ... />
) : (
  <div ...>Kein Video vorhanden</div>   // Zeile 210–213
)}
```

1. **„Kein Video vorhanden"** → `lesson.video_url` ist in der DB **leer/null**.
   Das Video wurde nie hinterlegt oder wieder entfernt. → DB-Problem an der
   Lektion.
2. **404** → `video_url` ist gesetzt und zeigt auf
   `https://iframe.mediadelivery.net/embed/{libraryId}/{videoId}`, aber das
   **Bunny-Video existiert dort nicht (mehr)** (gelöscht, falsche `libraryId`,
   oder `videoId`/guid stimmt nicht). Bunny liefert dann 404 **innerhalb** des
   iframes. → Bunny-/URL-Problem.

## Stärkste Hypothese für den 404
In `app/api/upload.py` (`delete_video`) und
`app/integrations/bunny_stream.py` (`delete_video_by_embed_url`) wird beim
Entfernen eines Videos aus einer Lektion **das Bunny-Video gelöscht**
(siehe ROADMAP: „Video-Löschung bei Bunny.net beim Entfernen aus Lektion").

Verdacht: Ein Bunny-Video wurde gelöscht (Lektion bearbeitet, Video getauscht,
oder versehentlich), **aber die alte `embed_url` steht noch an der Lektion** —
oder dieselbe Bunny-Video-guid wurde an mehreren Lektionen referenziert und ist
jetzt nur noch an einer gültig. Ergebnis: 404 im Player.

## Konkrete erste Schritte
1. **Reproduzieren** per Impersonation (s. o.). Notieren: 404 **oder** „kein
   Video"? Bei welcher Lektion?
2. **DB prüfen** — `video_url` der betroffenen Lektionen im Frühstückskurs
   ansehen: leer (Fall 1) oder gesetzt (Fall 2)? Tabelle `lessons`, Spalte
   `video_url`. Beispiel-Query:
   `SELECT l.id, l.title, l.video_url FROM lessons l ... WHERE course = Frühstückskurs`
   (join über sections → modules → courses).
3. **Bei gesetzter URL (Fall 2):** guid + libraryId aus der URL ziehen und gegen
   die Bunny-Library prüfen:
   `GET https://video.bunnycdn.com/library/{libraryId}/videos/{videoId}`
   mit Header `AccessKey: $BUNNY_API_KEY`. 404 ⇒ Video existiert bei Bunny nicht
   mehr. 200 ⇒ Video ist da, dann Player-/Host-/Token-Problem weiter untersuchen
   (Bunny „Token Authentication" / erlaubte Referrer-Domains der Library?).
4. **libraryId gegenprüfen:** Stimmt die `libraryId` in der gespeicherten URL mit
   der aktiven `BUNNY_LIBRARY_ID` überein? Ein Library-Wechsel würde alte URLs
   flächendeckend brechen.

## Wichtige Dateien & Endpunkte
- `frontend/src/pages/LessonView.tsx` — Player, `withPlayerParams()`,
  „Kein Video vorhanden"-Fallback.
- `app/api/upload.py` — `create-video` (embed_url-Format), `delete-video`.
- `app/integrations/bunny_stream.py` — Server-Upload + `delete_video_by_embed_url`.
- `app/api/lessons.py` — Lesson-CRUD (wo `video_url` gesetzt/gelöscht wird — hier
  prüfen, ob beim Update die alte URL/das Bunny-Video sauber behandelt wird).
- `app/api/courses.py` — was die Kundin an Lektionen/`video_url` überhaupt
  ausgeliefert bekommt (Published-/Drip-Filter).
- Modelle: `app/models/course.py` (`Lesson.video_url`).

## Konfiguration / Secrets (nötig zum Prüfen)
- `BUNNY_API_KEY`, `BUNNY_LIBRARY_ID` (Env). Ohne die kann man die Bunny-Library
  nicht abfragen. **Keine Secrets in Commits/PRs.**
- Deploy: Push auf `main` triggert GitHub Actions (`.github/workflows/deploy.yml`).

## Embed-URL-Format (Referenz)
`https://iframe.mediadelivery.net/embed/{libraryId}/{videoId}`
`withPlayerParams()` ersetzt `player.mediadelivery.net` → `iframe.mediadelivery.net`
und hängt `playsinline=true&preload=true&responsive=true` an.

## Offene Fragen für die neue Sitzung
- Betrifft es **alle** Videos des Frühstückskurses oder nur einzelne Lektionen?
  (alle ⇒ Library-/Config-weit; einzelne ⇒ gelöschte/getauschte Videos)
- Sehen **andere** Teilnehmerinnen dieselben Videos ebenfalls als 404, oder ist
  es Uta-spezifisch? (via Impersonation eines zweiten Users gegenprüfen —
  grenzt Daten- vs. Zugriffsproblem ein)
- Hat Bunny „Token Authentication" oder eine Referrer-Whitelist aktiv, die die
  Produktionsdomain (noch) nicht enthält?
- Wurde die Bunny-Library kürzlich gewechselt oder aufgeräumt (gelöschte Videos)?
