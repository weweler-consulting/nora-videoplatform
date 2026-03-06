from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.db import engine, Base
from app.api import auth, courses, modules, sections, lessons, users, progress


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
