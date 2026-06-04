import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.time import utc_now


class CheckinTemplate(Base):
    """Editierbares Check-In-Formular. typ unterscheidet 'start' (Bestandsaufnahme),
    'laufend' (wöchentlich) und 'ende' (vorerst nur Schema, nicht ausgebaut)."""
    __tablename__ = "checkin_templates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    typ: Mapped[str] = mapped_column(String, nullable=False)  # 'start' | 'laufend' | 'ende'
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    steps = relationship(
        "CheckinStep",
        back_populates="template",
        order_by="CheckinStep.sort_order",
        cascade="all, delete-orphan",
    )


class CheckinStep(Base):
    """Eine Frage/ein Schritt eines Templates. key ist stabil über alle Wochen
    hinweg → spätere Vergleichbarkeit der Antworten."""
    __tablename__ = "checkin_steps"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id: Mapped[str] = mapped_column(
        String, ForeignKey("checkin_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String, nullable=False)  # stabiler Frage-Key
    # 'intro'|'skala'|'einfachauswahl'|'mehrfachauswahl'|'kurztext'|'langtext'|'bestaetigung'
    typ: Mapped[str] = mapped_column(String, nullable=False)
    frage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hilfetext: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pflichtfeld: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    optionen: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ["Option A", "Option B", ...]
    skala_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    skala_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    skala_labels: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {"min": "...", "max": "..."}
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    template = relationship("CheckinTemplate", back_populates="steps")


class CheckinResponse(Base):
    """Antwort einer Klientin auf ein Check-In. Wird ZUERST hier gespeichert
    (treibt Player & Fortschritt), danach via crm_outbox ans CRM synchronisiert.
    Eine Antwort pro (user, lesson) — Bearbeiten = Update derselben Zeile."""
    __tablename__ = "checkin_responses"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_checkin_user_lesson"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[str] = mapped_column(String, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id: Mapped[str] = mapped_column(String, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    template_typ: Mapped[str] = mapped_column(String, nullable=False)  # 'start' | 'laufend' | 'ende'
    week_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # {key: Wert}
    status: Mapped[str] = mapped_column(String, nullable=False, default="submitted", server_default="submitted")
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    synced_to_crm: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class CrmOutbox(Base):
    """Outbox für ausgehende CRM-Syncs. Ein Background-Loop (Muster drip_notifier)
    arbeitet offene Zeilen ab und markiert synced_at. retry_count/last_error für
    fehlertolerantes, nicht-blockierendes Nachliefern."""
    __tablename__ = "crm_outbox"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type: Mapped[str] = mapped_column(String, nullable=False)  # 'checkin_response'
    user_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    course_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
