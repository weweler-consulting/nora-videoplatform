import pytest

from app.core.auth import create_access_token, decode_token_payload
from tests.test_checkin import _mk_user, _auth


@pytest.mark.asyncio
async def test_admin_can_impersonate_customer(client, session):
    admin = await _mk_user(session, admin=True)
    customer = await _mk_user(session, admin=False)

    r = await client.post(f"/api/v1/users/{customer.id}/impersonate", headers=_auth(admin))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["id"] == customer.id

    # The issued token carries the admin as impersonator and scopes to the customer.
    payload = decode_token_payload(body["access_token"])
    assert payload["sub"] == customer.id
    assert payload["imp"] == admin.id


@pytest.mark.asyncio
async def test_me_surfaces_impersonation(client, session):
    admin = await _mk_user(session, admin=True)
    customer = await _mk_user(session, admin=False)

    token = create_access_token(customer.id, impersonator_id=admin.id)
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == customer.id
    assert body["impersonated"] is True
    assert body["impersonator"]["id"] == admin.id
    assert body["impersonator"]["email"] == admin.email


@pytest.mark.asyncio
async def test_me_normal_session_not_impersonated(client, session):
    customer = await _mk_user(session, admin=False)
    r = await client.get("/api/v1/auth/me", headers=_auth(customer))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["impersonated"] is False
    assert body["impersonator"] is None


@pytest.mark.asyncio
async def test_non_admin_cannot_impersonate(client, session):
    customer = await _mk_user(session, admin=False)
    target = await _mk_user(session, admin=False)
    r = await client.post(f"/api/v1/users/{target.id}/impersonate", headers=_auth(customer))
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_cannot_impersonate_admin(client, session):
    admin = await _mk_user(session, admin=True)
    other_admin = await _mk_user(session, admin=True)
    r = await client.post(f"/api/v1/users/{other_admin.id}/impersonate", headers=_auth(admin))
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_impersonate_unknown_user_404(client, session):
    admin = await _mk_user(session, admin=True)
    r = await client.post("/api/v1/users/does-not-exist/impersonate", headers=_auth(admin))
    assert r.status_code == 404, r.text
