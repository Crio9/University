from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.dictionaries import Category, Tag
from app.schemas.post import CategoryRead, TagRead

router = APIRouter(tags=["dictionaries"])


@router.get("/tags", response_model=list[TagRead])
def list_tags(db: Session = Depends(get_db)) -> list[Tag]:
    return db.query(Tag).order_by(Tag.name.asc()).all()


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db)) -> list[Category]:
    return db.query(Category).order_by(Category.name.asc()).all()
