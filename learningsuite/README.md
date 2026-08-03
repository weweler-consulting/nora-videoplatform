# LearningSuite-Export

Migration: Videos + Inhalte aus LearningSuite ziehen, bevor Vertrag am **16.05.2026** endet.

## Setup (einmalig)

```bash
cd learningsuite
npm install
npx playwright install chromium
```

## Login (einmalig, bis Session abläuft)

```bash
node ls-export.mjs login
```

Chromium öffnet sich sichtbar → einloggen → Terminal zurück → **Enter**. Session landet in `auth.json` (gitignored).

## POC: 1 Video herunterladen

```bash
node ls-export.mjs download "https://noraweweler.learningsuite.io/admin/editor/…"
```

Lektion öffnet sich, **du klickst** im Browser „Video herunterladen". Script fängt die Datei ab und legt sie in `export/poc/` ab.

Sobald POC sitzt → Enumerator + Batch-Modus (Phase 2).
