from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class LessonOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    video_url: Optional[str]
    duration_minutes: int
    sort_order: int
    completed: bool = False


class SectionOut(BaseModel):
    id: str
    title: str
    sort_order: int
    lessons: list[LessonOut] = []


class ModuleOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    image_url: Optional[str]
    sort_order: int
    sections: list[SectionOut] = []
    total_lessons: int = 0
    completed_lessons: int = 0
    total_duration: int = 0


class CourseOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    image_url: Optional[str]
    is_active: bool
    sort_order: int
    created_at: datetime
    modules: list[ModuleOut] = []
    total_lessons: int = 0
    completed_lessons: int = 0
    progress_percent: int = 0


class CourseListItem(BaseModel):
    id: str
    title: str
    description: Optional[str]
    image_url: Optional[str]
    total_lessons: int = 0
    completed_lessons: int = 0
    progress_percent: int = 0


# Admin schemas
class ModuleCreate(BaseModel):
    course_id: str
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: int = 0


class ModuleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: Optional[int] = None


class SectionCreate(BaseModel):
    module_id: str
    title: str
    sort_order: int = 0


class SectionUpdate(BaseModel):
    title: Optional[str] = None
    sort_order: Optional[int] = None


class LessonCreate(BaseModel):
    section_id: str
    title: str
    description: Optional[str] = None
    video_url: Optional[str] = None
    duration_minutes: int = 0
    sort_order: int = 0


class LessonUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None
    duration_minutes: Optional[int] = None
    sort_order: Optional[int] = None
