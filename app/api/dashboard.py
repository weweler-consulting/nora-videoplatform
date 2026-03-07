from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.db import get_db
from app.models.user import User
from app.models.course import Course, Enrollment, Lesson, LessonProgress, Module, Section

router = APIRouter()


@router.get("/stats")
async def dashboard_stats(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    fourteen_days_ago = now - timedelta(days=14)

    # Total non-admin users
    total_users_q = await db.execute(
        select(func.count(User.id)).where(User.is_admin == False)
    )
    total_users = total_users_q.scalar() or 0

    # Active users (completed a lesson in the last 7 days)
    active_users_q = await db.execute(
        select(func.count(func.distinct(LessonProgress.user_id))).where(
            LessonProgress.completed == True,
            LessonProgress.completed_at >= seven_days_ago,
        )
    )
    active_users = active_users_q.scalar() or 0

    # New users this month
    new_users_month_q = await db.execute(
        select(func.count(User.id)).where(
            User.is_admin == False,
            User.created_at >= thirty_days_ago,
        )
    )
    new_users_month = new_users_month_q.scalar() or 0

    # Total completions (users who finished 100% of a course)
    # We'll compute per-course completion rates
    courses_q = await db.execute(select(Course))
    courses = courses_q.scalars().all()

    course_stats = []
    total_completed_courses = 0

    for course in courses:
        # Count lessons in this course
        lesson_count_q = await db.execute(
            select(func.count(Lesson.id))
            .select_from(Lesson)
            .join(Section, Lesson.section_id == Section.id)
            .join(Module, Section.module_id == Module.id)
            .where(Module.course_id == course.id)
        )
        total_lessons = lesson_count_q.scalar() or 0

        # Count enrollments
        enrollment_count_q = await db.execute(
            select(func.count(Enrollment.id)).where(Enrollment.course_id == course.id)
        )
        enrolled = enrollment_count_q.scalar() or 0

        if total_lessons == 0 or enrolled == 0:
            course_stats.append({
                "course_id": course.id,
                "title": course.title,
                "enrolled": enrolled,
                "total_lessons": total_lessons,
                "avg_progress": 0,
                "completed_count": 0,
            })
            continue

        # Get all lesson IDs for this course
        lesson_ids_q = await db.execute(
            select(Lesson.id)
            .join(Section, Lesson.section_id == Section.id)
            .join(Module, Section.module_id == Module.id)
            .where(Module.course_id == course.id)
        )
        lesson_ids = set(lesson_ids_q.scalars().all())

        # Get enrolled user IDs
        enrolled_users_q = await db.execute(
            select(Enrollment.user_id).where(Enrollment.course_id == course.id)
        )
        enrolled_user_ids = enrolled_users_q.scalars().all()

        # Per-user completion count for this course
        total_progress = 0
        completed_count = 0
        for uid in enrolled_user_ids:
            user_completed_q = await db.execute(
                select(func.count(LessonProgress.id)).where(
                    LessonProgress.user_id == uid,
                    LessonProgress.lesson_id.in_(lesson_ids),
                    LessonProgress.completed == True,
                )
            )
            user_completed = user_completed_q.scalar() or 0
            total_progress += user_completed
            if user_completed >= total_lessons:
                completed_count += 1

        avg_progress = int((total_progress / (enrolled * total_lessons)) * 100) if enrolled > 0 else 0
        total_completed_courses += completed_count

        course_stats.append({
            "course_id": course.id,
            "title": course.title,
            "enrolled": enrolled,
            "total_lessons": total_lessons,
            "avg_progress": avg_progress,
            "completed_count": completed_count,
        })

    # Inactive users: enrolled, not admin, no lesson completion in 14 days
    # Get users who HAVE completed something (ever) but nothing in last 14 days
    recently_active_q = await db.execute(
        select(func.distinct(LessonProgress.user_id)).where(
            LessonProgress.completed == True,
            LessonProgress.completed_at >= fourteen_days_ago,
        )
    )
    recently_active_ids = set(recently_active_q.scalars().all())

    # Get all enrolled non-admin users
    enrolled_users_q = await db.execute(
        select(User)
        .join(Enrollment, Enrollment.user_id == User.id)
        .where(User.is_admin == False, User.is_active == True)
        .distinct()
    )
    all_enrolled = enrolled_users_q.scalars().unique().all()

    inactive_users = []
    for u in all_enrolled:
        if u.id not in recently_active_ids:
            # Get last activity
            last_q = await db.execute(
                select(func.max(LessonProgress.completed_at)).where(
                    LessonProgress.user_id == u.id,
                    LessonProgress.completed == True,
                )
            )
            last_active = last_q.scalar()

            # Get total progress
            user_total_q = await db.execute(
                select(func.count(LessonProgress.id)).where(
                    LessonProgress.user_id == u.id,
                    LessonProgress.completed == True,
                )
            )
            user_completed = user_total_q.scalar() or 0

            # Get total lessons available to user
            user_lessons_q = await db.execute(
                select(func.count(Lesson.id))
                .select_from(Lesson)
                .join(Section, Lesson.section_id == Section.id)
                .join(Module, Section.module_id == Module.id)
                .join(Course, Module.course_id == Course.id)
                .join(Enrollment, and_(
                    Enrollment.course_id == Course.id,
                    Enrollment.user_id == u.id,
                ))
            )
            user_total_lessons = user_lessons_q.scalar() or 0

            inactive_users.append({
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "last_active": last_active.isoformat() if last_active else None,
                "completed_lessons": user_completed,
                "total_lessons": user_total_lessons,
                "progress_percent": int((user_completed / user_total_lessons * 100) if user_total_lessons > 0 else 0),
            })

    # Sort inactive by last_active (None = never active, first)
    inactive_users.sort(key=lambda x: x["last_active"] or "")

    return {
        "total_users": total_users,
        "active_users_7d": active_users,
        "new_users_30d": new_users_month,
        "total_completed_courses": total_completed_courses,
        "courses": course_stats,
        "inactive_users": inactive_users,
    }
