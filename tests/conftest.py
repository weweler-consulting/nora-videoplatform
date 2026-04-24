import asyncio
import os
from pathlib import Path
from typing import Optional

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Force SQLite in-memory before importing app
os.environ["NORA_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["NORA_SECRET_KEY"] = "test-secret-key-at-least-32-characters-long-xxxx"
os.environ["NORA_CORS_ORIGINS"] = "http://localhost:5173"

from app.core import db as db_module  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Patch the app's engine + session factory
    db_module.engine = eng
    db_module.async_session = async_sessionmaker(eng, expire_on_commit=False)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    async with db_module.async_session() as s:
        yield s


@pytest_asyncio.fixture
async def client(engine, tmp_path, monkeypatch):
    # Redirect file storage under tmp_path so tests are isolated
    monkeypatch.setenv("HUB_STORAGE_DIR", str(tmp_path / "hub"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
