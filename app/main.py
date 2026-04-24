import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from sqlalchemy import text
from app.core.db import engine, Base
from app.core.drip_notifier import drip_notifier_loop
from app.core.ratelimit import limiter
from app.api import auth, courses, hub, modules, sections, lessons, users, progress, upload, dashboard, stripe_webhook, attachments, integrations
from app.models import hub as _hub_models  # noqa: F401 — register Hub tables with Base
from sqlalchemy import select

logger = logging.getLogger(__name__)

HUB_DOWNLOADS_DIR = Path(os.environ.get("HUB_STORAGE_DIR", "/app/data/hub_downloads"))
if not HUB_DOWNLOADS_DIR.parent.exists():
    HUB_DOWNLOADS_DIR = Path(__file__).parent.parent / "data" / "hub_downloads"

_FK_CASCADES = [
    ("modules", "course_id", "courses"),
    ("sections", "module_id", "modules"),
    ("lessons", "section_id", "sections"),
    ("enrollments", "user_id", "users"),
    ("enrollments", "course_id", "courses"),
    ("drip_notifications", "user_id", "users"),
    ("drip_notifications", "module_id", "modules"),
    ("module_unlocks", "user_id", "users"),
    ("module_unlocks", "module_id", "modules"),
    ("lesson_attachments", "lesson_id", "lessons"),
    ("lesson_progress", "user_id", "users"),
    ("lesson_progress", "lesson_id", "lessons"),
]


def _build_migration_statements() -> list[str]:
    stmts = [
        "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL",
        "ALTER TABLE users ADD COLUMN reset_token VARCHAR",
        "ALTER TABLE users ADD COLUMN reset_token_expires TIMESTAMP",
        "ALTER TABLE users ADD COLUMN invite_token VARCHAR",
        "ALTER TABLE users ADD COLUMN invite_token_expires TIMESTAMP",
        "ALTER TABLE users ADD COLUMN invite_accepted_at TIMESTAMP",
        "ALTER TABLE users ADD COLUMN terms_accepted_at TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS ix_users_invite_token ON users (invite_token)",
        "CREATE INDEX IF NOT EXISTS ix_users_reset_token ON users (reset_token)",
        "ALTER TABLE modules ADD COLUMN unlock_after_days INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE courses ADD COLUMN stripe_product_id VARCHAR",
    ]
    # Re-create FK constraints with ON DELETE CASCADE (A3 from audit)
    for child, col, parent in _FK_CASCADES:
        fk_name = f"{child}_{col}_fkey"
        stmts.append(f'ALTER TABLE {child} DROP CONSTRAINT IF EXISTS {fk_name}')
        stmts.append(
            f'ALTER TABLE {child} ADD CONSTRAINT {fk_name} '
            f'FOREIGN KEY ({col}) REFERENCES {parent}(id) ON DELETE CASCADE'
        )
    # Unique constraints via unique indexes (A4 from audit)
    stmts += [
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_enrollment_user_course ON enrollments (user_id, course_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_drip_user_module ON drip_notifications (user_id, module_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_module_unlock_user_module ON module_unlocks (user_id, module_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_progress_user_lesson ON lesson_progress (user_id, lesson_id)",
    ]
    # Helpful indexes on FKs used in frequent queries
    for child, col, _ in _FK_CASCADES:
        stmts.append(f"CREATE INDEX IF NOT EXISTS ix_{child}_{col} ON {child} ({col})")
    return stmts


async def _backfill_course_hubs() -> None:
    """Ensure every Course has a CourseHub row (idempotent via unique constraint)."""
    async with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            result = await conn.execute(text(
                "INSERT INTO course_hubs (id, course_id, hero_variant, hero_eyebrow, "
                "hero_title_html, hero_body, contact_role, show_contact, show_live_calls, "
                "show_products, show_downloads, updated_at) "
                "SELECT lower(hex(randomblob(16))), c.id, 'berry', '', '', '', "
                "'Kursleitung & Ernährungsberaterin', 1, 1, 1, 1, CURRENT_TIMESTAMP "
                "FROM courses c WHERE NOT EXISTS "
                "(SELECT 1 FROM course_hubs h WHERE h.course_id = c.id)"
            ))
        else:
            result = await conn.execute(text(
                "INSERT INTO course_hubs (id, course_id, hero_variant, hero_eyebrow, "
                "hero_title_html, hero_body, contact_role, show_contact, show_live_calls, "
                "show_products, show_downloads, updated_at) "
                "SELECT gen_random_uuid()::text, c.id, 'berry', '', '', '', "
                "'Kursleitung & Ernährungsberaterin', TRUE, TRUE, TRUE, TRUE, NOW() "
                "FROM courses c WHERE NOT EXISTS "
                "(SELECT 1 FROM course_hubs h WHERE h.course_id = c.id)"
            ))
        logger.info(f"Hub backfill: {result.rowcount} hubs created")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Ad-hoc migrations (no Alembic). Each in its own transaction — PostgreSQL
    # aborts the whole txn on DDL error. Benign "already exists" errors are
    # silently swallowed; everything else is logged so Nora sees real problems.
    for stmt in _build_migration_statements():
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception as e:
            msg = str(e).lower()
            if "already exists" in msg or "duplicate" in msg:
                continue
            logger.warning(f"Migration step failed: {stmt[:100]}... — {e}")
    # Ensure hub download storage exists
    HUB_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    # Backfill: every existing Course gets an empty CourseHub
    try:
        await _backfill_course_hubs()
    except Exception as e:
        logger.warning(f"Hub backfill failed: {e}")
    task = asyncio.create_task(drip_notifier_loop())
    yield
    task.cancel()


app = FastAPI(title="Nora Videoplatform API", version="0.1.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_cors_env = os.environ.get("NORA_CORS_ORIGINS", "https://kose.noraweweler.de,https://kurse.noraweweler.de")
CORS_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
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
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(stripe_webhook.router, prefix="/api/v1/stripe", tags=["stripe"])
app.include_router(attachments.router, prefix="/api/v1", tags=["attachments"])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["integrations"])
app.include_router(hub.router, prefix="/api/v1/courses", tags=["hub"])


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
