"""Bunny Storage client for hub uploads (product images, contact photos).

The production Bunny Storage zone is separate from the video streaming zone
used by `app/api/upload.py`. Env vars:
  BUNNY_STORAGE_ZONE      — zone name, e.g. "noraweweler-hub"
  BUNNY_STORAGE_KEY       — storage-zone access key (NOT the stream API key)
  BUNNY_STORAGE_PULL_ZONE — pull-zone URL, e.g. "https://nw-hub.b-cdn.net"

If any of these are unset, BunnyNotConfigured is raised so the API layer can
surface a clean 503 to the admin form.
"""
import os
import uuid
from pathlib import Path

import httpx


class BunnyNotConfigured(RuntimeError):
    pass


def _require_env() -> tuple[str, str, str]:
    zone = os.environ.get("BUNNY_STORAGE_ZONE", "")
    key = os.environ.get("BUNNY_STORAGE_KEY", "")
    pull = os.environ.get("BUNNY_STORAGE_PULL_ZONE", "").rstrip("/")
    if not (zone and key and pull):
        raise BunnyNotConfigured(
            "Bunny Storage not configured. Set BUNNY_STORAGE_ZONE, "
            "BUNNY_STORAGE_KEY, BUNNY_STORAGE_PULL_ZONE."
        )
    return zone, key, pull


async def upload_image(file_bytes: bytes, *, course_id: str, kind: str, filename: str) -> str:
    """Upload bytes to Bunny Storage, return the public CDN URL.

    Path scheme: /hub/{course_id}/{kind}/{uuid}.{ext}
    `kind` is usually "product" or "contact_photo".
    """
    zone, key, pull = _require_env()
    ext = Path(filename).suffix.lower() or ".bin"
    object_path = f"hub/{course_id}/{kind}/{uuid.uuid4().hex}{ext}"
    url = f"https://storage.bunnycdn.com/{zone}/{object_path}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.put(
            url,
            headers={"AccessKey": key, "Content-Type": "application/octet-stream"},
            content=file_bytes,
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Bunny upload failed: {resp.status_code} {resp.text}")

    return f"{pull}/{object_path}"


async def delete_image(cdn_url: str) -> None:
    """Best-effort delete of a previously uploaded image. Errors are swallowed
    because a dangling CDN file is not worth blocking a save."""
    try:
        zone, key, pull = _require_env()
    except BunnyNotConfigured:
        return
    if not cdn_url.startswith(pull + "/"):
        return
    object_path = cdn_url[len(pull) + 1:]
    url = f"https://storage.bunnycdn.com/{zone}/{object_path}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            await client.delete(url, headers={"AccessKey": key})
        except httpx.HTTPError:
            return
