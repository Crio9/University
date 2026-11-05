from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.auth import require_roles
from app.models.appeal import Appeal
from app.models.user import User
from app.schemas.appeal import AppealCreate, AppealResponse, AppealUpdate

router = APIRouter(prefix="/appeals", tags=["appeals"])


@router.post(
    "",
    response_model=AppealResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_appeal(
    data: AppealCreate,
    current_user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    appeal = Appeal(
        student_id=current_user.id,
        category=data.category.value,
        subject=data.subject,
        message=data.message,
        status="CREATED",
    )

    db.add(appeal)
    await db.commit()
    await db.refresh(appeal)
    return appeal


@router.get("/my", response_model=list[AppealResponse])
async def get_my_appeals(
    current_user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Appeal)
        .where(Appeal.student_id == current_user.id)
        .order_by(Appeal.created_at.desc())
    )
    return result.scalars().all()


@router.get("", response_model=list[AppealResponse])
async def get_all_appeals(
    current_user: User = Depends(require_roles("staff", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Appeal).order_by(Appeal.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{appeal_id}", response_model=AppealResponse)
async def get_appeal(
    appeal_id: int,
    current_user: User = Depends(require_roles("staff", "admin")),
    db: AsyncSession = Depends(get_db),
):
    appeal = await db.get(Appeal, appeal_id)

    if appeal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appeal not found",
        )

    return appeal


@router.patch("/{appeal_id}", response_model=AppealResponse)
async def update_appeal(
    appeal_id: int,
    data: AppealUpdate,
    current_user: User = Depends(require_roles("staff", "admin")),
    db: AsyncSession = Depends(get_db),
):
    appeal = await db.get(Appeal, appeal_id)

    if appeal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appeal not found",
        )

    if appeal.status == "CLOSED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Closed appeal cannot be changed",
        )

    appeal.status = data.status.value
    appeal.staff_response = data.staff_response
    appeal.staff_id = current_user.id

    await db.commit()
    await db.refresh(appeal)
    return appeal