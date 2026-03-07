import logging
import os
import secrets
import string

import stripe
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session
from app.core.auth import hash_password
from app.core.email import send_invite_email
from app.models.user import User
from app.models.course import Course, Enrollment

logger = logging.getLogger(__name__)

router = APIRouter()

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


def _generate_password(length: int = 10) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


@router.post("/webhook")
async def stripe_webhook(request: Request):
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Stripe nicht konfiguriert")

    stripe.api_key = STRIPE_SECRET_KEY
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await _handle_checkout_completed(session, request)

    return {"ok": True}


async def _handle_checkout_completed(session: dict, request: Request):
    customer_email = session.get("customer_details", {}).get("email")
    customer_name = session.get("customer_details", {}).get("name", "")

    if not customer_email:
        logger.error("Stripe checkout session has no customer email")
        return

    # Get line items to find the product
    stripe.api_key = STRIPE_SECRET_KEY
    line_items = stripe.checkout.Session.list_line_items(session["id"], limit=10)

    product_ids = []
    for item in line_items.get("data", []):
        price = item.get("price", {})
        product_id = price.get("product")
        if product_id:
            product_ids.append(product_id)

    if not product_ids:
        logger.error(f"No products found in checkout session {session['id']}")
        return

    async with async_session() as db:
        # Find courses matching the product IDs
        result = await db.execute(
            select(Course).where(Course.stripe_product_id.in_(product_ids))
        )
        courses = result.scalars().all()

        if not courses:
            logger.error(f"No courses found for Stripe product IDs: {product_ids}")
            return

        # Find or create user
        user_result = await db.execute(select(User).where(User.email == customer_email))
        user = user_result.scalar_one_or_none()

        password = _generate_password()
        is_new_user = user is None

        if not user:
            # Split name into parts, use email prefix as fallback
            name = customer_name or customer_email.split("@")[0]
            user = User(
                email=customer_email,
                name=name,
                hashed_password=hash_password(password),
            )
            db.add(user)
            await db.flush()

        # Enroll in each matched course
        enrolled_courses = []
        for course in courses:
            existing = await db.execute(
                select(Enrollment).where(
                    Enrollment.user_id == user.id,
                    Enrollment.course_id == course.id,
                )
            )
            if not existing.scalar_one_or_none():
                db.add(Enrollment(user_id=user.id, course_id=course.id))
                enrolled_courses.append(course)

        await db.commit()

        # Send invite email for new users
        if is_new_user and enrolled_courses:
            base = str(request.base_url).rstrip("/").replace("http://", "https://", 1)
            login_url = f"{base}/login"
            course_titles = ", ".join(c.title for c in enrolled_courses)
            try:
                send_invite_email(customer_email, user.name, course_titles, password, login_url)
                logger.info(f"Invite email sent to {customer_email} for courses: {course_titles}")
            except Exception as e:
                logger.error(f"Failed to send invite email to {customer_email}: {e}")
        elif not is_new_user and enrolled_courses:
            logger.info(f"Existing user {customer_email} enrolled in: {[c.title for c in enrolled_courses]}")
