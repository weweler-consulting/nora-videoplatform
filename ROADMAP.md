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

## Offene Features — sortiert nach Business Impact

### Retention (hält Teilnehmer dran → weniger Refunds, mehr Empfehlungen)

| # | Feature | Impact | Aufwand |
|---|---|---|---|
| 1 | **E-Mail bei Modul-Freischaltung** | Teilnehmer merken sonst nicht, dass neuer Content da ist. Aktiviert die Drip-Funktion richtig. | Mittel |
| 2 | **E-Mail-Automationen** | Erinnerungen bei Inaktivität, Motivations-Mails, Drip-Sequenzen. Reduziert Abbruchrate massiv. | Groß |
| 3 | **Kommentar/Fragen pro Lektion** | Teilnehmer stellen Fragen, Nora antwortet — Community-Gefühl, persönliche Bindung. | Mittel |

### Lernerfolg (bessere Ergebnisse → bessere Testimonials → mehr Verkäufe)

| # | Feature | Impact | Aufwand |
|---|---|---|---|
| 4 | **Quiz/Tests** | Multiple-Choice pro Lektion — festigt Gelerntes, gibt Teilnehmern Erfolgserlebnisse. | Mittel |
| 5 | **Aufgaben/Submissions** | Teilnehmer reichen Fotos/Texte ein (z.B. Ernährungstagebuch). Tiefes Engagement. | Groß |
| 6 | **Zertifikat bei Abschluss** | Auto-PDF bei 100% — Motivation zum Durchziehen, teilbar auf Social Media. | Mittel |

### Skalierung (wird relevant ab mehreren Kursen/Durchgängen)

| # | Feature | Impact | Aufwand |
|---|---|---|---|
| 7 | **Gruppen/Kohorten** | Teilnehmer in Durchgänge einteilen. Relevant wenn gleicher Kurs mehrfach verkauft wird. | Mittel |

## Empfohlene Reihenfolge

1. **E-Mail bei Modul-Freischaltung** — aktiviert Drip richtig
2. **E-Mail-Automationen** — Retention-Hebel
3. **Kommentar/Fragen** — Community-Gefühl
4. **Zertifikat bei Abschluss** — Motivation + Social Proof
