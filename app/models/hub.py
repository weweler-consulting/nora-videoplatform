import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class CourseHub(Base):
    __tablename__ = "course_hubs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id: Mapped[str] = mapped_column(
        String, ForeignKey("courses.id", ondelete="CASCADE"), unique=True, nullable=False, index=True,
    )

    # Hero
    hero_variant: Mapped[str] = mapped_column(String, default="berry", server_default="berry")
    hero_eyebrow: Mapped[str] = mapped_column(String, default="", server_default="")
    hero_title_html: Mapped[str] = mapped_column(Text, default="", server_default="")
    hero_body: Mapped[str] = mapped_column(Text, default="", server_default="")

    # Contact
    contact_user_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    contact_name_override: Mapped[str] = mapped_column(String, default="", server_default="")
    contact_role: Mapped[str] = mapped_column(
        String, default="Kursleitung & Ernährungsberaterin",
        server_default="Kursleitung & Ernährungsberaterin",
    )
    contact_email_override: Mapped[str] = mapped_column(String, default="", server_default="")
    contact_whatsapp_url: Mapped[str] = mapped_column(String, default="", server_default="")
    contact_photo_url: Mapped[str] = mapped_column(String, default="", server_default="")

    # Section visibility
    show_contact: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    show_live_calls: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    show_products: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    show_downloads: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    course = relationship("Course", back_populates="hub")
    links = relationship(
        "HubLink", cascade="all, delete-orphan", order_by="HubLink.sort_order", lazy="selectin",
    )
    live_calls = relationship(
        "HubLiveCall", cascade="all, delete-orphan", order_by="HubLiveCall.sort_order", lazy="selectin",
    )
    products = relationship(
        "HubProduct", cascade="all, delete-orphan", order_by="HubProduct.sort_order", lazy="selectin",
    )
    downloads = relationship(
        "HubDownload", cascade="all, delete-orphan", order_by="HubDownload.sort_order", lazy="selectin",
    )


class HubLink(Base):
    __tablename__ = "hub_links"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id: Mapped[str] = mapped_column(
        String, ForeignKey("course_hubs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    icon_type: Mapped[str] = mapped_column(String, nullable=False)     # book|video|wa|cal|link
    label: Mapped[str] = mapped_column(String, nullable=False)
    sublabel: Mapped[str] = mapped_column(String, default="", server_default="")
    url: Mapped[str] = mapped_column(String, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class HubLiveCall(Base):
    __tablename__ = "hub_live_calls"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id: Mapped[str] = mapped_column(
        String, ForeignKey("course_hubs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    tag: Mapped[str] = mapped_column(String, default="", server_default="")
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class HubProduct(Base):
    __tablename__ = "hub_products"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id: Mapped[str] = mapped_column(
        String, ForeignKey("course_hubs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    label: Mapped[str] = mapped_column(String, default="", server_default="")
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    cta_text: Mapped[str] = mapped_column(String, default="Zum Shop", server_default="Zum Shop")
    url: Mapped[str] = mapped_column(String, default="", server_default="")
    image_url: Mapped[str] = mapped_column(String, default="", server_default="")
    highlight: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class HubDownload(Base):
    __tablename__ = "hub_downloads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id: Mapped[str] = mapped_column(
        String, ForeignKey("course_hubs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_size_kb: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
