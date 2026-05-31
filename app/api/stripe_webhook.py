import logging
import os
import secrets
from datetime import datetime, timedelta

import stripe
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import String, DateTime, select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, async_session
from app.core.email import send_invite_email, send_course_added_email
from app.core.time import utc_now
from app.models.user import User
from app.models.course import Course, Enrollment, ProductCourseMap

logger = logging.getLogger(__name__)

router = APIRouter()

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

INVITE_TOKEN_TTL_DAYS = 7


async def _courses_for_products(db: AsyncSession, product_ids: list[str]) -> list[Course]:
    """All courses granted by these Stripe products: the direct
    Course.stripe_product_id field match plus any product_course_map bundle
    rows. Deduplicated (a course matched by both ways appears once)."""
    result = await db.execute(
        select(Course).where(
            or_(
                Course.stripe_product_id.in_(product_ids),
                Course.id.in_(
                    select(ProductCourseMap.course_id).where(
                        ProductCourseMap.stripe_product_id.in_(product_ids)
                    )
                ),
            )
        )
    )
    return list(result.scalars().all())


class StripeProcessedEvent(Base):
    __tablename__ = "stripe_processed_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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

    # PRE-CHECK vor dem Idempotenz-Claim: wenn wir das Event ohnehin nicht
    # verarbeiten würden (z.B. unbekanntes Produkt, nicht-relevanter Event-Type),
    # soll der Resend nach einem Fix funktionieren statt als "already processed"
    # geskipped zu werden.
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        try:
            line_items = stripe.checkout.Session.list_line_items(session["id"], limit=10)
        except Exception as e:
            logger.error(f"Stripe API failed for session {session['id']}: {e}")
            raise HTTPException(status_code=500, detail="Stripe API failed")
        product_ids = [
            (item.get("price") or {}).get("product")
            for item in line_items.get("data", [])
        ]
        product_ids = [p for p in product_ids if p]
        if not product_ids:
            logger.error(f"No products in session {session['id']} — not claiming event")
            return {"ok": True, "ignored": "no_products"}
        async with async_session() as check_db:
            if not await _courses_for_products(check_db, product_ids):
                logger.error(
                    f"No courses match Stripe product IDs {product_ids} — not claiming event "
                    f"(resend after fix possible)"
                )
                return {"ok": True, "ignored": "no_match"}
    elif event["type"] not in ("charge.refunded",):
        logger.info(f"Unhandled Stripe event type: {event['type']} — not claiming")
        return {"ok": True, "ignored": "unhandled_type"}

    # Idempotency: claim the event ID. Skip if already processed.
    async with async_session() as db:
        db.add(StripeProcessedEvent(event_id=event["id"]))
        try:
            await db.commit()
        except IntegrityError:
            logger.info(f"Stripe event {event['id']} already processed, skipping")
            return {"ok": True, "duplicate": True}

    if event["type"] == "checkout.session.completed":
        await _handle_checkout_completed(event["data"]["object"], request)
    elif event["type"] == "charge.refunded":
        await _handle_refund(event["data"]["object"])

    return {"ok": True}


async def _handle_refund(charge: dict):
    """Remove enrollments when a charge is fully refunded."""
    if charge.get("amount_refunded", 0) < charge.get("amount", 0):
        logger.info(f"Partial refund on charge {charge.get('id')}, ignoring")
        return

    payment_intent_id = charge.get("payment_intent")
    if not payment_intent_id:
        logger.warning(f"Refunded charge {charge.get('id')} has no payment_intent")
        return

    stripe.api_key = STRIPE_SECRET_KEY
    sessions = stripe.checkout.Session.list(payment_intent=payment_intent_id, limit=1)
    session_list = sessions.get("data", []) if isinstance(sessions, dict) else list(sessions.data)
    if not session_list:
        logger.warning(f"No checkout session for refunded payment_intent {payment_intent_id}")
        return
    session = session_list[0]
    session_id = session["id"] if isinstance(session, dict) else session.id

    customer_email = (
        (session.get("customer_details", {}) if isinstance(session, dict) else session.customer_details or {}).get("email")
        or charge.get("billing_details", {}).get("email")
    )
    if not customer_email:
        logger.warning(f"Refund on {payment_intent_id}: no customer email found")
        return

    line_items = stripe.checkout.Session.list_line_items(session_id, limit=10)
    product_ids = []
    for item in line_items.get("data", []) if isinstance(line_items, dict) else line_items.data:
        price = item.get("price", {}) if isinstance(item, dict) else (item.price or {})
        pid = price.get("product") if isinstance(price, dict) else price.product
        if pid:
            product_ids.append(pid)

    if not product_ids:
        logger.warning(f"Refund on {payment_intent_id}: no product IDs found")
        return

    async with async_session() as db:
        courses = await _courses_for_products(db, product_ids)
        if not courses:
            logger.info(f"Refund on {payment_intent_id}: no matching courses for products {product_ids}")
            return

        user_result = await db.execute(select(User).where(User.email == customer_email))
        user = user_result.scalar_one_or_none()
        if not user:
            logger.info(f"Refund on {payment_intent_id}: no user for email {customer_email}")
            return

        removed_titles = []
        for course in courses:
            enrollment_result = await db.execute(
                select(Enrollment).where(
                    Enrollment.user_id == user.id,
                    Enrollment.course_id == course.id,
                )
            )
            enrollment = enrollment_result.scalar_one_or_none()
            if enrollment:
                await db.delete(enrollment)
                removed_titles.append(course.title)
        await db.commit()

        if removed_titles:
            logger.info(
                f"Refund processed: removed enrollments for {customer_email} "
                f"from courses {removed_titles}"
            )
        else:
            logger.info(f"Refund on {payment_intent_id}: no enrollments to remove for {customer_email}")


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
        # Find courses matching the product IDs (direct field + bundle mappings)
        courses = await _courses_for_products(db, product_ids)

        if not courses:
            logger.error(f"No courses found for Stripe product IDs: {product_ids}")
            return

        # Find or create user
        user_result = await db.execute(select(User).where(User.email == customer_email))
        user = user_result.scalar_one_or_none()

        needs_invite = False
        if not user:
            name = customer_name or customer_email.split("@")[0]
            user = User(
                email=customer_email,
                name=name,
                hashed_password="",
                invite_token=secrets.token_urlsafe(32),
                invite_token_expires=utc_now() + timedelta(days=INVITE_TOKEN_TTL_DAYS),
            )
            db.add(user)
            await db.flush()
            needs_invite = True
        elif not user.invite_accepted_at:
            # User stuck with an unaccepted invite — refresh token, resend
            user.invite_token = secrets.token_urlsafe(32)
            user.invite_token_expires = utc_now() + timedelta(days=INVITE_TOKEN_TTL_DAYS)
            needs_invite = True

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

        if needs_invite and enrolled_courses:
            base = str(request.base_url).rstrip("/").replace("http://", "https://", 1)
            invite_url = f"{base}/accept-invite?token={user.invite_token}"
            course_titles = ", ".join(c.title for c in enrolled_courses)
            try:
                send_invite_email(customer_email, user.name, course_titles, invite_url)
                logger.info(f"Invite email sent to {customer_email} for courses: {course_titles}")
            except Exception as e:
                logger.error(f"Failed to send invite email to {customer_email}: {e}")
        elif not needs_invite and enrolled_courses:
            base = str(request.base_url).rstrip("/").replace("http://", "https://", 1)
            login_url = f"{base}/login"
            course_titles = ", ".join(c.title for c in enrolled_courses)
            try:
                send_course_added_email(customer_email, user.name, course_titles, login_url)
                logger.info(f"Course-added email sent to {customer_email} for: {course_titles}")
            except Exception as e:
                logger.error(f"Failed to send course-added email to {customer_email}: {e}")
