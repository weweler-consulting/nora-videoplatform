import hashlib
import os
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import require_admin
from app.models.user import User

router = APIRouter()

BUNNY_API_KEY = os.environ.get("BUNNY_API_KEY", "")
BUNNY_LIBRARY_ID = os.environ.get("BUNNY_LIBRARY_ID", "")


class CreateVideoRequest(BaseModel):
    title: str
    library_id: str | None = None


@router.post("/create-video")
async def create_video(data: CreateVideoRequest, admin: User = Depends(require_admin)):
    library_id = data.library_id or BUNNY_LIBRARY_ID
    api_key = BUNNY_API_KEY

    if not api_key or not library_id:
        raise HTTPException(status_code=500, detail="Bunny.net nicht konfiguriert")

    # Create video in Bunny Stream
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://video.bunnycdn.com/library/{library_id}/videos",
            headers={"AccessKey": api_key, "Content-Type": "application/json"},
            json={"title": data.title},
        )
        if resp.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail=f"Bunny API error: {resp.text}")

    video = resp.json()
    video_id = video["guid"]

    # Generate TUS upload auth
    expiration = int(time.time()) + 3600  # 1 hour
    signature_raw = f"{library_id}{api_key}{expiration}{video_id}"
    signature = hashlib.sha256(signature_raw.encode()).hexdigest()

    embed_url = f"https://iframe.mediadelivery.net/embed/{library_id}/{video_id}"

    return {
        "video_id": video_id,
        "library_id": library_id,
        "tus_endpoint": "https://video.bunnycdn.com/tusupload",
        "auth_signature": signature,
        "auth_expiration": expiration,
        "embed_url": embed_url,
    }


class DeleteVideoRequest(BaseModel):
    embed_url: str


@router.post("/delete-video")
async def delete_video(data: DeleteVideoRequest, admin: User = Depends(require_admin)):
    """Delete a video from Bunny.net by its embed URL."""
    api_key = BUNNY_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="Bunny.net nicht konfiguriert")

    # Parse library_id and video_id from embed URL
    # Format: https://iframe.mediadelivery.net/embed/{libraryId}/{videoId}
    try:
        parts = data.embed_url.rstrip("/").split("/")
        video_id = parts[-1]
        library_id = parts[-2]
    except (IndexError, ValueError):
        raise HTTPException(status_code=400, detail="Ungültige Video-URL")

    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"https://video.bunnycdn.com/library/{library_id}/videos/{video_id}",
            headers={"AccessKey": api_key},
        )
        if resp.status_code not in (200, 204):
            raise HTTPException(status_code=502, detail=f"Bunny API error: {resp.text}")

    return {"ok": True}
