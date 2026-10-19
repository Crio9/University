"""Reference-data synchronisation for categories and tags.

Keeps the ``categories`` / ``tags`` tables in sync with the canonical
vocabulary defined in :mod:`app.core.dictionaries`. The operation is idempotent
and safe to call repeatedly (seed, migrations, admin tooling).

Legacy rows (created during Sprint 1) are *reconciled* rather than duplicated:
if an existing row matches the canonical entry only by a legacy slug, it is
renamed in place so all foreign keys stay intact.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.dictionaries import CANONICAL_CATEGORIES, CANONICAL_TAGS, DictionaryEntry
from app.models.dictionaries import Category, Tag

# Legacy slug (Sprint 1) -> canonical code, so existing rows are reused.
LEGACY_CATEGORY_SLUGS: dict[str, str] = {
    "admin": "ADMINISTRATIVE",
    "opportunities": "OPPORTUNITY",
}

LEGACY_TAG_SLUGS: dict[str, str] = {
    "career": "CAREER",
    "internships": "INTERNSHIP",
    "science": "SCIENCE",
    "conferences": "CONFERENCE",
    "scholarships": "SCHOLARSHIP",
    "volunteering": "VOLUNTEERING",
    "dormitory": "DORMITORY",
    "documents": "DOCUMENTS",
    "sport": "SPORT",
}


def slug_for_code(code: str) -> str:
    """Canonical DB slug for a machine code (lower-case)."""
    return code.lower()


def _sync_entry(
    db: Session,
    model: type[Category] | type[Tag],
    entry: DictionaryEntry,
    legacy_slugs: dict[str, str],
) -> None:
    slug = slug_for_code(entry.code)
    row = db.query(model).filter(model.slug == slug).first()
    if row is None:
        # Try to reuse a legacy row mapped to this canonical code.
        legacy = next(
            (s for s, code in legacy_slugs.items() if code == entry.code), None
        )
        if legacy is not None:
            row = db.query(model).filter(model.slug == legacy).first()
        if row is not None:
            row.slug = slug
            row.name = entry.name
            db.flush()
            return
        db.add(model(name=entry.name, slug=slug))
        db.flush()
        return
    if row.name != entry.name:
        row.name = entry.name
        db.flush()


def sync_reference_data(db: Session) -> None:
    """Ensure all canonical categories and tags exist. Idempotent."""
    for entry in CANONICAL_CATEGORIES:
        _sync_entry(db, Category, entry, LEGACY_CATEGORY_SLUGS)
    for entry in CANONICAL_TAGS:
        _sync_entry(db, Tag, entry, LEGACY_TAG_SLUGS)
