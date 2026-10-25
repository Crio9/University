"""Content-intelligence pipeline: raw content -> structured Post.

Owns the ``pending -> processed / needs_review / failed`` state machine from
the classification spec. The AI call itself lives behind the pluggable
:class:`Classifier` protocol, so a concrete provider (MYUNI-98) can be added
without touching the pipeline or the ingestion endpoints.

Pipeline (MVP spec, section 5):
    raw content -> AI classification -> validation -> normalisation -> Post

Schema note: this codebase stores a *single* faculty/program/course per post,
while the AI contract returns lists. A one-element list is mapped directly; a
multi-value audience (e.g. courses [3, 4]) cannot be represented without losing
information, so such items are routed to ``needs_review`` instead of being
silently narrowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dictionaries import Category, Tag
from app.models.post import Post
from app.models.raw_content import RawContent, RawContentStatus
from app.models.user import User
from app.services.normalization import NormalizationResult, normalize_classification

# AI contract importance -> persisted Post.importance values used by the feed.
IMPORTANCE_MAP: dict[str, str] = {
    "LOW": "low",
    "NORMAL": "standard",
    "STANDARD": "standard",
    "HIGH": "high",
    "CRITICAL": "critical",
}


@dataclass
class ClassificationResult:
    """Validated AI output, normalised to this codebase's conventions."""

    category: str
    tags: list[str] = field(default_factory=list)
    importance: str = "standard"
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

    async def classify(self, raw: RawContent) -> dict:
        """Return the raw (unvalidated) classification payload for ``raw``."""


def get_classifier() -> Classifier | None:
    """Return the configured classifier, or ``None`` when none is configured.

    The concrete provider is added in MYUNI-98; until then ingestion items stay
    ``pending`` so nothing unvalidated is written to the structured store.
    """
    return None


def validate_payload(payload: dict) -> ClassificationResult:
    """Validate structure/types of an AI payload (raises ``ValueError``)."""
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

    importance = str(payload.get("importance") or "NORMAL").upper()
    if importance not in IMPORTANCE_MAP:
        raise ValueError(f"unsupported importance: {importance!r}")

    return ClassificationResult(
        category=category,
        tags=list(tags),
        importance=IMPORTANCE_MAP[importance],
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


async def process_raw_content(db: AsyncSession, raw: RawContent) -> RawContent:
    """Run the full pipeline for a single raw item and update its status."""
    classifier = get_classifier()
    if classifier is None:
        # No provider configured yet: keep the item queued, write nothing.
        raw.status = RawContentStatus.PENDING.value
        await db.flush()
        return raw

    try:
        payload = await classifier.classify(raw)
        result = validate_payload(payload)
    except Exception as exc:  # noqa: BLE001 - persist failures for diagnosis
        raw.status = RawContentStatus.FAILED.value
        raw.processing_error = f"{type(exc).__name__}: {exc}"
        raw.processed_at = datetime.now(timezone.utc)
        await db.flush()
        return raw

    normalized: NormalizationResult = await normalize_classification(
        {"category": result.category, "tags": result.tags}, db=db
    )
    if normalized.category is None or not normalized.is_fully_resolved:
        await _mark_needs_review(
            db,
            raw,
            "unresolved values: " + ", ".join(normalized.unresolved),
        )
        return raw

    # This schema keeps a single audience value per dimension.
    audience_problem = _single_value_problem(result)
    if audience_problem is not None:
        await _mark_needs_review(db, raw, audience_problem)
        return raw

    category = await _category_by_code(db, normalized.category)
    if category is None:
        await _mark_needs_review(
            db, raw, f"category {normalized.category} missing from reference data"
        )
        return raw

    tags = await _tags_by_codes(db, normalized.tags)

    author_id = await _fallback_author_id(db)
    if author_id is None:
        await _mark_needs_review(
            db, raw, "no staff/admin user available as post author"
        )
        return raw

    post = Post(
        title=(result.title or _derive_title(raw.raw_text)),
        content=raw.raw_text,
        summary=(result.summary or "").strip() or None,
        category_id=category.id,
        author_id=author_id,
        raw_content_id=raw.id,
        ai_confidence=result.confidence,
        importance=result.importance,
        deadline=result.deadline,
        target_faculty=_first(result.target_faculty),
        target_program=_first(result.target_program),
        target_course=_first(result.target_course),
        tags=tags,
    )
    db.add(post)
    raw.status = RawContentStatus.PROCESSED.value
    raw.processing_error = None
    raw.processed_at = datetime.now(timezone.utc)
    await db.flush()
    return raw


def _single_value_problem(result: ClassificationResult) -> str | None:
    for field_name in ("target_faculty", "target_program", "target_course"):
        values = getattr(result, field_name)
        if len(values) > 1:
            return (
                f"ambiguous audience: {field_name} has {len(values)} values, "
                "the schema supports a single value"
            )
    return None


def _first(values: list):
    return values[0] if values else None


async def _mark_needs_review(
    db: AsyncSession, raw: RawContent, reason: str
) -> None:
    raw.status = RawContentStatus.NEEDS_REVIEW.value
    raw.processing_error = reason
    raw.processed_at = datetime.now(timezone.utc)
    await db.flush()


async def _category_by_code(db: AsyncSession, code: str) -> Category | None:
    result = await db.execute(select(Category).where(Category.code == code))
    return result.scalar_one_or_none()


async def _tags_by_codes(db: AsyncSession, codes: list[str]) -> list[Tag]:
    if not codes:
        return []
    result = await db.execute(select(Tag).where(Tag.code.in_(codes)))
    return list(result.scalars().all())


def _derive_title(text: str, limit: int = 80) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return (first_line or "Публикация")[:limit]


async def _fallback_author_id(db: AsyncSession):
    """Author for AI-created posts: the first staff/admin user, if any."""
    result = await db.execute(
        select(User)
        .where(User.role.in_(["staff", "admin"]))
        .order_by(User.created_at.asc())
        .limit(1)
    )
    user = result.scalar_one_or_none()
    return user.id if user else None
