"""Server-seitiger Upload zu Bunny Stream (für den Live-Call-Auto-Import).

Anders als app/api/upload.py (TUS, client-seitig) lädt dies eine Datei vom
Datenträger direkt per PUT hoch — gestreamt, kein RAM-Blowup. Gleiche Stream-
Library wie der Video-Upload: Env BUNNY_API_KEY, BUNNY_LIBRARY_ID.
"""
import os

import httpx

_STREAM_BASE = "https://video.bunnycdn.com/library"


def upload_video_from_file(title: str, file_path: str) -> str:
    """Legt ein Bunny-Stream-Video an, lädt die Datei per PUT hoch, gibt die
    embed_url zurück (gleiches Format wie app/api/upload.py)."""
    api_key = os.environ.get("BUNNY_API_KEY", "")
    library_id = os.environ.get("BUNNY_LIBRARY_ID", "")
    if not api_key or not library_id:
        raise RuntimeError("Bunny Stream nicht konfiguriert (BUNNY_API_KEY/BUNNY_LIBRARY_ID)")
    base = f"{_STREAM_BASE}/{library_id}/videos"
    headers = {"AccessKey": api_key}

    create = httpx.post(base, headers={**headers, "Content-Type": "application/json"},
                        json={"title": title}, timeout=30.0)
    create.raise_for_status()
    video_id = create.json()["guid"]

    # Endlicher Timeout statt None — ein hängender Upload darf nicht ewig blockieren.
    # Großzügige read/write-Fenster (30 Min) für GB-Dateien, schneller connect.
    upload_timeout = httpx.Timeout(connect=30.0, read=1800.0, write=1800.0, pool=30.0)
    with open(file_path, "rb") as fh:
        up = httpx.put(f"{base}/{video_id}", headers=headers, content=fh, timeout=upload_timeout)
    up.raise_for_status()

    return f"https://iframe.mediadelivery.net/embed/{library_id}/{video_id}"


def delete_video_by_embed_url(embed_url: str) -> None:
    """Best-effort: Bunny-Video anhand der embed-URL löschen (für 'Verwerfen', Phase 3)."""
    api_key = os.environ.get("BUNNY_API_KEY", "")
    if not api_key:
        return
    parts = embed_url.rstrip("/").split("/")
    if len(parts) < 2:
        return
    video_id, library_id = parts[-1], parts[-2]
    try:
        httpx.delete(f"{_STREAM_BASE}/{library_id}/videos/{video_id}",
                     headers={"AccessKey": api_key}, timeout=15.0)
    except httpx.HTTPError:
        return
