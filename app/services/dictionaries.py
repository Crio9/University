"""Reference-data synchronisation for categories and tags.

Keeps the ``categories`` / ``tags`` tables in sync with the canonical
vocabulary defined in :mod:`app.core.dictionaries`. The operation is idempotent
and safe to call repeatedly (seed, migrations, admin tooling).

Existing rows are reconciled rather than duplicated: categories and tags created
before the canonical vocabulary existed are matched by their display name and
receive the corresponding machine ``code`` in place, so all foreign keys remain
intact.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dictionaries import CANONICAL_CATEGORIES, CANONICAL_TAGS, DictionaryEntry
from app.models.dictionaries import Category, Tag


async def _sync_entry(
    db: AsyncSession,
    model: type[Category] | type[Tag],
    entry: DictionaryEntry,
) -> None:
    # 1) Preferred match: the canonical machine code.
    result = await db.execute(select(model).where(model.code == entry.code))
    row = result.scalar_one_or_none()

    # 2) Fallback: an existing row with the same display name (legacy data).
    if row is None:
        result = await db.execute(select(model).where(model.name == entry.name))
        row = result.scalar_one_or_none()

    if row is None:
        db.add(model(name=entry.name, code=entry.code))
        await db.flush()
        return

    changed = False
    if row.code != entry.code:
        row.code = entry.code
        changed = True
    if row.name != entry.name:
        row.name = entry.name
        changed = True
    if changed:
        await db.flush()


async def sync_reference_data(db: AsyncSession) -> None:
    """Ensure all canonical categories and tags exist. Idempotent."""
    for entry in CANONICAL_CATEGORIES:
        await _sync_entry(db, Category, entry)
    for entry in CANONICAL_TAGS:
        await _sync_entry(db, Tag, entry)
