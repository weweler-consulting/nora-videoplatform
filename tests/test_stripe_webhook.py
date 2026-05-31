"""Endpoint-level tests for the Stripe webhook idempotency hardening (F1).

These prove the claim (stripe_processed_events) and the enrollment writes are
committed in ONE transaction: a failure mid-handler rolls back the claim too, so
Stripe's retry reprocesses instead of hitting a phantom "already processed".
"""
import pytest
import stripe
from sqlalchemy import select

import app.core.db as db_module
import app.api.stripe_webhook as wh
from app.models.course import Course, Enrollment
from app.models.user import User


PROD = "prod_test_f1"
EVENT = {
    "id": "evt_f1_1",
    "type": "checkout.session.completed",
    "data": {"object": {
        "id": "cs_1",
        "customer_details": {"email": "kundin@example.com", "name": "Kundin"},
    }},
}


def _patch_stripe(monkeypatch):
    # The webhook module imported `async_session` by name at import time, so point
    # it at the test engine's patched factory (same trick as the drip tests).
    monkeypatch.setattr(wh, "async_session", db_module.async_session)
    monkeypatch.setattr(wh, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(wh, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(stripe.Webhook, "construct_event",
                        lambda payload, sig, secret: EVENT)
    monkeypatch.setattr(stripe.checkout.Session, "list_line_items",
                        lambda session_id, limit=10: {"data": [{"price": {"product": PROD}}]})


async def _count(session, model, **filters):
    stmt = select(model)
    for key, val in filters.items():
        stmt = stmt.where(getattr(model, key) == val)
    res = await session.execute(stmt)
    return len(res.scalars().all())


async def _post(client):
    return await client.post(
        "/api/v1/stripe/webhook", content=b"{}", headers={"stripe-signature": "x"},
    )


@pytest.mark.asyncio
async def test_webhook_rolls_back_claim_when_handler_fails(client, session, monkeypatch):
    _patch_stripe(monkeypatch)
    session.add(Course(title="4-Wochen", is_active=True, stripe_product_id=PROD))
    await session.commit()

    # Fail AFTER enrollments are staged but before commit, to exercise the atomic
    # rollback of claim + writes together.
    real_label = wh._access_label_for
    state = {"fail": True}

    def flaky_label(courses, product_ids):
        if state["fail"]:
            raise RuntimeError("boom after enrollment add")
        return real_label(courses, product_ids)

    monkeypatch.setattr(wh, "_access_label_for", flaky_label)

    with pytest.raises(RuntimeError):
        await _post(client)

    # Nothing persisted — the claim rolled back with the work.
    assert await _count(session, wh.StripeProcessedEvent) == 0
    assert await _count(session, Enrollment) == 0
    assert await _count(session, User, email="kundin@example.com") == 0

    # Retry succeeds because the event was never durably claimed.
    state["fail"] = False
    r = await _post(client)
    assert r.status_code == 200
    assert await _count(session, wh.StripeProcessedEvent) == 1
    assert await _count(session, Enrollment) == 1
    assert await _count(session, User, email="kundin@example.com") == 1


@pytest.mark.asyncio
async def test_webhook_duplicate_event_is_skipped(client, session, monkeypatch):
    _patch_stripe(monkeypatch)
    session.add(Course(title="4-Wochen", is_active=True, stripe_product_id=PROD))
    await session.commit()

    r1 = await _post(client)
    assert r1.status_code == 200
    assert await _count(session, Enrollment) == 1

    r2 = await _post(client)
    assert r2.status_code == 200
    assert r2.json().get("duplicate") is True
    # No double enrollment, single claim row.
    assert await _count(session, Enrollment) == 1
    assert await _count(session, wh.StripeProcessedEvent) == 1
