"""Product -> course resolution for Stripe-driven provisioning.

Money path: a purchase must grant access to exactly the right courses.
The 4-Wochen-Bundle grants TWO courses (Begleitkurs via direct field match
+ Frühstückscode via a product_course_map bundle row), while a standalone
Frühstückscode purchase still grants only the one course.
"""
import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.api.stripe_webhook import _courses_for_products, _access_label_for, _join_de
from app.models.course import Course, ProductCourseMap

FRUEHSTUECK_PROD = "prod_UT6hAjm5oSM5Qs"
VIERWOCHEN_PROD = "prod_UbweNqpMeE7azJ"


async def _seed(session):
    fruehstueck = Course(title="Frühstücks-Code", stripe_product_id=FRUEHSTUECK_PROD)
    begleit = Course(title="4-Wochen Begleitkurs", stripe_product_id=VIERWOCHEN_PROD)
    session.add_all([fruehstueck, begleit])
    await session.flush()
    # Bundle: the 4-Wochen product additionally grants the Frühstücks-Code course
    session.add(ProductCourseMap(stripe_product_id=VIERWOCHEN_PROD, course_id=fruehstueck.id))
    await session.commit()
    return fruehstueck, begleit


def test_join_de():
    assert _join_de(["A"]) == "A"
    assert _join_de(["A", "B"]) == "A und B"
    assert _join_de(["A", "B", "C"]) == "A, B und C"


def test_access_label_bundle_reads_as_main_plus_included():
    courses = [
        Course(title="4-Wochen Glukose Balance Code", stripe_product_id=VIERWOCHEN_PROD),
        Course(title="Frühstücks-Code", stripe_product_id=FRUEHSTUECK_PROD),
    ]
    # Purchased product is the 4-Wochen one; Frühstücks-Code rides along via mapping
    label = _access_label_for(courses, [VIERWOCHEN_PROD])
    assert label == "4-Wochen Glukose Balance Code inkl. Frühstücks-Code"
    # Order of the input list must not change the framing
    assert _access_label_for(list(reversed(courses)), [VIERWOCHEN_PROD]) == label


def test_access_label_single_course_unchanged():
    courses = [Course(title="Frühstücks-Code", stripe_product_id=FRUEHSTUECK_PROD)]
    assert _access_label_for(courses, [FRUEHSTUECK_PROD]) == "Frühstücks-Code"


@pytest.mark.asyncio
async def test_standalone_fruehstueck_grants_only_one_course(session):
    fruehstueck, _ = await _seed(session)
    courses = await _courses_for_products(session, [FRUEHSTUECK_PROD])
    assert {c.id for c in courses} == {fruehstueck.id}


@pytest.mark.asyncio
async def test_bundle_grants_both_courses(session):
    fruehstueck, begleit = await _seed(session)
    courses = await _courses_for_products(session, [VIERWOCHEN_PROD])
    assert {c.id for c in courses} == {fruehstueck.id, begleit.id}


@pytest.mark.asyncio
async def test_course_matched_by_field_and_mapping_appears_once(session):
    fruehstueck, _ = await _seed(session)
    # Redundant mapping row pointing the Frühstücks-Code product at its own course
    session.add(ProductCourseMap(stripe_product_id=FRUEHSTUECK_PROD, course_id=fruehstueck.id))
    await session.commit()
    courses = await _courses_for_products(session, [FRUEHSTUECK_PROD])
    assert [c.id for c in courses].count(fruehstueck.id) == 1


@pytest.mark.asyncio
async def test_unknown_product_grants_nothing(session):
    await _seed(session)
    courses = await _courses_for_products(session, ["prod_does_not_exist"])
    assert courses == []


@pytest.mark.asyncio
async def test_checkout_handler_enrolls_both_courses_and_sends_one_invite(engine, session, monkeypatch):
    """End-to-end money path: a 4-Wochen purchase must create the user, enroll
    them in BOTH courses, and send exactly ONE invite email naming both."""
    import types
    import app.api.stripe_webhook as wh
    from app.models.user import User

    fruehstueck, begleit = await _seed(session)

    # Point the handler's session factory + Stripe + email at test doubles
    monkeypatch.setattr(wh, "async_session", db_module.async_session)
    monkeypatch.setattr(
        wh.stripe.checkout.Session,
        "list_line_items",
        staticmethod(lambda sid, limit=10: {"data": [{"price": {"product": VIERWOCHEN_PROD}}]}),
    )
    sent = []
    monkeypatch.setattr(wh, "send_invite_email", lambda *a, **k: sent.append(a) or True)
    monkeypatch.setattr(wh, "send_course_added_email", lambda *a, **k: sent.append(("ADDED",) + a) or True)

    fake_request = types.SimpleNamespace(base_url="https://kurse.noraweweler.de/")
    checkout = {
        "id": "cs_test_123",
        "customer_details": {"email": "kundin@example.com", "name": "Test Kundin"},
    }

    # New contract (F1): handler writes into the passed session without committing
    # and returns an email thunk; the caller commits, then fires the email.
    async with db_module.async_session() as db:
        email_job = await wh._handle_checkout_completed(checkout, fake_request, db)
        await db.commit()
    assert email_job is not None
    email_job()

    # User created
    user = (await session.execute(select(User).where(User.email == "kundin@example.com"))).scalar_one()
    # Enrolled in BOTH courses
    from app.models.course import Enrollment
    enr = (await session.execute(select(Enrollment).where(Enrollment.user_id == user.id))).scalars().all()
    assert {e.course_id for e in enr} == {fruehstueck.id, begleit.id}
    # Exactly one invite email, naming both courses
    assert len(sent) == 1
    titles_arg = sent[0][2]
    assert fruehstueck.title in titles_arg and begleit.title in titles_arg


@pytest.mark.asyncio
async def test_bundle_seed_is_correct_and_idempotent(engine, session, monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "engine", engine)
    fruehstueck = Course(title="Frühstücks-Code", stripe_product_id=FRUEHSTUECK_PROD)
    session.add(fruehstueck)
    await session.commit()

    await main._seed_bundle_mappings()
    await main._seed_bundle_mappings()  # second run must be a no-op

    result = await session.execute(
        select(ProductCourseMap).where(ProductCourseMap.stripe_product_id == VIERWOCHEN_PROD)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].course_id == fruehstueck.id
