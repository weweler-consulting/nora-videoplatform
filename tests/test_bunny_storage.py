import pytest
from unittest.mock import AsyncMock, patch

from app.integrations.bunny_storage import upload_image, BunnyNotConfigured


@pytest.mark.asyncio
async def test_upload_image_raises_when_not_configured(monkeypatch):
    monkeypatch.delenv("BUNNY_STORAGE_ZONE", raising=False)
    monkeypatch.delenv("BUNNY_STORAGE_KEY", raising=False)
    with pytest.raises(BunnyNotConfigured):
        await upload_image(b"x", course_id="c1", kind="product", filename="a.jpg")


@pytest.mark.asyncio
async def test_upload_image_returns_cdn_url(monkeypatch):
    monkeypatch.setenv("BUNNY_STORAGE_ZONE", "test-zone")
    monkeypatch.setenv("BUNNY_STORAGE_KEY", "k")
    monkeypatch.setenv("BUNNY_STORAGE_PULL_ZONE", "https://test.b-cdn.net")

    mock_resp = AsyncMock()
    mock_resp.status_code = 201
    with patch("httpx.AsyncClient.put", return_value=mock_resp):
        url = await upload_image(b"data", course_id="c1", kind="product", filename="x.jpg")
    assert url.startswith("https://test.b-cdn.net/hub/c1/product/")
    assert url.endswith(".jpg")
