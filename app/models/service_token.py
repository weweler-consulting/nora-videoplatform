import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.time import utc_now


class ServiceToken(Base):
    """Long-lived API token used by other apps (e.g. CRM) to call admin endpoints."""
    __tablename__ = "service_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
