from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth import login_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await register_user(db, data)


@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login_user(db, data)
