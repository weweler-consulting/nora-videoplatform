"""Drive-Lesezugriff via OAuth (Workspace-interner Client, scope drive.readonly).

Nutzt einen einmalig geholten Refresh-Token (siehe scripts/google_oauth_setup.py),
um als nora@… zu lesen: Video-Dateien im Meet-Recordings-Ordner listen + downloaden.
Access-Tokens werden bei Bedarf automatisch erneuert.
"""
import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.core.config import settings

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _service():
    if not settings.google_oauth_configured:
        raise RuntimeError("Google-OAuth nicht konfiguriert (Client-ID/Secret/Refresh-Token)")
    creds = Credentials(
        token=None,
        refresh_token=settings.google_oauth_refresh_token,
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        token_uri=_TOKEN_URI,
        scopes=_SCOPES,
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
