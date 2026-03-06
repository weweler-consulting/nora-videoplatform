from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.auth import require_admin
from app.models.user import User
from app.models.course import Section
from app.schemas.course import SectionCreate, SectionUpdate

router = APIRouter()


@router.post("/", response_model=dict)
async def create_section(data: SectionCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    section = Section(**data.model_dump())
    db.add(section)
    await db.flush()
    return {"id": section.id}


@router.put("/{section_id}", response_model=dict)
async def update_section(section_id: str, data: SectionUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Section).where(Section.id == section_id))
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(section, key, value)
    return {"id": section.id}


@router.delete("/{section_id}")
async def delete_section(section_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Section).where(Section.id == section_id))
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    await db.delete(section)
    return {"ok": True}
