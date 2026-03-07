from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.auth import require_admin
from app.models.user import User
from app.models.course import Module, ModuleUnlock
from app.schemas.course import ModuleCreate, ModuleUpdate

router = APIRouter()


@router.post("/", response_model=dict)
async def create_module(data: ModuleCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    module = Module(**data.model_dump())
    db.add(module)
    await db.flush()
    return {"id": module.id}


@router.put("/{module_id}", response_model=dict)
async def update_module(module_id: str, data: ModuleUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(module, key, value)
    return {"id": module.id}


@router.delete("/{module_id}")
async def delete_module(module_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    await db.delete(module)
    return {"ok": True}


@router.post("/{module_id}/unlock/{user_id}")
async def unlock_module_for_user(module_id: str, user_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(ModuleUnlock).where(ModuleUnlock.module_id == module_id, ModuleUnlock.user_id == user_id)
    )
    if existing.scalar_one_or_none():
        return {"ok": True}
    db.add(ModuleUnlock(user_id=user_id, module_id=module_id))
    return {"ok": True}


@router.delete("/{module_id}/unlock/{user_id}")
async def lock_module_for_user(module_id: str, user_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ModuleUnlock).where(ModuleUnlock.module_id == module_id, ModuleUnlock.user_id == user_id)
    )
    unlock = result.scalar_one_or_none()
    if unlock:
        await db.delete(unlock)
    return {"ok": True}
