"""Spike: validiert Service-Account-Auth + Drive-Erkennung + Big-File-Download.

Voraussetzung: ENV NORA_GOOGLE_SA_JSON, NORA_GOOGLE_IMPERSONATE_SUBJECT,
NORA_MEET_RECORDINGS_FOLDER_ID (plus NORA_SECRET_KEY für den Config-Import).

  python3 scripts/spike_live_call.py --list
  python3 scripts/spike_live_call.py --download <drive_file_id>
"""
import argparse
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta

# Repo-Root auf den Pfad, damit `app` auch beim Aufruf aus scripts/ importierbar ist.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.live_call_parser import parse_occurrence_at
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
    rate = size_mb / dt if dt else 0
    print(f"Download fertig: {size_mb:.1f} MB in {dt:.1f}s ({rate:.1f} MB/s) → {dest}")
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
