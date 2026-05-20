from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


TargetType = Literal["module", "lesson"]


class AnnouncementCreateRequest(BaseModel):
    target_type: TargetType
    target_id: str = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)


class AnnouncementPreviewResponse(BaseModel):
    suggested_subject: str
    suggested_body: str
    recipient_count: int
    target_title: str
    target_module_title: Optional[str] = None  # None for module-target


class CreatedByInfo(BaseModel):
    id: str
    name: str


class AnnouncementResponse(BaseModel):
    id: str
    course_id: str
    target_type: TargetType
    target_id: str
    target_title: Optional[str]  # None if target wurde gelöscht
    target_module_title: Optional[str]  # nur bei target_type=lesson
    subject: str
    body: str
    recipient_count: int
    sent_at: datetime
    created_by: Optional[CreatedByInfo]


class AnnouncementCreateResponse(BaseModel):
    announcement: AnnouncementResponse
    delivery_summary: dict  # {"sent": int, "failed": int}


class AnnouncementListResponse(BaseModel):
    announcements: list[AnnouncementResponse]
