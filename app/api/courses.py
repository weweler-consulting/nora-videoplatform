from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.auth import get_current_user, require_admin
from app.models.user import User
from app.models.course import Course, Module, Section, Lesson, Enrollment, LessonProgress, ModuleUnlock
from app.schemas.course import (
    CourseCreate, CourseUpdate, CourseOut, CourseListItem, ModuleOut, SectionOut, LessonOut,
)

router = APIRouter()


async def _get_user_progress(db: AsyncSession, user_id: str) -> set[str]:
    result = await db.execute(
        select(LessonProgress.lesson_id).where(
            LessonProgress.user_id == user_id, LessonProgress.completed == True
        )
    )
    return set(result.scalars().all())


def _build_course_out(course: Course, completed_ids: set[str], enrolled_at: datetime | None = None, unlocked_module_ids: set[str] | None = None) -> CourseOut:
    modules_out = []
    total_lessons = 0
    total_completed = 0
    now = datetime.utcnow()

    for module in course.modules:
        # Drip content: check if module is locked
        is_locked = False
        unlocks_at = None
        manually_unlocked = unlocked_module_ids and module.id in unlocked_module_ids
        if not manually_unlocked and enrolled_at and module.unlock_after_days > 0:
            unlock_date = enrolled_at + timedelta(days=module.unlock_after_days)
            if now < unlock_date:
                is_locked = True
                unlocks_at = unlock_date.strftime("%d.%m.%Y")

        sections_out = []
        mod_lessons = 0
        mod_completed = 0
        mod_duration = 0

        for section in module.sections:
            lessons_out = []
            for lesson in section.lessons:
                is_done = lesson.id in completed_ids
                lessons_out.append(LessonOut(
                    id=lesson.id, title=lesson.title,
                    description=None if is_locked else lesson.description,
                    video_url=None if is_locked else lesson.video_url,
                    duration_minutes=lesson.duration_minutes,
                    sort_order=lesson.sort_order, completed=is_done,
                ))
                mod_lessons += 1
                mod_duration += lesson.duration_minutes
                if is_done:
                    mod_completed += 1
            sections_out.append(SectionOut(
                id=section.id, title=section.title, sort_order=section.sort_order, lessons=lessons_out,
            ))

        total_lessons += mod_lessons
        total_completed += mod_completed
        modules_out.append(ModuleOut(
            id=module.id, title=module.title, description=module.description,
            image_url=module.image_url, sort_order=module.sort_order,
            unlock_after_days=module.unlock_after_days,
            is_locked=is_locked, unlocks_at=unlocks_at,
            sections=sections_out, total_lessons=mod_lessons,
            completed_lessons=mod_completed, total_duration=mod_duration,
        ))

    progress = int((total_completed / total_lessons * 100) if total_lessons > 0 else 0)

    return CourseOut(
        id=course.id, title=course.title, description=course.description,
        image_url=course.image_url, is_active=course.is_active,
        sort_order=course.sort_order, stripe_product_id=course.stripe_product_id,
        created_at=course.created_at,
        modules=modules_out, total_lessons=total_lessons,
        completed_lessons=total_completed, progress_percent=progress,
    )


@router.get("/", response_model=list[CourseListItem])
async def list_my_courses(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Course)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .where(Enrollment.user_id == user.id, Course.is_active == True)
        .options(
            selectinload(Course.modules)
            .selectinload(Module.sections)
            .selectinload(Section.lessons)
        )
        .order_by(Course.sort_order)
    )
    courses = result.scalars().unique().all()
    completed_ids = await _get_user_progress(db, user.id)

    items = []
    for course in courses:
        total = sum(len(s.lessons) for m in course.modules for s in m.sections)
        done = sum(1 for m in course.modules for s in m.sections for l in s.lessons if l.id in completed_ids)
        items.append(CourseListItem(
            id=course.id, title=course.title, description=course.description,
            image_url=course.image_url, total_lessons=total, completed_lessons=done,
            progress_percent=int((done / total * 100) if total > 0 else 0),
        ))
    return items


@router.get("/{course_id}", response_model=CourseOut)
async def get_course(course_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Check enrollment
    enrollment_result = await db.execute(
        select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == course_id)
    )
    enrollment = enrollment_result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=403, detail="Not enrolled in this course")

    result = await db.execute(
        select(Course).where(Course.id == course_id).options(
            selectinload(Course.modules)
            .selectinload(Module.sections)
            .selectinload(Section.lessons)
        )
    )
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    completed_ids = await _get_user_progress(db, user.id)
    # Admin sees everything unlocked
    if user.is_admin:
        return _build_course_out(course, completed_ids)

    # Load manual unlocks for this user
    unlocks_result = await db.execute(
        select(ModuleUnlock.module_id).where(ModuleUnlock.user_id == user.id)
    )
    unlocked_module_ids = set(unlocks_result.scalars().all())
    return _build_course_out(course, completed_ids, enrolled_at=enrollment.enrolled_at, unlocked_module_ids=unlocked_module_ids)


# Admin endpoints
@router.post("/", response_model=dict)
async def create_course(data: CourseCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    course = Course(**data.model_dump())
    db.add(course)
    await db.flush()
    return {"id": course.id}


@router.put("/{course_id}", response_model=dict)
async def update_course(course_id: str, data: CourseUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(course, key, value)
    return {"id": course.id}


@router.delete("/{course_id}")
async def delete_course(course_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    await db.delete(course)
    return {"ok": True}


# Admin: list all courses (must be before {course_id} route)
@router.get("/admin/all", response_model=list[CourseListItem])
async def list_all_courses(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Course).options(
            selectinload(Course.modules).selectinload(Module.sections).selectinload(Section.lessons)
        ).order_by(Course.sort_order)
    )
    courses = result.scalars().unique().all()
    items = []
    for course in courses:
        total = sum(len(s.lessons) for m in course.modules for s in m.sections)
        items.append(CourseListItem(
            id=course.id, title=course.title, description=course.description,
            image_url=course.image_url, total_lessons=total,
        ))
    return items


# Admin: get single course with full tree
@router.get("/admin/{course_id}", response_model=CourseOut)
async def admin_get_course(course_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Course).where(Course.id == course_id).options(
            selectinload(Course.modules)
            .selectinload(Module.sections)
            .selectinload(Section.lessons)
        )
    )
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return _build_course_out(course, set())
