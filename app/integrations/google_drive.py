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


_FOLDER_MIME = "application/vnd.google-apps.folder"
_MEET_ROOT_FOLDER_NAME = "Google Meet"
_MAX_FOLDER_DEPTH = 3      # Google Meet/<Meeting>/ braucht 1; Puffer für Verschachtelung
_MAX_FOLDERS = 300         # Reißleine, falls je auf einen riesigen Baum gezeigt wird
_PARENTS_PER_QUERY = 25    # Drive-Query nicht unbegrenzt lang werden lassen


def search_root_ids(svc, folder_id: str) -> list[str]:
    """Suchwurzeln bestimmen: konfigurierter Ordner + der Ordner „Google Meet".

    Seit Googles Drive-Umbau (Rapid Release 22.07.2026 / Scheduled 30.07.2026) legt
    Meet Aufzeichnungen in `Google Meet/<Meeting>/` ab; der alte Ordner `Meet Recordings`
    wird dorthin verschoben und in `Legacy Meet Recordings` umbenannt — laut Google
    existieren beide während der Umstellung aber eine Weile NEBENEINANDER. Genau dieser
    Zustand liegt bei Nora vor: die Historie liegt weiter im konfigurierten Ordner, neue
    Aufzeichnungen ausschließlich unter `Google Meet`.

    Deshalb immer beide Wurzeln durchsuchen. Der Meet-Ordner wird über den exakten Namen
    in „Meine Ablage" aufgelöst — nie über die Wurzel selbst, sonst würden wir das ganze
    Drive scannen. Findet sich keiner, bleibt es beim konfigurierten Ordner.
    """
    roots = [folder_id]
    try:
        q = (f"'root' in parents and trashed = false and mimeType = '{_FOLDER_MIME}' "
             f"and name = '{_MEET_ROOT_FOLDER_NAME}'")
        roots.extend(f["id"] for f in _list_all(svc, q, "id") if f["id"] != folder_id)
    except Exception as e:  # Auflösung ist Kür — im Zweifel wie bisher nur der Ordner
        logger.warning(f"Drive: Ordner „{_MEET_ROOT_FOLDER_NAME}\" nicht auflösbar: {e}")
    return roots


def _folder_tree_ids(svc, root_ids: list[str]) -> list[str]:
    """Wurzeln + alle Unterordner (breadth-first, tiefen-/mengenbegrenzt)."""
    ids = list(dict.fromkeys(root_ids))
    frontier = list(ids)
    for _ in range(_MAX_FOLDER_DEPTH):
        children: list[str] = []
        for chunk in _chunks(frontier, _PARENTS_PER_QUERY):
            q = f"({_parents_clause(chunk)}) and trashed = false and mimeType = '{_FOLDER_MIME}'"
            children.extend(f["id"] for f in _list_all(svc, q, "id"))
        frontier = [fid for fid in dict.fromkeys(children) if fid not in ids]
        if not frontier:
            break
        ids.extend(frontier)
        if len(ids) >= _MAX_FOLDERS:
            logger.warning(f"Drive: Ordner-Limit {_MAX_FOLDERS} erreicht, Baum abgeschnitten")
            return ids[:_MAX_FOLDERS]
    return ids


def _chunks(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _parents_clause(folder_ids: list[str]) -> str:
    return " or ".join(f"'{fid}' in parents" for fid in folder_ids)


def _list_all(svc, q: str, file_fields: str) -> list[dict]:
    """files.list mit Paging bis zum Ende."""
    out, page_token = [], None
    while True:
        resp = svc.files().list(
            q=q,
            fields=f"nextPageToken, files({file_fields})",
            pageSize=100, pageToken=page_token,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        out.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            return out


def list_video_files(folder_id: str, name_prefix: str, modified_after_iso: str) -> list[dict]:
    """Video-Dateien im Ordnerbaum mit Name-Prefix, geändert nach modified_after_iso.
    Gibt [{id,name,mimeType,size,modifiedTime,createdTime}]. Echten Prefix clientseitig
    prüfen, da Drive 'name contains' nur als Teilstring kann."""
    svc = _service()
    folders = _folder_tree_ids(svc, search_root_ids(svc, folder_id))
    files: dict[str, dict] = {}
    for chunk in _chunks(folders, _PARENTS_PER_QUERY):
        q = (
            f"({_parents_clause(chunk)}) and trashed = false "
            f"and mimeType contains 'video/' "
            f"and modifiedTime > '{modified_after_iso}'"
        )
        for f in _list_all(svc, q, "id,name,mimeType,size,modifiedTime,createdTime"):
            files[f["id"]] = f
    return [f for f in files.values() if f["name"].startswith(name_prefix)]


def download_to_file(file_id: str, dest_path: str) -> None:
    """Chunked-Download auf die Platte (kein RAM-Blowup bei ~1 GB)."""
    svc = _service()
    request = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
