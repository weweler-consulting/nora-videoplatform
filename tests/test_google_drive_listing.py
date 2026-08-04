"""Drive-Listing über den Ordnerbaum.

Hintergrund: seit Googles Drive-Umbau (Juli 2026) landen Meet-Aufzeichnungen in
`Google Meet/<Meeting>/`, während die Historie noch im alten, separat daneben
liegenden Ordner steht (Google migriert schrittweise, beide existieren parallel).
Ein flaches `'<id>' in parents` auf den konfigurierten Ordner findet neue
Aufzeichnungen deshalb nie.
"""
import pytest

from app.integrations import google_drive


LEGACY = "legacy-folder-id"      # konfigurierter Ordner (NORA_MEET_RECORDINGS_FOLDER_ID)
MEET_ROOT = "google-meet-folder-id"
MEETING_SUB = "meeting-subfolder-id"

NEW_RECORDING = {
    "id": "vid-neu", "name": "Live Call 4 Wochen Glukose Balance Code (Start Aug 2026) - 2026/08/04 10:59 WEST – Recording",
    "mimeType": "video/mp4", "size": "123", "modifiedTime": "2026-08-04T09:59:00Z",
    "createdTime": "2026-08-04T09:59:00Z",
}
OLD_RECORDING = {
    "id": "vid-alt", "name": "Live Call | Glukose Balance - 2026/07/01 - Recording",
    "mimeType": "video/mp4", "size": "123", "modifiedTime": "2026-07-30T17:00:00Z",
    "createdTime": "2026-07-01T17:00:00Z",
}
FREMD = {
    "id": "vid-fremd", "name": "Urlaubsvideo",
    "mimeType": "video/mp4", "size": "1", "modifiedTime": "2026-08-01T10:00:00Z",
    "createdTime": "2026-08-01T10:00:00Z",
}

FOLDER_MIME = "application/vnd.google-apps.folder"


class _FakeDrive:
    """Minimaler Drive-Stub: Ordner je Elternordner + Dateien je Elternordner."""

    def __init__(self, subfolders: dict, videos: dict, meet_root: str | None = MEET_ROOT):
        self._subfolders, self._videos, self._meet_root = subfolders, videos, meet_root
        self.queries: list[str] = []

    def files(self):  # googleapiclient-Form: svc.files().list(...).execute()
        return self

    def list(self, q, fields, pageSize, pageToken, supportsAllDrives, includeItemsFromAllDrives):
        self.queries.append(q)
        if "'root' in parents" in q:
            return _Exec({"files": [{"id": self._meet_root}] if self._meet_root else []})
        parents = {p.split("'")[1] for p in q.split(" or ") if "in parents" in p}
        source = self._subfolders if f"mimeType = '{FOLDER_MIME}'" in q else self._videos
        return _Exec({"files": [item for parent in parents for item in source.get(parent, [])]})


class _Exec:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


@pytest.fixture
def drive(monkeypatch):
    """Noras realer Zustand: Legacy-Ordner UND 'Google Meet' liegen nebeneinander."""
    svc = _FakeDrive(
        subfolders={MEET_ROOT: [{"id": MEETING_SUB}]},
        videos={LEGACY: [OLD_RECORDING], MEETING_SUB: [NEW_RECORDING], MEET_ROOT: [FREMD]},
    )
    monkeypatch.setattr(google_drive, "_service", lambda: svc)
    return svc


def test_findet_aufzeichnung_im_neuen_meeting_unterordner(drive):
    files = google_drive.list_video_files(
        LEGACY, "Live Call 4 Wochen Glukose Balance Code (Start Aug 2026)", "2026-07-20T00:00:00Z"
    )
    assert [f["id"] for f in files] == ["vid-neu"]


def test_historie_im_konfigurierten_ordner_bleibt_auffindbar(drive):
    files = google_drive.list_video_files(LEGACY, "Live Call | Glukose Balance", "2026-07-20T00:00:00Z")
    assert [f["id"] for f in files] == ["vid-alt"]


def test_prefix_filter_schliesst_fremde_videos_aus(drive):
    files = google_drive.list_video_files(LEGACY, "Live Call", "2026-07-20T00:00:00Z")
    assert {f["id"] for f in files} == {"vid-neu", "vid-alt"}


def test_legacy_ordner_unterhalb_google_meet_wird_nicht_doppelt_gelistet(monkeypatch):
    """Nach der Migration hängt der konfigurierte Ordner IM 'Google Meet'-Ordner —
    dann darf dieselbe Datei nicht doppelt auftauchen."""
    svc = _FakeDrive(
        subfolders={MEET_ROOT: [{"id": LEGACY}, {"id": MEETING_SUB}]},
        videos={LEGACY: [OLD_RECORDING], MEETING_SUB: [NEW_RECORDING]},
    )
    monkeypatch.setattr(google_drive, "_service", lambda: svc)
    files = google_drive.list_video_files(LEGACY, "Live Call", "2026-07-20T00:00:00Z")
    assert sorted(f["id"] for f in files) == ["vid-alt", "vid-neu"]


def test_ohne_google_meet_ordner_bleibt_es_beim_konfigurierten_ordner(monkeypatch):
    """Zustand vor der Umstellung: nur der alte Ordner existiert."""
    svc = _FakeDrive(subfolders={}, videos={LEGACY: [OLD_RECORDING]}, meet_root=None)
    monkeypatch.setattr(google_drive, "_service", lambda: svc)
    files = google_drive.list_video_files(LEGACY, "Live Call | Glukose Balance", "2026-07-20T00:00:00Z")
    assert [f["id"] for f in files] == ["vid-alt"]


def test_meet_ordner_wird_nie_ueber_die_drive_wurzel_gesucht(drive):
    """'root' darf nur zum Auflösen des Meet-Ordners dienen, nie als Suchwurzel —
    sonst würde das komplette Drive gescannt."""
    google_drive.list_video_files(LEGACY, "Live Call", "2026-07-20T00:00:00Z")
    video_queries = [q for q in drive.queries if "video/" in q]
    assert video_queries and all("'root' in parents" not in q for q in video_queries)


def test_drive_fehler_beim_aufloesen_killt_das_listing_nicht(monkeypatch):
    class _Broken(_FakeDrive):
        def list(self, q, **kw):
            if "'root' in parents" in q:
                raise RuntimeError("Drive kaputt")
            return super().list(q, **kw)

    svc = _Broken(subfolders={}, videos={LEGACY: [OLD_RECORDING]})
    monkeypatch.setattr(google_drive, "_service", lambda: svc)
    files = google_drive.list_video_files(LEGACY, "Live Call | Glukose Balance", "2026-07-20T00:00:00Z")
    assert [f["id"] for f in files] == ["vid-alt"]
