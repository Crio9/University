"""Single idempotent RawContent -> validated classification -> canonical Post pipeline."""

import json
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Category, Post, RawContent, RawContentStatus, Tag, User
from app.schemas.ai_classification import AIClassificationResult
from app.services.ai_classifier import AIProvider, NVIDIAAIProvider
from app.services.audience import normalize_audience
from app.services.normalization import normalize_classification

IMPORTANCE_MAP = {
    "LOW": "low",
    "NORMAL": "standard",
    "HIGH": "high",
    "CRITICAL": "critical",
}


class NeedsReview(ValueError):
    pass


class Classifier(Protocol):
    async def classify(self, raw: RawContent) -> AIClassificationResult | dict: ...


class RawContentClassifier:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    async def classify(self, raw: RawContent) -> AIClassificationResult:
        published_at = raw.source_published_at or raw.created_at
        if published_at is not None and published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        return await self.provider.classify(
            title=_derive_title(raw.raw_text),
            content=raw.raw_text,
            context={
                "source_type": raw.source_type,
                "source_url": raw.source_url,
                "published_at": (
                    published_at.isoformat() if published_at is not None else None
                ),
            },
        )


def get_classifier() -> Classifier | None:
    return RawContentClassifier(NVIDIAAIProvider()) if settings.NVIDIA_API_KEY else None


def validate_payload(payload) -> AIClassificationResult:
    return AIClassificationResult.model_validate(payload)


async def process_raw_content(
    db: AsyncSession, raw: RawContent, *, skip_locked=False
) -> RawContent:
    await db.flush()
    # Serialize retries and workers. Refresh the ORM object after waiting for a lock.
    locked = await db.scalar(
        select(RawContent)
        .where(RawContent.id == raw.id)
        .with_for_update(skip_locked=skip_locked)
        .execution_options(populate_existing=True)
    )
    if locked is None:
        return raw
    raw = locked
    existing = await db.scalar(select(Post.id).where(Post.raw_content_id == raw.id))
    if existing is not None:
        raw.status = RawContentStatus.PROCESSED.value
        raw.processing_error = None
        await db.flush()
        return raw

    classifier = get_classifier()
    if classifier is None:
        raw.status = RawContentStatus.PENDING.value
        raw.processing_error = None
        raw.processed_at = None
        await db.flush()
        return raw

    raw.ai_result = None
    try:
        payload = await classifier.classify(raw)
        if isinstance(payload, AIClassificationResult):
            payload = payload.model_dump(mode="json")
        if isinstance(payload, dict):
            raw.ai_result = json.loads(json.dumps(payload, default=str))
        result = validate_payload(payload)
        normalized = await normalize_classification(result.model_dump(), db=db)
        if normalized.category is None or not normalized.is_fully_resolved:
            raise NeedsReview(
                "Unresolved references: " + ", ".join(normalized.unresolved)
            )
        audience, unresolved = await normalize_audience(db, result.target_audience)
        if unresolved:
            raise NeedsReview("Unresolved audience: " + ", ".join(unresolved))
        category = await db.scalar(
            select(Category).where(Category.code == normalized.category)
        )
        tags = list(
            (await db.scalars(select(Tag).where(Tag.code.in_(normalized.tags)))).all()
        )
        missing = set(normalized.tags) - {tag.code for tag in tags}
        if category is None or missing:
            raise NeedsReview("Canonical reference data is missing; run seed.py")
        author_id = await db.scalar(
            select(User.id)
            .where(User.role.in_(["staff", "admin"]))
            .order_by(User.id)
            .limit(1)
        )
        if author_id is None:
            raise NeedsReview("No staff/admin author is available")
        # Keep a failed insert from invalidating the outer raw-content transaction.
        async with db.begin_nested():
            post = Post(
                title=_derive_title(raw.raw_text),
                content=raw.raw_text,
                category_id=category.id,
                author_id=author_id,
                raw_content_id=raw.id,
                summary=result.summary,
                ai_confidence=result.confidence,
                importance=IMPORTANCE_MAP[result.importance],
                deadline=result.deadline,
                target_audience=audience.model_dump(),
                target_faculty=_single(audience.faculty),
                target_program=_single(audience.program),
                target_course=_single(audience.course),
                tags=tags,
            )
            db.add(post)
            await db.flush()
        raw.status = RawContentStatus.PROCESSED.value
        raw.processing_error = None
    except NeedsReview as exc:
        raw.status = RawContentStatus.NEEDS_REVIEW.value
        raw.processing_error = str(exc)[:2000]
    except Exception as exc:
        raw.status = RawContentStatus.FAILED.value
        raw.processing_error = f"{type(exc).__name__}: {exc}"[:2000]
    raw.processed_at = datetime.now(timezone.utc)
    await db.flush()
    return raw


def _single(values):
    return values[0] if len(values) == 1 else None


def _derive_title(text):
    return next(
        (line.strip()[:80] for line in text.splitlines() if line.strip()), "Публикация"
    )
