from datetime import datetime, timedelta
from typing import Optional, Union

import hashlib
import hmac
import secrets

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.time import utc_now
from app.models.user import User
from app.models.service_token import ServiceToken

security = HTTPBearer()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${h.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password or "$" not in hashed_password:
        return False
    salt, hash_hex = hashed_password.split("$", 1)
    h = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt.encode(), 100_000)
    return hmac.compare_digest(h.hex(), hash_hex)


def create_access_token(user_id: str) -> str:
    expire = utc_now() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def create_email_change_token(user_id: str, new_email: str) -> str:
    """Short-lived token that confirms the user wants to swap their email."""
    expire = utc_now() + timedelta(hours=1)
    payload = {"sub": user_id, "new_email": new_email, "purpose": "email_change", "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_email_change_token(token: str) -> Optional[tuple[str, str]]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("purpose") != "email_change":
        return None
    user_id = payload.get("sub")
    new_email = payload.get("new_email")
    if not user_id or not new_email:
        return None
    return user_id, new_email


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deaktiviert")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


def hash_service_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_service_token() -> str:
    """Return a fresh random service token in the `nvp_` prefixed format."""
    return f"nvp_{secrets.token_urlsafe(32)}"


async def _resolve_service_token(request: Request, db: AsyncSession) -> Optional[ServiceToken]:
    raw = request.headers.get("X-Service-Token")
    if not raw:
        return None
    token_hash = hash_service_token(raw)
    result = await db.execute(select(ServiceToken).where(ServiceToken.token_hash == token_hash))
    token = result.scalar_one_or_none()
    if token:
        token.last_used_at = utc_now()
    return token


async def require_admin_or_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Union[User, ServiceToken]:
    """Accept either a service token (X-Service-Token header) or an admin JWT.

    Service tokens are used by other internal apps (e.g. the CRM) to call
    admin endpoints without needing an admin user login.
    """
    service_token = await _resolve_service_token(request, db)
    if service_token:
        return service_token

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")
    jwt_token = auth_header[7:]
    user_id = decode_access_token(jwt_token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deaktiviert")
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user
