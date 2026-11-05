"""Appeal business rules for Sprint 3 (FR-4 and FR-5).

MVP contract: each new appeal is addressed to an existing staff user. The
existing appeals.staff_id field stores that recipient; staff can only handle
appeals addressed to them. Admin can handle all. Legacy rows with staff_id
NULL remain accessible to admin, without an unsafe guessed assignment.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appeal import Appeal
from app.models.user import User
from app.schemas.appeal import AppealCreate, AppealUpdate

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"IN_REVIEW"},
    "IN_REVIEW": {"CLOSED"},
    "CLOSED": set(),
}


def _scope(user: User):
    """Staff sees their assigned appeals; admin sees all; student sees own."""
    if user.role == "admin":
        return None
    if user.role == "staff":
        return Appeal.staff_id == user.id
    if user.role == "student":
        return Appeal.student_id == user.id
    raise HTTPException(status_code=403, detail="Insufficient permissions")


async def create_appeal(db: AsyncSession, student: User, payload: AppealCreate) -> Appeal:
    # Validate the recipient independently of any supplied student/author ID.
    recipient = await db.get(User, payload.recipient_id)
    if recipient is None:
        raise HTTPException(status_code=404, detail="Recipient not found")
    if recipient.role != "staff":
        raise HTTPException(status_code=422, detail="Recipient must be a staff user")
    row = Appeal(
        student_id=student.id,
        staff_id=recipient.id,
        category=payload.category.value,
        subject=payload.subject,
        message=payload.message,
        status="CREATED",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_appeals(db: AsyncSession, user: User) -> list[Appeal]:
    stmt = select(Appeal).order_by(Appeal.created_at.desc(), Appeal.id.desc())
    scope = _scope(user)
    if scope is not None:
        stmt = stmt.where(scope)
    return list((await db.scalars(stmt)).all())


async def get_appeal(db: AsyncSession, user: User, appeal_id: int) -> Appeal:
    stmt = select(Appeal).where(Appeal.id == appeal_id)
    scope = _scope(user)
    if scope is not None:
        stmt = stmt.where(scope)
    row = await db.scalar(stmt)
    if row is None:
        # 404 both for nonexistent and out-of-scope IDs, avoiding ID disclosure.
        raise HTTPException(status_code=404, detail="Appeal not found")
    return row


async def change_status(
    db: AsyncSession, user: User, appeal_id: int, payload: AppealUpdate
) -> Appeal:
    if user.role not in ("staff", "admin"):
        raise HTTPException(status_code=403, detail="Staff or admin required")
    stmt = select(Appeal).where(Appeal.id == appeal_id).with_for_update()
    scope = _scope(user)
    if scope is not None:
        stmt = stmt.where(scope)
    row = await db.scalar(stmt)
    if row is None:
        raise HTTPException(status_code=404, detail="Appeal not found")
    if payload.status.value not in ALLOWED_TRANSITIONS.get(row.status, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transition {row.status} -> {payload.status.value} is not allowed",
        )
    row.status = payload.status.value
    if "staff_response" in payload.model_fields_set:
        row.staff_response = payload.staff_response
    # Staff ID remains the recipient, not the last user who edited the case.
    await db.commit()
    await db.refresh(row)
    return row
