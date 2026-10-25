from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.auth import require_roles
from app.models.raw_content import RawContent, RawContentStatus
from app.models.user import User
from app.schemas.raw_content import RawContentCreate, RawContentRead
from app.services.classification import process_raw_content
from app.services.ingestion import ingest_raw_content
from app.services import classification
from app.services.processing import get_processing_session_factory, process_raw_ids

router = APIRouter(prefix="/ingest", tags=["ingest"])

require_staff = require_roles("staff", "admin")


@router.post("/process-pending")
async def process_pending(
    background_tasks: BackgroundTasks,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
    session_factory=Depends(get_processing_session_factory),
):
    if classification.get_classifier() is None:
        raise HTTPException(status_code=503, detail="NVIDIA_API_KEY is not configured")
    ids = list(
        await db.scalars(
            select(RawContent.id)
            .where(RawContent.status == "pending")
            .order_by(RawContent.id)
            .limit(limit)
        )
    )
    background_tasks.add_task(process_raw_ids, ids, session_factory)
    return {"queued": len(ids)}


@router.post("/raw", response_model=RawContentRead, status_code=201)
async def create_raw_content(
    data: RawContentCreate,
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    """Manual ingestion entry point (fallback / testing). Idempotent per source."""
    raw = await ingest_raw_content(db, data)
    # Keep the source durable even if the provider request is interrupted.
    await db.commit()
    await process_raw_content(db, raw)
    await db.commit()
    await db.refresh(raw)
    return raw


@router.get("/raw", response_model=list[RawContentRead])
async def list_raw_content(
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    """List ingested raw publications and their processing status."""
    query = select(RawContent).order_by(RawContent.created_at.desc())
    if status_filter is not None:
        if status_filter not in {s.value for s in RawContentStatus}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unknown status",
            )
        query = query.where(RawContent.status == status_filter)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/raw/{raw_id}/retry", response_model=RawContentRead)
async def retry_raw_content(
    raw_id: int,
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    """Re-run classification for a failed / needs-review item."""
    raw = await db.get(RawContent, raw_id)
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Raw content not found",
        )

    await process_raw_content(db, raw)
    await db.commit()
    await db.refresh(raw)
    return raw
