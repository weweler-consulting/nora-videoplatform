"""Drive-Listing über den Ordnerbaum.

Hintergrund: seit Googles Drive-Umbau (Juli 2026) landen Meet-Aufzeichnungen in
`Google Meet/<Meeting>/`; der alte Ordner wurde dorthin verschoben und in
`Legacy Meet Recordings` umbenannt (ID unverändert). Ein flaches
`'<id>' in parents` findet neue Aufzeichnungen deshalb nie mehr.
"""
import pytest

from app.integrations import google_drive


LEGACY = "legacy-folder-id"
MEET_ROOT = "google-meet-folder-id"
MEETING_SUB = "meeting-subfolder-id"

NEW_RECORDING = {
    "id": "vid-neu", "name": "Live Call 4 Wochen Glukose Balance Code (Start Aug 2026) - 2026/08/04 - Recording",
    "mimeType": "video/mp4", "size": "123", "modifiedTime": "2026-08-04T17:00:00Z",
    "createdTime": "2026-08-04T17:00:00Z",
}
OLD_RECORDING = {
    "id": "vid-alt", "name": "Live Call | Glukose Balance - 2026/07/30 - Recording",
    "mimeType": "video/mp4", "size": "123", "modifiedTime": "2026-07-30T17:00:00Z",
    "createdTime": "2026-07-30T17:00:00Z",
}
FREMD = {
    "id": "vid-fremd", "name": "Urlaubsvideo",
    "mimeType": "video/mp4", "size": "1", "modifiedTime": "2026-08-01T10:00:00Z",
    "createdTime": "2026-08-01T10:00:00Z",
}

FOLDER_MIME = "application/vnd.google-apps.folder"


class _FakeDrive:
    """Minimaler Drive-Stub: Ordnerbaum + Dateien pro Elternordner."""

    def __init__(self, meta: dict, subfolders: dict, videos: dict):
        self._meta, self._subfolders, self._videos = meta, subfolders, videos
        self.queries: list[str] = []

    # --- googleapiclient-Form: svc.files().get(...).execute()
    def files(self):
        return self

    def get(self, fileId, fields, supportsAllDrives=False):
        if fileId not in self._meta:
            raise KeyError(fileId)
        return _Exec(self._meta[fileId])

    def list(self, q, fields, pageSize, pageToken, supportsAllDrives, includeItemsFromAllDrives):
        self.queries.append(q)
        parents = {p.split("'")[1] for p in q.split(" or ") if "in parents" in p}
        source = self._subfolders if f"mimeType = '{FOLDER_MIME}'" in q else self._videos
        out = [item for parent in parents for item in source.get(parent, [])]
        return _Exec({"files": out})


class _Exec:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


def _fake_drive() -> _FakeDrive:
    return _FakeDrive(
        meta={
            LEGACY: {"parents": [MEET_ROOT]},
            MEET_ROOT: {"id": MEET_ROOT, "name": "Google Meet", "mimeType": FOLDER_MIME},
        },
        subfolders={
            MEET_ROOT: [{"id": LEGACY}, {"id": MEETING_SUB}],
        },
        videos={
            MEET_ROOT: [FREMD],
            LEGACY: [OLD_RECORDING],
            MEETING_SUB: [NEW_RECORDING],
        },
    )


@pytest.fixture
def drive(monkeypatch):
    svc = _fake_drive()
    monkeypatch.setattr(google_drive, "_service", lambda: svc)
    return svc


def test_findet_aufzeichnung_im_neuen_meeting_unterordner(drive):
    files = google_drive.list_video_files(
        LEGACY, "Live Call 4 Wochen Glukose Balance Code (Start Aug 2026)", "2026-07-20T00:00:00Z"
    )
    assert [f["id"] for f in files] == ["vid-neu"]


def test_historie_im_legacy_ordner_bleibt_auffindbar(drive):
    files = google_drive.list_video_files(LEGACY, "Live Call | Glukose Balance", "2026-07-20T00:00:00Z")
    assert [f["id"] for f in files] == ["vid-alt"]


def test_prefix_filter_schliesst_fremde_videos_aus(drive):
    files = google_drive.list_video_files(LEGACY, "Live Call", "2026-07-20T00:00:00Z")
    assert {f["id"] for f in files} == {"vid-neu", "vid-alt"}


def test_ohne_google_meet_eltern_bleibt_konfigurierter_ordner_die_wurzel(monkeypatch):
    """Zustand vor der Migration: Elternordner ist 'Meine Ablage' → nicht hochlaufen,
    sonst würde das ganze Drive gescannt."""
    svc = _FakeDrive(
        meta={LEGACY: {"parents": ["root-id"]},
              "root-id": {"id": "root-id", "name": "Meine Ablage", "mimeType": FOLDER_MIME}},
        subfolders={},
        videos={LEGACY: [OLD_RECORDING], "root-id": [FREMD]},
    )
    monkeypatch.setattr(google_drive, "_service", lambda: svc)
    files = google_drive.list_video_files(LEGACY, "Live Call | Glukose Balance", "2026-07-20T00:00:00Z")
    assert [f["id"] for f in files] == ["vid-alt"]
    assert all("root-id" not in q for q in svc.queries)


def test_unaufloesbarer_elternordner_faellt_auf_konfigurierten_ordner_zurueck(monkeypatch):
    """Drive-Fehler beim Auflösen darf das Listing nicht killen."""
    svc = _FakeDrive(meta={}, subfolders={}, videos={LEGACY: [OLD_RECORDING]})
    monkeypatch.setattr(google_drive, "_service", lambda: svc)
    files = google_drive.list_video_files(LEGACY, "Live Call | Glukose Balance", "2026-07-20T00:00:00Z")
    assert [f["id"] for f in files] == ["vid-alt"]
