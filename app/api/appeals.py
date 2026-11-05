"""REST routes for Sprint 3 student appeals; business rules live in services."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import User
from app.schemas.appeal import AppealCreate, AppealResponse, AppealUpdate
from app.services.appeals import (
    change_status,
    create_appeal as create_appeal_service,
    get_appeal as get_appeal_service,
    list_appeals,
)

router = APIRouter(prefix="/appeals", tags=["appeals"])


@router.post("", response_model=AppealResponse, status_code=status.HTTP_201_CREATED)
async def create_appeal(
    data: AppealCreate,
    current_user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    return await create_appeal_service(db, current_user, data)


@router.get("/my", response_model=list[AppealResponse], include_in_schema=False)
@router.get("/me", response_model=list[AppealResponse])
async def get_my_appeals(
    current_user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    return await list_appeals(db, current_user)


@router.get("", response_model=list[AppealResponse])
async def get_all_appeals(
    current_user: User = Depends(require_roles("staff", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await list_appeals(db, current_user)


@router.get("/{appeal_id}", response_model=AppealResponse)
async def get_appeal(
    appeal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_appeal_service(db, current_user, appeal_id)


@router.patch("/{appeal_id}", response_model=AppealResponse, include_in_schema=False)
@router.patch("/{appeal_id}/status", response_model=AppealResponse)
async def update_appeal_status(
    appeal_id: int,
    data: AppealUpdate,
    current_user: User = Depends(require_roles("staff", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await change_status(db, current_user, appeal_id, data)
