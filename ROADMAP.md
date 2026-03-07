# Nora Videoplatform — Roadmap

## Bereits umgesetzt
- Kurse, Module, Sektionen, Lektionen
- Video-Embedding (Bunny.net, YouTube, Vimeo)
- Nutzer-Management + Einladungen (E-Mail + Copy-Paste)
- Kurs-Zuordnung (mehrere Kurse pro Nutzer)
- Fortschritts-Tracking (Lektionen abhaken)
- Content Drip (Module nach X Tagen freischalten)
- Passwort vergessen / Reset per E-Mail
- User-Detail-Sheet mit Fortschritts-Analytics pro Kurs & Modul
- Custom Branding (Nora Corporate Design)
- Login-Footer (Impressum, Datenschutz, AGB)
- Video-Upload direkt zu Bunny.net (TUS-Upload mit Fortschrittsbalken)
- Video-Löschung bei Bunny.net beim Entfernen aus Lektion
- Auto-Deploy auf Push via GitHub Actions
- Admin-Dashboard (KPIs, Kursfortschritt, inaktive Teilnehmer)
- Stripe-Kaufflow (Payment Link → automatisch Account + Kurs + Zugangsdaten per E-Mail)
- Datei-Downloads pro Lektion (PDFs, Rezepte, Worksheets)
- Rich-Text/Markdown für Lektionen (formatierter Text unter Videos)

## Offene Features — sortiert nach Business Impact + Aufwand

| # | Feature | Business Impact | Aufwand | Warum diese Reihenfolge |
|---|---|---|---|---|
| 1 | **E-Mail bei Modul-Freischaltung** | Hoch | Mittel | Ohne das ist Drip-Content nutzlos — Teilnehmer merken nicht, dass neuer Content da ist. Direkt weniger Abbrüche. |
| 2 | **Zertifikat bei Abschluss** | Hoch | Mittel | Auto-PDF bei 100% — Teilnehmer teilen es auf Social Media = kostenlose Werbung. Motiviert zum Durchziehen = weniger Refunds. |
| 3 | **E-Mail-Automationen** | Hoch | Groß | Inaktivitäts-Reminder, Motivations-Mails. Größter Retention-Hebel, aber auch größter Aufwand. |
| 4 | **Kommentar/Fragen pro Lektion** | Mittel | Mittel | Community-Gefühl, persönliche Bindung zu Nora. Gut für Empfehlungen, aber kein direkter Umsatz-Treiber. |
| 5 | **Quiz/Tests** | Mittel | Mittel | Multiple-Choice festigt Gelerntes. Gibt Erfolgserlebnisse, aber Teilnehmer kaufen nicht wegen Quiz. |
| 6 | **Aufgaben/Submissions** | Mittel | Groß | Ernährungstagebuch etc. Tiefes Engagement, aber großer Aufwand und erst sinnvoll mit aktiver Community. |
| 7 | **Gruppen/Kohorten** | Niedrig | Mittel | Erst relevant wenn gleicher Kurs mehrfach als Durchgang verkauft wird. Heute nicht nötig. |
