import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.db import async_session
from app.core.email import send_module_unlocked_email
from app.models.user import User
from app.models.course import Course, Module, Enrollment, DripNotification, ModuleUnlock

logger = logging.getLogger(__name__)


async def check_drip_notifications(base_url: str = "https://kurse.noraweweler.de"):
    """Check for modules that just became unlocked and send notification emails."""
    now = datetime.utcnow()

    async with async_session() as db:
        # Get all enrollments with courses and modules
        result = await db.execute(
            select(Enrollment, User, Course)
            .join(User, User.id == Enrollment.user_id)
            .join(Course, Course.id == Enrollment.course_id)
            .where(User.is_active == True, User.is_admin == False)
        )
        rows = result.all()

        for enrollment, user, course in rows:
            # Get modules with drip for this course
            modules_result = await db.execute(
                select(Module)
                .where(Module.course_id == course.id, Module.unlock_after_days > 0)
                .order_by(Module.sort_order)
            )
            modules = modules_result.scalars().all()

            for module in modules:
                unlock_date = enrollment.enrolled_at + timedelta(days=module.unlock_after_days)

                # Module should be unlocked now (but wasn't before — within last 2 hours buffer)
                if unlock_date > now:
                    continue  # Still locked

                if unlock_date < now - timedelta(hours=2):
                    continue  # Unlocked more than 2 hours ago, skip (avoid sending old notifications)

                # Check if we already sent this notification
                existing = await db.execute(
                    select(DripNotification).where(
                        DripNotification.user_id == user.id,
                        DripNotification.module_id == module.id,
                    )
                )
                if existing.scalar_one_or_none():
                    continue  # Already notified

                # Check if manually unlocked earlier (no need to notify again)
                manual = await db.execute(
                    select(ModuleUnlock).where(
                        ModuleUnlock.user_id == user.id,
                        ModuleUnlock.module_id == module.id,
                    )
                )
                if manual.scalar_one_or_none():
                    # Record as notified so we don't check again
                    db.add(DripNotification(user_id=user.id, module_id=module.id))
                    await db.commit()
                    continue

                # Send notification
                login_url = f"{base_url}/login"
                try:
                    send_module_unlocked_email(
                        to_email=user.email,
                        to_name=user.name,
                        module_title=module.title,
                        course_title=course.title,
                        login_url=login_url,
                    )
                    logger.info(f"Drip notification sent to {user.email} for module '{module.title}'")
                except Exception as e:
                    logger.error(f"Failed to send drip notification to {user.email}: {e}")
                    continue

                # Record notification
                db.add(DripNotification(user_id=user.id, module_id=module.id))
                await db.commit()


async def drip_notifier_loop():
    """Run drip notification check every hour."""
    while True:
        try:
            await check_drip_notifications()
        except Exception as e:
            logger.error(f"Drip notifier error: {e}", exc_info=True)
        await asyncio.sleep(3600)  # Check every hour
