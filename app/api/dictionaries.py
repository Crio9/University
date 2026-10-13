from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.dictionaries import Category, Tag
from app.schemas.dictionary import CategoryRead, TagRead

router = APIRouter(tags=["dictionaries"])


@router.get("/tags", response_model=list[TagRead])
async def get_tags(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tag).order_by(Tag.id.asc()))
    return result.scalars().all()


@router.get("/categories", response_model=list[CategoryRead])
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).order_by(Category.id.asc()))
    return result.scalars().all()
