import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.time import utc_now


class LiveCallSeries(Base):
    """Verknüpfung Recording-Namen-Prefix → Kurs (1:1). Einmal pro Kurs/Kohorte
    im Admin gesetzt. Der Prefix ist der Namensteil VOR dem Datum."""
    __tablename__ = "live_call_series"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id: Mapped[str] = mapped_column(String, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    recording_name_prefix: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class LiveCallImport(Base):
    """Ein erkanntes Recording + sein Import-/Freigabe-Zustand. drive_file_id ist
    der Dedup-Schlüssel (ein Recording = eine Zeile, egal wie oft der Loop läuft)."""
    __tablename__ = "live_call_imports"
    __table_args__ = (UniqueConstraint("drive_file_id", name="uq_live_call_drive_file"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id: Mapped[str] = mapped_column(String, ForeignKey("live_call_series.id", ondelete="CASCADE"), nullable=False, index=True)
    drive_file_id: Mapped[str] = mapped_column(String, nullable=False)
    recording_name: Mapped[str] = mapped_column(String, nullable=False)
    occurrence_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    module_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lesson_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # 'new' | 'imported' | 'published' | 'dismissed' | 'failed'
    status: Mapped[str] = mapped_column(String, nullable=False, default="new", server_default="new")
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
