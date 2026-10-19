from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import require_staff
from app.models.raw_content import RawContent, RawContentStatus
from app.models.user import User
from app.schemas.raw_content import RawContentCreate, RawContentRead
from app.services.classification import process_raw_content
from app.services.ingestion import ingest_raw_content

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/raw", response_model=RawContentRead, status_code=201)
def create_raw_content(
    data: RawContentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
) -> RawContent:
    """Manual ingestion entry point (fallback / testing). Idempotent per source."""
    raw = ingest_raw_content(db, data)
    process_raw_content(db, raw)
    db.commit()
    db.refresh(raw)
    return raw


@router.get("/raw", response_model=list[RawContentRead])
def list_raw_content(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
    raw_status: RawContentStatus | None = Query(default=None, alias="status"),
) -> list[RawContent]:
    """List ingested raw publications and their processing status."""
    query = db.query(RawContent)
    if raw_status is not None:
        query = query.filter(RawContent.status == raw_status)
    return query.order_by(RawContent.created_at.desc()).all()


@router.post("/raw/{raw_id}/retry", response_model=RawContentRead)
def retry_raw_content(
    raw_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
) -> RawContent:
    """Re-run classification for a failed / needs-review item."""
    raw = db.query(RawContent).filter(RawContent.id == raw_id).first()
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw content not found")

    process_raw_content(db, raw)
    db.commit()
    db.refresh(raw)
    return raw
