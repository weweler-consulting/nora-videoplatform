import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from sqlalchemy import text
from app.core.db import engine, Base
from app.api import auth, courses, modules, sections, lessons, users, progress, upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Add columns if missing (no Alembic migrations)
    # Each in its own transaction — PostgreSQL aborts the whole txn on DDL error
    for stmt in [
        "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL",
        "ALTER TABLE users ADD COLUMN reset_token VARCHAR",
        "ALTER TABLE users ADD COLUMN reset_token_expires TIMESTAMP",
        "ALTER TABLE modules ADD COLUMN unlock_after_days INTEGER DEFAULT 0 NOT NULL",
    ]:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception:
            pass  # Column already exists
    yield


app = FastAPI(title="Nora Videoplatform API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(courses.router, prefix="/api/v1/courses", tags=["courses"])
app.include_router(modules.router, prefix="/api/v1/modules", tags=["modules"])
app.include_router(sections.router, prefix="/api/v1/sections", tags=["sections"])
app.include_router(lessons.router, prefix="/api/v1/lessons", tags=["lessons"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(progress.router, prefix="/api/v1/progress", tags=["progress"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


# Serve frontend static files in production
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static")

    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
