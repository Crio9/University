"""Normalisation of AI classifier output onto canonical references.

The AI describes *properties* of a publication (category, tags, audience...).
This module maps the free-form strings it may return onto the approved
vocabulary and reports anything that cannot be safely mapped, so the caller can
mark the source as ``needs_review`` instead of writing bad data.

The static alias table in :mod:`app.core.dictionaries` works without a DB
session; when a session is passed we additionally match existing DB rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dictionaries import ALIASES, CATEGORY_CODES, TAG_CODES, normalise_key
from app.models.dictionaries import Category, Tag


@dataclass
class NormalizationResult:
    """Outcome of normalising AI output.

    ``unresolved`` holds raw values that could not be mapped. When it is
    non-empty the caller should treat the item as ``needs_review`` rather than
    silently dropping information.
    """

    category: str | None = None
    tags: list[str] = field(default_factory=list)
    unresolved_categories: list[str] = field(default_factory=list)
    unresolved_tags: list[str] = field(default_factory=list)

    @property
    def is_fully_resolved(self) -> bool:
        return not self.unresolved_categories and not self.unresolved_tags

    @property
    def unresolved(self) -> list[str]:
        return [*self.unresolved_categories, *self.unresolved_tags]


def canonical_code(value: str) -> str | None:
    """Map a raw string onto a canonical code, or return ``None``."""
    if not value:
        return None
    key = normalise_key(value)
    if not key:
        return None
    upper = value.strip().upper()
    if upper in CATEGORY_CODES or upper in TAG_CODES:
        return upper
    return ALIASES.get(key)


async def normalize_category(
    value: str | None, *, db: AsyncSession | None = None
) -> str | None:
    """Return a canonical category code or ``None`` if it cannot be resolved."""
    if value is None:
        return None
    code = canonical_code(value)
    if code in CATEGORY_CODES:
        return code
    if db is not None:
        row = await _match_existing(db, Category, value)
        if row is not None and row.code in CATEGORY_CODES:
            return row.code
    return None


async def normalize_tag(value: str, *, db: AsyncSession | None = None) -> str | None:
    """Return a canonical tag code or ``None`` if it cannot be resolved."""
    code = canonical_code(value)
    if code in TAG_CODES:
        return code
    if db is not None:
        row = await _match_existing(db, Tag, value)
        if row is not None and row.code in TAG_CODES:
            return row.code
    return None


async def _match_existing(
    db: AsyncSession, model: type[Category] | type[Tag], value: str
):
    stripped = value.strip()
    if not stripped:
        return None
    result = await db.scalars(select(model))
    return next(
        (row for row in result if row.name.casefold() == stripped.casefold()), None
    )


async def normalize_tags(
    values: list[str] | None,
    *,
    db: AsyncSession | None = None,
    limit: int | None = 5,
) -> NormalizationResult:
    """Normalise a list of raw tags, preserving order and de-duplicating."""
    result = NormalizationResult()
    if not values:
        return result
    seen: set[str] = set()
    for raw in values:
        code = await normalize_tag(raw, db=db) if isinstance(raw, str) else None
        if code is None:
            result.unresolved_tags.append(str(raw))
            continue
        if code not in seen:
            seen.add(code)
            result.tags.append(code)
    # The vocabulary recommends 0-5 tags.
    if limit is not None and len(result.tags) > limit:
        result.tags = result.tags[:limit]
    return result


async def normalize_classification(
    payload: dict, *, db: AsyncSession | None = None
) -> NormalizationResult:
    """Normalise a full AI-classification payload.

    Only ``category`` and ``tags`` are resolved here; audience fields are handled
    by domain rules (see the classification spec, section 6).
    """
    result = await normalize_tags(payload.get("tags"), db=db)
    raw_category = payload.get("category")
    code = await normalize_category(raw_category, db=db)
    if raw_category is not None and code is None:
        result.unresolved_categories.append(str(raw_category))
    result.category = code
    return result
