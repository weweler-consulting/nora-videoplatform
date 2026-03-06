from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.auth import require_admin
from app.models.user import User
from app.models.course import Module
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
