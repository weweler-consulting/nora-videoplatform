# Live-Call Auto-Import — Phase 1: Setup + Spike (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die drei Foundation-Unbekannten validieren (Service-Account-Auth gegen Workspace, Drive-Recording-Erkennung per Name, Download einer ~1-GB-Datei) und den wiederverwendbaren Name-Parser per TDD bauen — bevor die Voll-Pipeline (Phase 2/3) entsteht.

**Architecture:** Reiner Lese-Pfad. Ein Service-Account (Domain-Wide-Delegation, impersoniert `nora@noraweweler.de`, `drive.readonly`) listet den „Meet Recordings"-Ordner, filtert Gruppen-Live-Call-Videos per Name-Prefix, parst das Datum. Ein TDD-getesteter Pure-Function-Parser + ein dünner Drive-Client + ein manuelles Spike-Skript.

**Tech Stack:** Python/FastAPI, `google-api-python-client`, `google-auth`, pytest.

**Referenz-Spec:** `docs/superpowers/specs/2026-06-05-live-call-auto-import-design.md`

---

## Phase 0: Operative Vorbereitung (User-Aktion — von mir begleitet, KEIN Code)

> **Auth-Pivot:** Statt Service-Account → **OAuth** (Workspace-interner Client). Grund: Org-Policy
> `iam.disableServiceAccountKeyCreation` blockiert SA-Keys. Tasks 3–5 wurden entsprechend auf
> OAuth refaktoriert (Config: `google_oauth_*`; Drive-Client: Refresh-Token-Credentials;
> neues `scripts/google_oauth_setup.py`).

Diese Schritte macht Justus in GCP/Workspace; ohne sie kann der Spike nicht laufen.

- [x] **0.1** GCP-Projekt `nora-automation` (Org `noraweweler.de`) angelegt, **Google Drive API** aktiviert.
- [ ] **0.2** **OAuth-Consent-Screen** → User-Type **„Intern"** (App-Name `Nora Live-Call Import`).
- [ ] **0.3** **OAuth-Client-ID** (Typ **Desktop-App**) erstellen → Client-Secret-JSON herunterladen.
- [ ] **0.4** Einmaliger Consent: `python3 scripts/google_oauth_setup.py <client_secret.json>` lokal laufen lassen → im Browser als `nora@noraweweler.de` Drive-Lesezugriff bestätigen → gibt Client-ID, Secret, Refresh-Token aus.
- [ ] **0.5** Diese drei + Folder-ID als ENV setzen (lokal für den Spike, später `/app/data/env.sh`):
  `NORA_GOOGLE_OAUTH_CLIENT_ID`, `NORA_GOOGLE_OAUTH_CLIENT_SECRET`, `NORA_GOOGLE_OAUTH_REFRESH_TOKEN`,
  `NORA_MEET_RECORDINGS_FOLDER_ID=1rruYIZ956dNjllrenSGleL4UoZHZuM9h`. Nicht committen.

---

## Task 1: Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Dependencies ergänzen**

`requirements.txt` um diese Zeilen erweitern:

```
google-api-python-client>=2.120
google-auth>=2.30
```

- [ ] **Step 2: Installieren**

Run: `.venv/bin/pip install -r requirements.txt`
Expected: beide Pakete installiert, keine Fehler.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "build: google-api-python-client + google-auth für Live-Call-Import"
```

---

## Task 2: Recording-Name-Parser (TDD, Pure Function)

Der einzige rein logische Baustein — voll testbar, in Phase 2 wiederverwendet.

**Files:**
- Create: `app/core/live_call_parser.py`
- Test: `tests/test_live_call_parser.py`

- [ ] **Step 1: Failing Test schreiben**

`tests/test_live_call_parser.py`:

```python
from datetime import datetime

from app.core.live_call_parser import parse_occurrence_at, is_group_recording


def test_parse_occurrence_at_group_recording():
    name = "Live Call | Glukose Balance - 2026/06/04 19:14 WEST - Recording"
    assert parse_occurrence_at(name) == datetime(2026, 6, 4, 19, 14)


def test_parse_occurrence_at_handles_notizen_name():
    # Notizen-Doc trägt dasselbe Datum; mimeType-Filter trennt Video/Doc,
    # aber der Parser muss das Datum trotzdem sauber ziehen.
    name = "Live Call | Glukose Balance – 2026/05/28 19:14 WEST – Notizen von Nora"
    assert parse_occurrence_at(name) == datetime(2026, 5, 28, 19, 14)


def test_parse_occurrence_at_returns_none_without_date():
    assert parse_occurrence_at("Irgendein Dokument ohne Datum") is None


def test_is_group_recording_matches_prefix():
    prefix = "Live Call | Glukose Balance"
    assert is_group_recording("Live Call | Glukose Balance - 2026/06/04 19:14 WEST - Recording", prefix) is True


def test_is_group_recording_excludes_one_on_one():
    prefix = "Live Call | Glukose Balance"
    assert is_group_recording("Glukose Balance Coaching - Kathi x Nora - 2026/06/03 11:01 WEST - Recording", prefix) is False
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `.venv/bin/python -m pytest tests/test_live_call_parser.py -v`
Expected: FAIL (`ModuleNotFoundError: app.core.live_call_parser`).

- [ ] **Step 3: Minimal-Implementierung**

`app/core/live_call_parser.py`:

```python
"""Parsing der Meet-Recording-Dateinamen der Gruppen-Live-Calls.

Schema (Video):  "<Prefix> - YYYY/MM/DD HH:MM <TZ> - Recording"
Beispiel:        "Live Call | Glukose Balance - 2026/06/04 19:14 WEST - Recording"

Der Prefix ist kurs-spezifisch und trennt Gruppen-Live-Calls von 1:1-Calls/
Beratungsgesprächen im selben Ordner. Video vs. Notizen-Doc wird über den
mimeType in der Drive-Query getrennt, nicht hier.
"""
import re
from datetime import datetime

_DATE_RE = re.compile(r"(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2})")


def parse_occurrence_at(name: str) -> datetime | None:
    """Datum+Uhrzeit (naive lokale Wandzeit) aus dem Namen ziehen; None ohne Treffer."""
    m = _DATE_RE.search(name)
    if not m:
        return None
    y, mo, d, h, mi = (int(g) for g in m.groups())
    try:
        return datetime(y, mo, d, h, mi)
    except ValueError:
        return None


def is_group_recording(name: str, prefix: str) -> bool:
    """True, wenn der Name mit dem kurs-spezifischen Prefix beginnt."""
    return name.startswith(prefix)
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `.venv/bin/python -m pytest tests/test_live_call_parser.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/core/live_call_parser.py tests/test_live_call_parser.py
git commit -m "feat(live-call): Recording-Name-Parser (Datum + Prefix-Filter)"
```

---

## Task 3: Config-Felder für Google-Service-Account

**Files:**
- Modify: `app/core/config.py`

- [ ] **Step 1: Felder + Parsing ergänzen**

In `app/core/config.py` zur `Settings`-Klasse (Feldnamen ggf. an vorhandene Konvention anpassen; Env-Prefix beachten):

```python
    # Google Drive (Live-Call-Import)
    google_sa_json: str | None = None            # Service-Account-Key als JSON-String
    google_impersonate_subject: str | None = None
    meet_recordings_folder_id: str | None = None

    @property
    def google_sa_info(self) -> dict | None:
        """Geparster Service-Account-Key oder None, wenn nicht konfiguriert."""
        import json
        if not self.google_sa_json:
            return None
        return json.loads(self.google_sa_json)
```

- [ ] **Step 2: Import-Smoke-Test**

Run: `.venv/bin/python -c "from app.core.config import settings; print(settings.google_sa_info is None)"`
Expected: `True` (lokal ohne ENV → None, kein Crash).

- [ ] **Step 3: Commit**

```bash
git add app/core/config.py
git commit -m "feat(live-call): Config-Felder für Google-Service-Account"
```

---

## Task 4: Drive-Client (dünner Wrapper, live-validiert per Spike)

Kein Unit-Test mit echten Calls — die Validierung passiert in Task 5 (Spike) gegen echtes Google.

**Files:**
- Create: `app/integrations/google_drive.py`

- [ ] **Step 1: Implementierung**

`app/integrations/google_drive.py`:

```python
"""Drive-Lesezugriff als Service-Account mit Domain-Wide-Delegation.

Impersoniert den konfigurierten Workspace-Nutzer (nora@…) und liest ausschließlich
(scope drive.readonly): Video-Dateien im Meet-Recordings-Ordner listen + downloaden.
"""
import logging

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.core.config import settings

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _service():
    info = settings.google_sa_info
    if not info or not settings.google_impersonate_subject:
        raise RuntimeError("Google-Service-Account nicht konfiguriert")
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=_SCOPES, subject=settings.google_impersonate_subject,
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_video_files(folder_id: str, name_prefix: str, modified_after_iso: str) -> list[dict]:
    """Video-Dateien im Ordner mit Name-Prefix, geändert nach modified_after_iso.
    Gibt [{id,name,mimeType,size,modifiedTime}]. Echten Prefix clientseitig prüfen,
    da Drives 'name contains' nur Teilstring kann."""
    svc = _service()
    q = (
        f"'{folder_id}' in parents and trashed = false "
        f"and mimeType contains 'video/' "
        f"and modifiedTime > '{modified_after_iso}'"
    )
    files, page_token = [], None
    while True:
        resp = svc.files().list(
            q=q,
            fields="nextPageToken, files(id,name,mimeType,size,modifiedTime)",
            pageSize=100, pageToken=page_token,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return [f for f in files if f["name"].startswith(name_prefix)]


def download_to_file(file_id: str, dest_path: str) -> None:
    """Chunked-Download auf die Platte (kein RAM-Blowup bei ~1 GB)."""
    svc = _service()
    request = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
```

- [ ] **Step 2: Import-Smoke-Test**

Run: `.venv/bin/python -c "import app.integrations.google_drive"`
Expected: kein Fehler (Module importierbar).

- [ ] **Step 3: Commit**

```bash
git add app/integrations/google_drive.py
git commit -m "feat(live-call): Drive-Client (Service-Account, list + download)"
```

---

## Task 5: Spike-Skript (manuelle Live-Validierung)

**Files:**
- Create: `scripts/spike_live_call.py`

- [ ] **Step 1: Implementierung**

`scripts/spike_live_call.py`:

```python
"""Spike: validiert Service-Account-Auth + Drive-Erkennung + Big-File-Download.

Voraussetzung: ENV GOOGLE_SA_JSON, GOOGLE_IMPERSONATE_SUBJECT, MEET_RECORDINGS_FOLDER_ID.

  python3 scripts/spike_live_call.py --list
  python3 scripts/spike_live_call.py --download <drive_file_id>
"""
import argparse
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.live_call_parser import parse_occurrence_at, is_group_recording
from app.integrations.google_drive import list_video_files, download_to_file

PREFIX = "Live Call | Glukose Balance"  # für den Spike fest; in Phase 2 aus dem Mapping


def cmd_list() -> None:
    folder = settings.meet_recordings_folder_id
    since = (datetime.utcnow() - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    files = list_video_files(folder, PREFIX, since)
    print(f"{len(files)} Video-Datei(en) mit Prefix '{PREFIX}':")
    for f in files:
        occ = parse_occurrence_at(f["name"])
        size_mb = int(f.get("size", 0)) / 1e6
        print(f"  - {f['name']}")
        print(f"      id={f['id']}  mime={f['mimeType']}  {size_mb:.1f} MB  occurrence={occ}")


def cmd_download(file_id: str) -> None:
    dest = os.path.join(tempfile.gettempdir(), f"spike_{file_id}.mp4")
    t0 = time.time()
    download_to_file(file_id, dest)
    dt = time.time() - t0
    size_mb = os.path.getsize(dest) / 1e6
    print(f"Download fertig: {size_mb:.1f} MB in {dt:.1f}s ({size_mb/dt:.1f} MB/s) → {dest}")
    os.remove(dest)
    print("Temp-Datei gelöscht.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--download", metavar="FILE_ID")
    args = ap.parse_args()
    if args.list:
        cmd_list()
    elif args.download:
        cmd_download(args.download)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Live-Listing ausführen (validiert Auth + Erkennung)**

Run: `.venv/bin/python scripts/spike_live_call.py --list`
Expected: Liste der `Live Call | Glukose Balance …`-Videos mit korrekt geparstem `occurrence`, **ohne** die Notizen-Docs und **ohne** 1:1-Calls.

- [ ] **Step 3: Big-File-Download ausführen (validiert ~1-GB-Pfad)**

Run: `.venv/bin/python scripts/spike_live_call.py --download <eine_file_id_aus_step_2>`
Expected: Download läuft durch, Größe/Zeit/Durchsatz werden ausgegeben, Temp-Datei wird gelöscht. (Auf dem Cloudron-Container gegenchecken, dass Temp-Disk reicht.)

- [ ] **Step 4: Commit**

```bash
git add scripts/spike_live_call.py
git commit -m "feat(live-call): Spike-Skript (Auth + Erkennung + Big-File-Download)"
```

---

## Task 6: Spike-Ergebnisse festhalten

**Files:**
- Modify: `docs/superpowers/specs/2026-06-05-live-call-auto-import-design.md`

- [ ] **Step 1: Findings ergänzen**

Am Ende des Spec einen Abschnitt **„Spike-Ergebnisse (2026-…)"** anhängen mit: bestätigte Drive-Feld-Namen/Formate, beobachtetes Download-Tempo, ob die mimeType+Prefix-Filterung sauber trennt, ENV/DWD-Stolpersteine. Diese Fakten präzisieren den Phase-2-Plan.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-06-05-live-call-auto-import-design.md
git commit -m "docs(spec): Spike-Ergebnisse Live-Call-Import"
```

---

## Self-Review (gegen den Spec)

- **Spec-Abdeckung Phase 1:** Auth (Task 3/4) ✓, Drive-Erkennung + Prefix/mimeType-Filter (Task 4/5) ✓, Name→Datum-Parsing (Task 2) ✓, Big-File-Download/Stream-Risiko (Task 5) ✓, Setup-Anforderungen (Phase 0) ✓.
- **Platzhalter:** keine — jeder Code-Step enthält vollständigen Code bzw. konkreten Befehl.
- **Typ-Konsistenz:** `parse_occurrence_at`/`is_group_recording`/`list_video_files`/`download_to_file`/`settings.google_sa_info` durchgängig gleich benannt.

## Nicht in diesem Plan (separate Pläne nach dem Spike)

- **Phase 2 (Core-Pipeline):** Datenmodell (`LiveCallSeries`, `LiveCallImport`, `Lesson.is_published`), Detector-Loop, Importer (Bunny-Server-Upload + hybride Platzierung), Serie→Kurs-Mapping-Admin.
- **Phase 3 (Freigabe):** Signierte 1-Klick-Mail, Approve/Dismiss-Endpoints, Ankündigungs-Integration, Admin-Liste.

Diese werden nach dem Spike detailliert geplant, weil die exakten Drive-Feldformate + das Streaming-Verhalten ihre Implementierung beeinflussen.
