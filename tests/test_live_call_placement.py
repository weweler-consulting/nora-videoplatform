import pytest
from datetime import datetime
from sqlalchemy import select as _select

from app.models.course import Course, Module, Section, Lesson
from app.core.live_call_placement import resolve_target_section


@pytest.mark.asyncio
async def test_fills_dated_placeholder(session):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    placeholder = Module(course_id=course.id, title="Live Call 02.10.2026", sort_order=5)
    session.add(placeholder); await session.commit()

    section_id, module_id = await resolve_target_section(session, course.id, datetime(2026, 10, 2, 19, 14))
    assert module_id == placeholder.id  # Datum traf den Platzhalter
    sec = (await session.execute(_select(Section).where(Section.id == section_id))).scalar_one()
    assert sec.module_id == placeholder.id


@pytest.mark.asyncio
async def test_creates_new_module_when_no_placeholder(session):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    other = Module(course_id=course.id, title="Modul 1", sort_order=0); session.add(other); await session.commit()

    section_id, module_id = await resolve_target_section(session, course.id, datetime(2026, 10, 9, 19, 14))
    new_mod = (await session.execute(_select(Module).where(Module.id == module_id))).scalar_one()
    assert new_mod.title == "Live Call 09.10.2026"
    assert new_mod.sort_order == 1  # max(0)+1


@pytest.mark.asyncio
async def test_placeholder_with_video_lesson_is_not_reused(session):
    course = Course(title="K", is_active=True); session.add(course); await session.commit()
    mod = Module(course_id=course.id, title="Live Call 02.10.2026", sort_order=0); session.add(mod); await session.commit()
    sec = Section(module_id=mod.id, title="S", sort_order=0); session.add(sec); await session.commit()
    session.add(Lesson(section_id=sec.id, title="schon da", type="video", video_url="x", sort_order=0))
    await session.commit()

    _section_id, module_id = await resolve_target_section(session, course.id, datetime(2026, 10, 2, 19, 14))
    assert module_id != mod.id  # belegter Platzhalter → neues Modul
