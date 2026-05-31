import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.db as db_module
import app.core.drip_notifier as drip
from app.core.auth import hash_password
from app.core.time import utc_now
from app.models.course import Course, Module, Enrollment, DripNotification
from app.models.user import User


@pytest.fixture
def patched_drip_session(engine, monkeypatch):
    # drip_notifier did `from app.core.db import async_session` at import time, so it
    # holds the original factory. Repoint it at the test engine's patched factory.
    monkeypatch.setattr(drip, "async_session", db_module.async_session)


async def _setup(session: AsyncSession, *, hashed_password: str) -> tuple[User, Module]:
    user = User(
        email=f"{uuid.uuid4().hex}@example.com", name="Kundin",
        hashed_password=hashed_password, is_admin=False, is_active=True,
    )
    course = Course(title="4-Wochen", is_active=True)
    session.add_all([user, course])
    await session.flush()
    module = Module(course_id=course.id, title="Modul 2", unlock_after_days=1, sort_order=1)
    session.add(module)
    # enrolled 2 days ago -> module (unlock_after_days=1) unlocked ~1 day ago (within 48h)
    session.add(Enrollment(
        user_id=user.id, course_id=course.id,
        enrolled_at=utc_now() - timedelta(days=2),
    ))
    await session.commit()
    return user, module


async def _drip_count(session: AsyncSession, user_id: str) -> int:
    res = await session.execute(
        select(DripNotification).where(DripNotification.user_id == user_id)
    )
    return len(res.scalars().all())


@pytest.mark.asyncio
async def test_drip_skips_users_who_cannot_log_in(patched_drip_session, session, monkeypatch):
    """Invited/Stripe users (empty password) must not get drip mails yet."""
    calls = []
    monkeypatch.setattr(drip, "send_module_unlocked_email",
                        lambda **kw: calls.append(kw) or True)
    user, _ = await _setup(session, hashed_password="")

    await drip.check_drip_notifications()

    assert calls == []
    assert await _drip_count(session, user.id) == 0


@pytest.mark.asyncio
async def test_drip_sends_to_active_users(patched_drip_session, session, monkeypatch):
    calls = []
    monkeypatch.setattr(drip, "send_module_unlocked_email",
                        lambda **kw: calls.append(kw) or True)
    user, _ = await _setup(session, hashed_password=hash_password("pw"))

    await drip.check_drip_notifications()

    assert len(calls) == 1
    assert await _drip_count(session, user.id) == 1


@pytest.mark.asyncio
async def test_drip_does_not_mark_sent_when_mail_fails(patched_drip_session, session, monkeypatch):
    """send helper returns False (mail not configured) -> no dedup row, retry later."""
    monkeypatch.setattr(drip, "send_module_unlocked_email", lambda **kw: False)
    user, _ = await _setup(session, hashed_password=hash_password("pw"))

    await drip.check_drip_notifications()

    assert await _drip_count(session, user.id) == 0
