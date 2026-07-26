# Go-Live: 4-Wochen Glukose Balance Code — Start August 2026

**Stand:** 2026-07-26, 20:10 WEST · **Launch geplant:** 2026-07-27
**Modus:** rollierend (Drip-Anker = `enrolled_at`, kein fixer Kohortenstart)

Betroffene Repos: `nora-videoplatform` (Kursplattform), `nora-crm`, `nora-website` (Sales Page).

---

## Grundentscheidung: Stripe-Produkt wird wiederverwendet

`prod_UbweNqpMeE7azJ` (Bundle: 4-Wochen-Kurs + Frühstücks-Code) bleibt bestehen.
Payment Link: `https://book.stripe.com/5kQaEW5OO6p79vp7d10Ny04`

**Warum das die richtige Wahl war:** Ein neues Stripe-Produkt hätte drei zusätzliche,
jeweils still fehlschlagende Handgriffe erzwungen:
1. `product_course_map`-Zeile für den Frühstücks-Code — **es gibt keine Admin-UI dafür**,
   nur der hardcodierte Seed `_seed_bundle_mappings()` in `app/main.py:118-165` oder manuelles SQL.
2. Neues CRM-Produkt anlegen **und danach erneut öffnen**, um `stripeProductId` nachzutragen
   (das Anlege-Formular hat das Feld nicht — `ProductCreate.tsx` vs. `ProductEdit.tsx:275-287`).
3. `runsAsCohort=true` per SQL — in keiner UI pflegbar.

Durch die Wiederverwendung entfallen alle drei.

---

## Block 0 — Vorab-Checks

- [x] **Resend-Kontingent** — Paid Plan, ~7.900 Mails unkritisch
- [x] **CRM-Prod-Stand** — Tag-Feature ist live (PR #26 + #27, gemerged 2026-07-21, `ffa4253`)
- [x] **Stripe `success_url`** — verifiziert 2026-07-26:
      `https://noraweweler.de/kurse/glukose-balance-code/danke/?session_id={CHECKOUT_SESSION_ID}`

Die Danke-Seite liest `session_id` (Fallback `checkout_session_id`), verwirft einen nicht
ersetzten Platzhalter über `indexOf('{') === -1` und dedupliziert per `sessionStorage`
(`public/kurse/glukose-balance-code/danke/index.html:299-312`). Passt.

- [ ] **Preis gegenprüfen:** `value: 395.00` ist in der Danke-Seite hart codiert
      (Z. 316 und 322, zusätzlich Sales Page Z. 1849/1953).

> Weicht der August-Preis von 395 € ab, meldet das Tracking dauerhaft einen falschen
> Umsatzwert an GA4/Meta, während Stripe korrekt bucht. Nichts bricht — fällt erst beim
> Monatsabgleich auf.

---

## Block 1 — Kursplattform (`kurse.noraweweler.de`)

Kurs: **„4-Wochen Glukose Balance Code (Start August 2026)"**
`https://kurse.noraweweler.de/admin/course/e8f9c580-f86b-4964-824e-52017919088c`

- [x] Kurs angelegt
- [x] `stripe_product_id = prod_UbweNqpMeE7azJ` eingetragen
- [x] Check-in-Module eingetragen (inkl. **Abschluss-Check-in** — treibt den Premium-Upsell)
- [x] Modulgerüst 1–4 angelegt (Stand 20:36: alle **0 Lektionen**)
- [ ] **Inhalte Woche 1 füllen** (Entscheidung Justus: heute Nacht, Rest per Drip)
- [ ] `unlock_after_days` pro Modul setzen — **noch unbestätigt**

### Struktur (Stand 2026-07-26, 20:36)

```
 1  Check-in: Bestandsaufnahme   (Start)
 2  Check-in Woche 1             (laufend)
 3  Modul 1 – Einführung
 4  Check-in Woche 2             (laufend)
 5  Modul 2
 6  Check-in Woche 3             (laufend)
 7  Modul 3
 8  Check-in Woche 4             (laufend)
 9  Modul 4
10  Abschluss-Check-in           (Abschluss)
```

**Offene Frage:** Check-in steht jeweils **vor** dem zugehörigen Modul. Sinnvoll, wenn es
Wochen-*Start*-Formulare sind; eine Position zu früh, wenn es Rückschauen auf die Woche sind.
Die Sortierung ist rein kosmetisch — terminiert wird nur über `unlock_after_days`. Weichen
beide voneinander ab, sieht die Kundin ein gesperrtes Element über einem offenen.

### ⚠️ Verbindliche Deadlines durch Plan A

Module 2–4 existieren jetzt mit 0 Lektionen. Der Drip-Notifier wählt Module **allein** über
`unlock_after_days > 0` (`app/core/drip_notifier.py:38-42`) — **kein Lektions-Check**. Ein leeres
Modul löst die Mail „Modul freigeschaltet" trotzdem aus. Und der Versand schreibt eine
`DripNotification`-Zeile pro `(user, module)`: wird das Modul später gefüllt, geht **keine
zweite Mail** raus. Die Ankündigung ist dann verbrannt; Rettung nur manuell per Announcement.

Anker ist `enrolled_at` pro Käuferin — die **erste** Käuferin setzt die früheste Frist:

| Modul | `unlock_after_days` | Muss gefüllt sein bis (erste Käuferin 27.07.) |
|---|---|---|
| Modul 2 | 7 | **03.08.** |
| Modul 3 | 14 | **10.08.** |
| Modul 4 | 21 | **17.08.** |
- [ ] Live-Call-Serie mappen (siehe unten)
- [ ] Hub / Mitgliederbereich befüllt?

### ⚠️ „Start August" existiert im System nicht

Der Drip-Anker ist `enrolled_at` (`app/api/courses.py:53-62`), nicht ein Kohortendatum.
Es gibt **kein `start_date`-Feld**. Wer morgen kauft, schaltet Modul 1 mit
`unlock_after_days = 0` **sofort** frei — nicht im August.

Zwei saubere Optionen:
- **A (empfohlen):** Woche-1-Inhalte vor dem ersten Verkauf fertig haben und
  Sofortzugang als Vorteil kommunizieren („du kannst direkt loslegen").
- **B:** `unlock_after_days` von Modul 1 auf den Abstand bis zum Wunschstart setzen.
  Wirkt aber **pro Käuferin relativ**, nicht absolut — wer später kauft, startet
  entsprechend später. Ein echter Fixstart ist damit nicht abbildbar.

### ⚠️ Check-in-Module sind ab Tag 1 alle sichtbar

`create_checkin_module` (`app/api/checkin.py:117`) setzt `unlock_after_days` nicht → Default 0.
Alle Wochen-Check-ins sind sofort offen und ausfüllbar. Pro Check-in-Modul manuell
`unlock_after_days` nachziehen (7 / 14 / 21 / 28).

### ⚠️ Check-in-Texte nur per Lektions-Override ändern

Die Templates (`start` / `laufend` / `ende`) sind **global**, nicht pro Kurs
(`CheckinTemplate` in `app/models/checkin.py:12-27` hat keine `course_id`).
Im Start-Template steht hart **„Wir starten am 8. Juni"** (`app/core/checkin_seed.py:60-61`),
dazu „4 Wochen"-Formulierungen in `:35` und `:105-135`.

→ Änderungen **ausschließlich** über `AdminCheckinDetail` als Lektions-Override.
Wer das Template selbst editiert, ändert es rückwirkend für jeden anderen Kurs.

### Live-Call-Serie (Stand 2026-07-26)

Nora hat die Kalender-Serie angelegt: **ab Dienstag 04.08.2026, wöchentlich**.
Aktueller Titel: `Live Call "4 Wochen Glukose Balance Code" (Start Aug 2026)`

- [ ] **Anführungszeichen aus dem Serientitel entfernen** — mit „**Alle Termine**", vor dem 04.08.
- [ ] Mapping im Admin setzen — bevorzugt per „Prefix vorschlagen" am 04.08.
- [ ] Nach dem ersten Call aktiv in Admin → Live-Calls nachsehen

**Neuer Titel (Umbenennung mit Justus abgestimmt, 2026-07-26):**
```
Live Call 4 Wochen Glukose Balance Code (Start Aug 2026)
```

> ⚠️ Beim Umbenennen einer Kalender-Serie fragt Google „Diesen Termin" vs. „Alle Termine".
> Es muss **„Alle Termine"** sein. Sonst behalten die Calls ab dem 11.08. den alten Titel
> und ab Woche 2 kommt nichts mehr an — während Call 1 sauber durchläuft und alles
> funktionierend aussieht.

**Warum:** Der Kalendertitel wird zum Meet-Titel und damit zum Drive-Dateinamen
(`<Serientitel> - YYYY/MM/DD [HH:MM TZ] - Recording`). Der Präfix ist alles vor dem Datum,
geprüft mit `name.startswith(prefix)` — **zeichengenau** (`live_call_parser.py:33-35`).
Typografische Anführungszeichen („…" / "…"), wie sie macOS beim Tippen automatisch setzt,
sind von `"` optisch kaum zu unterscheiden, aber andere Bytes. Ein falsches Zeichen im
Präfix → `startswith` matcht nie → **völlig lautloser Ausfall**: kein Log, kein Fehler,
keine Mail, die Aufzeichnung kommt nie im Kurs an.

Der Titel ohne Anführungszeichen überschneidet sich nicht mit der alten Serie
`Live Call | Glukose Balance` (Zeichen 11: `4` vs. `|`). Überlappungsfreiheit ist Pflicht.

**Sicherheitsnetz:** `LOOKBACK_DAYS = 21` (`live_call_detector.py:18`) — ein Mapping, das
erst *nach* der ersten Aufzeichnung angelegt wird, zieht sie noch nach. Der sicherere Weg
ist deshalb: am 04.08. nach dem Call „Prefix vorschlagen" nutzen, der die **echten**
Drive-Dateinamen zum Anklicken listet (`GET /api/v1/live-calls/suggest-prefixes`).
Doku-Regel: **nicht abtippen** (`docs/live-call-naming.md`).

> ⚠️ Der organische Pfad Detector → Import → Freigabe-Mail ist in Prod **noch nie komplett
> durchgelaufen**. Der 04.08. ist die erste echte Feuerprobe — nach dem Call aktiv in
> Admin → Live-Calls nachsehen, statt auf die Benachrichtigung zu warten.

### Was ist das Live-Call-Mapping?

Der Auto-Import holt Google-Meet-Aufzeichnungen aus Drive und legt sie automatisch
als versteckte Lektion im Kurs an — Nora bekommt eine Freigabe-Mail mit 1-Klick-Button.

Verknüpft wird über einen **Namens-Präfix**: `LiveCallSeries` (`recording_name_prefix` → `course_id`).
Der Präfix ist der Teil des Recording-Namens **vor dem Datum**, z.B. `Live Call | Glukose Balance`.
Einzurichten im Admin unter dem Kurs; die UI schlägt Präfixe aus echten Drive-Dateinamen vor.

**Ohne Mapping passiert gar nichts** — der Detector iteriert nur über existierende Serien.
Kein Log, kein Fehler, keine Mail. Reiner stiller Ausfall.

Voraussetzung: die Kalender-Serie muss **vor dem ersten Call** korrekt benannt sein,
sonst greift der Präfix nicht. Nur relevant, wenn zum Programm Live-Calls gehören.

---

## Block 2 — CRM (`crm.noraweweler.de`)

- [x] Gruppe **„4 Wochen Glukose Balance Code Start Aug 2026"** angelegt, Status `geplant`
- [ ] **Gegencheck offen** (siehe unten)

`planned` reicht für die Auto-Zuweisung — `resolveCurrentCohort`
(`src/lib/coaching-groups/auto-assign.ts:21-26`) akzeptiert `planned` **und** `active`.

**Regel: immer genau EINE offene Gruppe pro Produkt.** Bei null oder mehreren greift
die Auto-Zuweisung nicht; der Kauf bleibt unzugewiesen und erzeugt eine Glocke
„⚠️ Kauf braucht manuelle Kohorten-Zuweisung". Nichts geht verloren, aber es wird Handarbeit.

### Offener Gegencheck (Punkt 10) — read-only

Zu prüfen: Hängt die neue Gruppe am richtigen Produkt, und hat dieses Produkt
`stripeProductId` + `runsAsCohort=true`? Sonst kein Auto-Assign.

```bash
cloudron login
cloudron exec --app crm.noraweweler.de -- bash -c 'cd /app && NODE_PATH=/app/node_modules node scripts/sql.js "SELECT g.id, g.name, g.status, p.id AS product, p.\"stripeProductId\", p.\"runsAsCohort\" FROM \"CoachingGroup\" g JOIN \"Product\" p ON p.id=g.\"productId\" WHERE g.\"deletedAt\" IS NULL"'
```

**Erwartung:** genau eine Zeile mit Status `planned` oder `active`,
`stripeProductId = prod_UbweNqpMeE7azJ`, `runsAsCohort = true`.
Die alte Juni-Gruppe muss auf `completed` stehen (bereits erledigt).

> Bekannte Falle: Gruppen für „4 Wochen" hingen früher am 1980-€-Produkt
> `prod-gruppen-coaching` statt am digitalen `prod-4-wochen-kurs`. Dann zeigt das
> Zuweis-Modal die falschen Käuferinnen. Der Gegencheck oben deckt das mit ab.

---

## Block 3 — Testkauf (nicht überspringen)

- [ ] 100 %-Coupon-Testkauf über den echten Payment Link

Muss **alles** davon zeigen:
1. Enrollment in **beide** Kurse (4-Wochen **und** Frühstücks-Code)
2. Invite-Mail kommt an
3. `/accept-invite` → Passwort setzen funktioniert
4. Kurs ist danach sichtbar
5. CRM: Kontakt + Purchase + **Kohortenzuweisung** entstanden
6. Danke-Seite feuert das Purchase-Event (`session_id` in der URL)

> Punkt 1 ist der wichtigste: das Bundle-Mapping war schon einmal still leer
> (Seed-Bug auf Postgres, `AmbiguousParameterError`). Nur ein echter Kauf beweist, dass es greift.

---

## Block 3b — Kauf- und Einladungs-Mails (geprüft 2026-07-26)

Quelle: `app/core/email.py`. Betreff bei Neukundin (Bundle-Label aus
`stripe_webhook.py:55-64`):
`Dein Zugang zum 4-Wochen Glukose Balance Code (Start August 2026) inkl. Frühstücks-Code ist da`

- [ ] 🔴 **Widerrufs-Verzicht im Stripe-Checkout prüfen**
- [ ] Ablauf-Hinweis (Start, erster Live-Call) in die Mail aufnehmen
- [ ] Kurstitel kundentauglich machen
- [ ] Satz „Falls du diese Einladung nicht erwartet hast…" für Käufe entfernen
- [ ] PNG-Fallback fürs Logo
- [ ] Stripe-Belege im Live-Mode aktiv?

**🔴 Widerrufs-Verzicht.** `_widerruf_text()` (`email.py:149-154`) formuliert korrekt, dass das
Widerrufsrecht bei digitalen Inhalten nur erlischt, wenn die Kundin **ausdrücklich zugestimmt
und den Rechtsverlust bestätigt** hat. Wird das im Payment Link nicht als Pflichtfeld
eingeholt, gilt 14 Tage volles Widerrufsrecht → halber Kurs konsumierbar, volle Erstattung.
Bei 495 € der einzige Punkt der Mail-Kette mit direktem Geldbezug.

Positiv: Belehrung liegt im Mail-Volltext (ein Link genügt §312f nicht), Verkäuferanschrift
vollständig, Muster-Widerrufsformular vorhanden.

**Kohorten-Marker im Betreff.** „(Start August 2026)" ist eine Admin-Notiz und steht wörtlich
in Betreff und Text. Betreff = 89 Zeichen, mobil nach ~40 abgeschnitten → der Bundle-Vorteil
ist unsichtbar. Bei rollierendem Verkauf sieht eine September-Käuferin „Start August 2026".
**Nicht ersatzlos streichen** — beide Kursinstanzen heißen sonst identisch, und die
Admin-Auswahllisten führen kein `is_active` (`app/schemas/course.py:84-91`), was beim
Announcement-Versand zum Fehlgriff einlädt. Besser umformulieren, z.B. `· August-Gruppe`.

**Kein Ablauf-Hinweis.** Weder Startdatum noch Live-Call-Termin stehen in irgendeiner Mail
(`email.py:215-240`). Höchste Aufmerksamkeit im Funnel, aktuell ungenutzt.

**Fehlplatzierter Satz.** „Falls du diese Einladung nicht erwartet hast, kannst du diese
E-Mail ignorieren" (`email.py:225/238`) stammt aus dem Admin-Invite-Flow.

**Logo bricht in Outlook.** `_wrap_in_brand_template` (`email.py:61`) lädt
`nw-logo.webp` — WebP wird vom Word-Renderer in Outlook für Windows nicht unterstützt.
Beide Bild-URLs sind erreichbar (HTTP 200, verifiziert 2026-07-26); Profilbild ist JPEG.

## Block 4 — Sales Page (`nora-website`)

Statisches HTML, kein Build, kein Feature-Flag. Deploy: Push auf `main` → GitHub Action → Cloudron Surfer.

Der Checkout **existierte schon** und wurde am 08.06. zurückgebaut. Reverse-Diff:
```bash
git show 9fd26f5   # Anmeldung geschlossen, CTAs auf Warteliste, Tracking neutralisiert
git show b51fe9f   # Juni-Termine & Checkout-Copy entfernt
```
Vorhandenes Runbook aus dem Juni-Launch: `tasks/go-live-4-wochen-glukose-balance-code.md`

Umzustellen in `public/kurse/glukose-balance-code/index.html`:
- [ ] 4 CTAs (Z. 1429 nav, 1461 hero, 1964 price-card, 2116 final) → Payment Link,
      `target="_blank" rel="noopener"`, Label „Platz sichern"
- [ ] Scarcity-Copy (Z. 1444, 1446, 1778, 1947, 1950, 2115, 2049)
- [ ] Buy-Notes (Z. 1466, 1965ff, 2117ff) + Zahlungsmethoden-Zeile
- [ ] Tracking (Z. 2241-2249) → `begin_checkout` mit `ecommerce{value, item_id:'4wochencode'}`
- [ ] **Countdown (Z. 2199-2233): Deadline steht auf `2026-06-08`** — mitziehen oder Block löschen
- [ ] Homepage `public/index.html:2808`: „Start Juni 2026" → August
- [ ] Warteliste-Seite: Redirect oder Copy auf „nächste Runde"

**Zwei stille Fallen:**
- Klasse `js-buy-btn` muss an den CTAs bleiben — `public/utm.js:52-78` hängt
  `client_reference_id` nur an Elemente mit dieser Klasse. Sonst fällt die UTM-Attribution weg.
- Preis steht an mehreren Stellen (Z. 1849, 1953 + Danke-Seite Z. 319/325). Bei Preisänderung
  alle mitziehen, sonst wird ein falscher Umsatzwert an GA4/Meta gemeldet.

**Copy-Konflikt:** Die Seite sagt aktuell „nächste Gruppe ab September", der Kurs heißt
„Start August 2026", der Warteliste-Tag heißt „Warteliste GBC September" und die
Bestätigungsmail der Warteliste versprach September. Vor dem Launch auf eine Aussage einigen.
(Der Tag-Name selbst ist nur ein Label und funktional egal.)

---

## Block 5 — Kampagnen

### 🔴 Kampagne A — „Launch 4 Wochen Code August (Warteliste)" — akut

**Ist-Stand (Screenshot 20:05):** Entwurf · **2 E-Mails statt geplant 4** · **0 Empfängerinnen**
- Mail 1: **26.07., 20:30** ← heute
- Mail 2: 27.07., 12:00
- Tag `Warteliste GBC September` hat **28 Kontakte**
- Zielgruppe (Stufen): nichts angehakt — korrekt, Targeting läuft rein über den Tag
- „Neue Kontakte mit diesem Tag automatisch aufnehmen": **nicht aktiviert**

**Im Entwurf geht nichts raus.** `enrollContactsInSequence` setzt die Subs auf `paused`
mit `nextSendAt: null` (`sequences.ts:730/740`); der Cron greift nur aktive Subs mit
fälligem `nextSendAt`. Vergangene Termine lösen also keinen versehentlichen Versand aus.

### ⚠️ Der Skip wird beim ZUORDNEN eingebrannt, nicht beim Aktivieren

`enrollContactsInSequence` (`sequences.ts:705-711`) rechnet bereits beim Bulk-Subscribe:

```js
const firstEmail = findFirstEmailStep(sequence.steps, 0, true);  // skipPast
const initialIndex = firstEmail?.index ?? 0;
```

`currentStepIndex` wird im **Moment der Zuordnung** festgeschrieben. Werden Kontakte
zugeordnet, während Mail 1 bereits in der Vergangenheit liegt, stehen sie ab da auf Mail 2 —
und das bleibt so, **auch wenn Mail 1 danach in die Zukunft geschoben wird**. Beim Aktivieren
läuft `findFirstEmailStep(steps, sub.currentStepIndex, ...)` ab dem gespeicherten Index
und geht nie zurück. Keine Warnung, keine Fehlermeldung.

Zweiter Effekt: Sind **alle** Termine vorbei, wirft der Bulk-Subscribe hart
`"Sequenz hat keine zukünftigen Mails mehr — Bulk-Subscribe nicht möglich"` (`:708`).

**Daraus folgt die Reihenfolge — Schritt 2 zwingend vor Schritt 3:**
1. [ ] Mails 3 und 4 ergänzen
2. [ ] **Alle `sendDate` in die Zukunft setzen**
3. [ ] *Danach* „Kontakte mit Tag zuordnen" → 28 Kontakte
4. [ ] „Neue Kontakte mit diesem Tag automatisch aufnehmen" aktivieren
5. [ ] Sequenz auf **Aktiv**

> ⚠️ Ein `sendDate` in die **Vergangenheit** editieren löst dagegen Sofortversand an alle aus —
> `updateSequenceSteps` (`sequences.ts:373-374`) setzt `nextSendAt = sendDate` ohne
> Vergangenheitsprüfung. Am Launchtag nicht mehr an Timings drehen.

Zu Schritt 4: `autoSubscribeByTag` (`sequences.ts:616`) nimmt Nachzügler laufend auf und
startet sie bei der nächsten **zukünftigen** Mail. Sind alle Termine durch, kein Subscribe mehr —
sauberer Cutoff, nichts weiter zu tun. Greift aber nur bei Status `active`.

### Kampagne B — ~2600 Kontakte

- [ ] Zuordnung **in Blöcken**, nicht in einem Rutsch. `bulkSubscribeByStage`
      (`sequences.ts:751-773`) macht ~2.600 sequentielle Einzel-Writes ohne Chunking.
      Bricht es ab: einfach wiederholen, die Zuordnung ist idempotent.
- [ ] **Überschneidung mit Kampagne A entscheiden.** Es gibt **keinen** Ausschluss zwischen
      Kampagnen — Dedup läuft nur pro `(contactId, sequenceId)`. Wer auf der Warteliste steht
      und in den 2600 ist, bekommt **7 Mails**, teils zwei am selben Tag.
- [ ] **`isTest` und `emailInvalid` vorher aussortieren.** Werden nirgends gefiltert —
      weder beim Zuordnen noch beim Versand (verifiziert über `sequences.ts`, `emails.ts`, `resend.ts`).
- [ ] Prüfen, ob parallel laufende Launch-Kampagnen kollidieren
      („Launch Glukose Balance auf Reisen" steht auf **Aktiv**).

**Versanddauer ~60 Min pro Mail:** 500 pro Lauf (`emails.ts:136`), 600 ms Throttle (`:151`),
Cron alle 10 Min (`instrumentation.ts:18`) → 6 Läufe. Die letzte Empfängerin bekommt die Mail
rund eine Stunde nach der ersten. Bei Zeitdruck-Copy („nur heute bis 20 Uhr") einplanen.

**Kein CRM-Deploy während des Versands.** Der Claim nullt `nextSendAt` **vor** dem Senden
(`emails.ts:125-139`). Ein Container-Neustart mitten im Batch verliert die geclaimten
Empfängerinnen still — sie werden von keiner Query je wieder aufgegriffen.

**Soft-Bounce = permanenter Unsubscribe** (`webhooks/resend/route.ts:137-147`). Ein
„Mailbox voll" wirft die Kontaktin dauerhaft aus *allen* Kampagnen. Bei 2600 länger nicht
gemailten Adressen verbrennt das einen messbaren Teil der Liste; Reset nur manuell.

---

## Kritischer Pfad

```
Block 0 → Block 1 → Block 2 → Block 3 (Testkauf) → Sales Page live → Kampagnen aktivieren
```

Die Kampagnen sind das Letzte. Geht eine Mail raus, bevor der Testkauf durch ist,
wird in ein System verkauft, von dem niemand weiß, ob es liefert.

---

## Nach dem Launch beobachten

- [ ] Tag 1–3: Abgleich Stripe-Käufe ↔ Enrollments von Hand
      (Webhook-Idempotenz-Härtung F1 ist offen — siehe `tasks/webhook-idempotency-hardening.md`)
- [ ] CRM-Glocke auf „⚠️ Kauf braucht manuelle Kohorten-Zuweisung" prüfen
- [ ] Erste echte Check-in-Antwort: kommt sie im CRM an?

**Support-Wissen:** Invite-Token laufen nach 7 Tagen ab. „Passwort vergessen" heilt das
automatisch — `forgot-password` erkennt `invite_accepted_at IS NULL` und verschickt einen
frischen Invite statt einer Reset-Mail (`app/api/auth.py:114-131`).
