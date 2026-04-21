from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin, hash_service_token, generate_service_token
from app.core.db import get_db
from app.models.service_token import ServiceToken
from app.models.user import User

router = APIRouter()


class ServiceTokenOut(BaseModel):
    id: str
    name: str
    created_at: str
    last_used_at: str | None


class ServiceTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ServiceTokenCreated(ServiceTokenOut):
    token: str  # Plaintext — shown only once, right after creation


@router.get("/tokens", response_model=list[ServiceTokenOut])
async def list_tokens(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ServiceToken).order_by(ServiceToken.created_at.desc()))
    tokens = result.scalars().all()
    return [
        ServiceTokenOut(
            id=t.id,
            name=t.name,
            created_at=t.created_at.isoformat(),
            last_used_at=t.last_used_at.isoformat() if t.last_used_at else None,
        )
        for t in tokens
    ]


@router.post("/tokens", response_model=ServiceTokenCreated)
async def create_token(
    data: ServiceTokenCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    raw = generate_service_token()
    token = ServiceToken(name=data.name, token_hash=hash_service_token(raw))
    db.add(token)
    await db.flush()
    return ServiceTokenCreated(
        id=token.id,
        name=token.name,
        created_at=token.created_at.isoformat(),
        last_used_at=None,
        token=raw,
    )


@router.delete("/tokens/{token_id}")
async def delete_token(
    token_id: str,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ServiceToken).where(ServiceToken.id == token_id))
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail="Token nicht gefunden")
    await db.delete(token)
    return {"ok": True}
