"""Content-intelligence pipeline: raw content -> structured Post.

This module owns the ``pending -> processed / needs_review / failed`` state
machine from the classification spec. The actual AI call lives behind the
pluggable :class:`Classifier` protocol so the provider (MYUNI-98) can be added
without touching the pipeline or the ingestion endpoints.

Pipeline (section 5 of the MVP spec):
    raw content -> AI classification -> Pydantic/domain validation
    -> normalisation by reference data -> structured Post
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.orm import Session

from app.models.dictionaries import Category, Tag
from app.models.post import Post
from app.models.raw_content import RawContent, RawContentStatus
from app.services.dictionaries import slug_for_code
from app.services.normalization import normalize_classification


@dataclass
class ClassificationResult:
    """Validated, normalised AI output ready to be persisted as a Post."""

    category: str
    tags: list[str] = field(default_factory=list)
    importance: str | None = None
    deadline: datetime | None = None
    summary: str | None = None
    confidence: float | None = None
    target_faculty: list[str] = field(default_factory=list)
    target_program: list[str] = field(default_factory=list)
    target_course: list[int] = field(default_factory=list)
    target_group: list[str] = field(default_factory=list)
    title: str | None = None


class Classifier(Protocol):
    """Adapter for an AI classification provider."""

    def classify(self, raw: RawContent) -> dict:
        """Return the raw (unvalidated) classification payload for ``raw``."""


def get_classifier() -> Classifier | None:
    """Return the configured classifier, or ``None`` when none is configured.

    The concrete provider is added in MYUNI-98; until then ingestion items stay
    ``pending`` so nothing is written to the structured store unvalidated.
    """
    return None


def validate_payload(payload: dict) -> ClassificationResult:
    """Validate the structure/types of an AI payload (raises ``ValueError``)."""
    if not isinstance(payload, dict):
        raise ValueError("classification payload must be an object")

    category = payload.get("category")
    if not isinstance(category, str) or not category.strip():
        raise ValueError("classification payload requires a 'category'")

    tags = payload.get("tags") or []
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise ValueError("'tags' must be a list of strings")

    deadline = payload.get("deadline")
    if deadline is not None and not isinstance(deadline, str):
        raise ValueError("'deadline' must be a string or null")

    confidence = payload.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("'confidence' must be a number within [0, 1]")

    return ClassificationResult(
        category=category,
        tags=[t for t in tags],
        importance=payload.get("importance"),
        deadline=_parse_datetime(deadline),
        summary=(payload.get("summary") or None),
        confidence=None if confidence is None else float(confidence),
        target_faculty=_as_str_list(payload.get("target_faculty")),
        target_program=_as_str_list(payload.get("target_program")),
        target_course=_as_int_list(payload.get("target_course")),
        target_group=_as_str_list(payload.get("target_group")),
        title=payload.get("title"),
    )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid deadline: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _as_str_list(value: object) -> list[str]:
    if not value:
        return []
    if not isinstance(value, list):
        raise ValueError("audience fields must be lists")
    return [str(v) for v in value]


def _as_int_list(value: object) -> list[int]:
    if not value:
        return []
    if not isinstance(value, list):
        raise ValueError("audience fields must be lists")
    return [int(v) for v in value]


def process_raw_content(db: Session, raw: RawContent) -> RawContent:
    """Run the full pipeline for a single raw item and update its status."""
    classifier = get_classifier()
    if classifier is None:
        # No provider configured yet: keep the item queued, do not write bad data.
        raw.status = RawContentStatus.PENDING
        db.flush()
        return raw

    try:
        payload = classifier.classify(raw)
        result = validate_payload(payload)
    except Exception as exc:  # noqa: BLE001 - persist any failure for diagnosis
        raw.status = RawContentStatus.FAILED
        raw.processing_error = f"{type(exc).__name__}: {exc}"
        raw.processed_at = datetime.now(timezone.utc)
        db.flush()
        return raw

    normalized = normalize_classification(
        {"category": result.category, "tags": result.tags}, db=db
    )
    if normalized.category is None or not normalized.is_fully_resolved:
        raw.status = RawContentStatus.NEEDS_REVIEW
        raw.processing_error = "unresolved values: " + ", ".join(normalized.unresolved)
        raw.processed_at = datetime.now(timezone.utc)
        db.flush()
        return raw

    category = (
        db.query(Category)
        .filter(Category.slug == slug_for_code(normalized.category))
        .one_or_none()
    )
    if category is None:
        raw.status = RawContentStatus.NEEDS_REVIEW
        raw.processing_error = f"category {normalized.category} missing from reference data"
        raw.processed_at = datetime.now(timezone.utc)
        db.flush()
        return raw

    tags = (
        db.query(Tag)
        .filter(Tag.slug.in_([slug_for_code(code) for code in normalized.tags]))
        .all()
    )

    author_id = _fallback_author_id(db)
    if author_id is None:
        raw.status = RawContentStatus.NEEDS_REVIEW
        raw.processing_error = "no staff/admin user available as post author"
        raw.processed_at = datetime.now(timezone.utc)
        db.flush()
        return raw

    summary = (result.summary or "").strip() or None
    post = Post(
        title=(result.title or _derive_title(raw.raw_text)),
        body=raw.raw_text,
        summary=summary,
        category_id=category.id,
        author_id=author_id,
        raw_content_id=raw.id,
        ai_confidence=result.confidence,
        target_faculties=result.target_faculty,
        target_courses=result.target_course,
        deadline=result.deadline,
        tags=tags,
    )
    db.add(post)
    raw.status = RawContentStatus.PROCESSED
    raw.processing_error = None
    raw.processed_at = datetime.now(timezone.utc)
    db.flush()
    return raw


def _derive_title(text: str, limit: int = 80) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    title = first_line or "Публикация"
    return title[:limit]


def _fallback_author_id(db: Session):
    """Author for AI-created posts: the first staff/admin user, if any."""
    from app.models.user import User, UserRole

    user = (
        db.query(User)
        .filter(User.role.in_([UserRole.STAFF, UserRole.ADMIN]))
        .order_by(User.created_at.asc())
        .first()
    )
    return user.id if user else None
