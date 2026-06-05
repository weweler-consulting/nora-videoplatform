import pytest
from sqlalchemy import select as _select

from app.models.live_call import LiveCallSeries, LiveCallImport
from app.models.course import Course


@pytest.mark.asyncio
async def test_series_and_import_roundtrip(session):
    course = Course(title="4-Wochen Code", is_active=True)
    session.add(course)
    await session.commit()

    series = LiveCallSeries(course_id=course.id, recording_name_prefix="4-Wochen Glukose Balance Code Live Call")
    session.add(series)
    await session.commit()

    imp = LiveCallImport(
        series_id=series.id, drive_file_id="drive-123",
        recording_name="4-Wochen Glukose Balance Code Live Call - 2026/10/02 19:14 WEST - Recording",
        status="new",
    )
    session.add(imp)
    await session.commit()

    row = (await session.execute(_select(LiveCallImport).where(LiveCallImport.drive_file_id == "drive-123"))).scalar_one()
    assert row.status == "new"
    assert row.series_id == series.id
    assert row.lesson_id is None and row.retry_count == 0
