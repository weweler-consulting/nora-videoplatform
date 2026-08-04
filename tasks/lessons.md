# Lessons

Muster, die sich wiederholt haben. Vor größeren Analysen kurz durchgehen.

---

## Lokalen Checkout-Stand prüfen, bevor Code als „nicht vorhanden" gemeldet wird

**Wann passiert (2026-07-26):** Behauptet, im `nora-crm` gebe es keine Tag→Sequenz-Zuordnung
und das müsse gebaut werden. Tatsächlich lag das Feature seit fünf Tagen in `origin/main`
(PR #26 + #27). Analysiert wurde `/Users/justus/Developer/nora-crm`, das **33 Commits
hinterherhing**. Ergebnis: ein erfundener Blocker auf dem kritischen Pfad vor einem Launch.

**Warum es passiert:** Nora-Repos existieren mehrfach lokal (`~/Developer/*` und
`~/conductor/workspaces/*`). Subagents greifen sich irgendeinen davon und lesen den
Arbeitsbaum, ohne den Remote-Stand zu kennen. Ein `grep` auf einem alten Checkout ist
syntaktisch sauber und inhaltlich falsch.

**Regel:** Bevor eine Aussage der Form „Feature X existiert nicht" oder „muss gebaut werden"
über ein *anderes* Repo als das Arbeitsverzeichnis gemacht wird:

```bash
git -C <repo> fetch -q && git -C <repo> rev-list --left-right --count HEAD...origin/main
```

Steht rechts etwas ≠ 0, gegen `origin/main` prüfen statt gegen den Arbeitsbaum:
`git grep <muster> origin/main -- <pfad>`. Zusätzlich `gh pr list --state all` — ein
gemergter PR-Titel beantwortet die Frage oft in einer Zeile.

Subagents, die fremde Repos untersuchen, bekommen diese Anweisung mit in den Prompt.

---

## Bei „was habe ich übersehen" die stillen Ausfälle suchen, nicht die lauten

**Wann (2026-07-26, Launch-Analyse):** Der Wert der Analyse lag fast vollständig in Pfaden,
die mit HTTP 200 antworten und trotzdem nichts tun — Stripe-Webhook ohne Produkt-Mapping
(`{"ok": true, "ignored": "no_match"}`), Live-Call-Import ohne Serie (kein Log), fehlende
`success_url`-Parameter (Tracking still auf 0), `runsAsCohort=false` (keine Zuweisung, keine Glocke).

**Regel:** Bei Go-Live- und Review-Fragen gezielt nach Code suchen, der Fehler in Erfolg
umdeutet: `return`/`continue` nach einem fehlgeschlagenen Lookup, `logger.warning` ohne
Alarm, `ok: true` bei ausgelassener Arbeit, Defaults, die Konfiguration vortäuschen.
Zu jedem Punkt beantworten: *Woran merkt der Mensch, dass es nicht passiert ist?*
Wenn die Antwort „gar nicht" ist, gehört er nach oben in die Liste.

---

## Zustands-Behauptungen über Prod als solche kennzeichnen

**Wann (2026-07-26):** Empfehlungen zu `stripe_product_id`-Zuordnungen ausgesprochen, ohne
Zugriff auf die Prod-DB (`cloudron` war nicht eingeloggt). Die Schlüsse aus dem Code waren
richtig, die tatsächliche Datenlage aber ungeprüft.

**Regel:** Ableitungen aus Code und Ableitungen aus Prod-Daten sauber trennen und die
Lücke benennen, statt sie zu überspielen. Wenn der Zugriff fehlt: den fertigen read-only
Befehl mitliefern, damit der Check nachgeholt werden kann. Verifikationswege stehen in
`reference_cloudron_env_management` (Memory) — `scripts/sql.py` bzw. `scripts/sql.js`.

---

## Fremdsystem-Umbauten: den dokumentierten Endzustand nicht als Ist-Zustand annehmen

**Wann (2026-08-04, Live-Call-Import):** Googles Blogpost zum Drive-Umbau beschreibt, dass der
alte Ordner `Meet Recordings` nach `Google Meet/` verschoben und umbenannt wird. Fix darauf
gebaut (Suchwurzel = Elternordner, falls er „Google Meet" heisst) — bei Nora lag der alte
Ordner aber noch DANEBEN. Google migriert schrittweise, der Blogpost sagt das sogar in einem
Nebensatz („beide koennen voruebergehend erscheinen"). Kostete einen kompletten Deploy-Zyklus.

**Regel:** Bei Aenderungen an Fremdsystemen den Fix so bauen, dass er ALLE Zwischenzustaende
abdeckt (hier: beide Ordner immer durchsuchen), nicht nur den dokumentierten Endzustand.
Migrationen laufen tage- bis wochenlang und pro Account unterschiedlich. Und: bevor man auf
eine unbewiesene Annahme ueber fremde Daten deployt, erst den einen Befehl bauen, der sie
prueft — hier haette `spike_live_call.py --list` die falsche Wurzel sofort gezeigt.
