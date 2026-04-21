"""Seed script: creates the initial admin user on an empty database.

Runs on first start via start.sh. Safe to re-run — exits cleanly if the
database already contains users, so no existing data is ever overwritten.
"""
import asyncio
import os

from sqlalchemy import select

from app.core.db import engine, Base, async_session
from app.core.auth import hash_password
from app.models.user import User


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    admin_email = os.environ.get("NORA_ADMIN_EMAIL")
    admin_name = os.environ.get("NORA_ADMIN_NAME", "Admin")
    admin_password = os.environ.get("NORA_ADMIN_PASSWORD")

    async with async_session() as db:
        existing = await db.execute(select(User).limit(1))
        if existing.scalar_one_or_none():
            print("Seed: users already exist, skipping.")
            return

        if not admin_email or not admin_password:
            print(
                "Seed: NORA_ADMIN_EMAIL and NORA_ADMIN_PASSWORD not set — "
                "skipping admin creation. Set them and restart to bootstrap an admin."
            )
            return

        if len(admin_password) < 8:
            print("Seed: NORA_ADMIN_PASSWORD must be at least 8 characters — skipping.")
            return

        admin = User(
            email=admin_email,
            name=admin_name,
            hashed_password=hash_password(admin_password),
            is_admin=True,
        )
        db.add(admin)
        await db.commit()
        print(f"Seed: created admin user {admin_email}")


if __name__ == "__main__":
    asyncio.run(seed())
