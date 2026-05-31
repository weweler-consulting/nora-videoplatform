"""Product -> course resolution for Stripe-driven provisioning.

Money path: a purchase must grant access to exactly the right courses.
The 4-Wochen-Bundle grants TWO courses (Begleitkurs via direct field match
+ Frühstückscode via a product_course_map bundle row), while a standalone
Frühstückscode purchase still grants only the one course.
"""
import pytest
from sqlalchemy import select

from app.api.stripe_webhook import _courses_for_products
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
