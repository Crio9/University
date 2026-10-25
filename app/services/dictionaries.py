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

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dictionaries import CANONICAL_CATEGORIES, CANONICAL_TAGS, DictionaryEntry
from app.models.dictionaries import Category, Tag
from app.models.post import Post, post_tags
from app.models.student_interest import student_interests
from app.services.normalization import canonical_code


async def _sync_entry(
    db: AsyncSession,
    model: type[Category] | type[Tag],
    entry: DictionaryEntry,
) -> None:
    rows = list(await db.scalars(select(model).order_by(model.id)))
    candidates = [
        row
        for row in rows
        if row.code == entry.code
        or (
            row.code is None
            and (row.name == entry.name or canonical_code(row.name) == entry.code)
        )
    ]
    row = next((row for row in candidates if row.code == entry.code), None)
    if row is None and candidates:
        row = candidates[0]

    if row is None:
        db.add(model(name=entry.name, code=entry.code))
        await db.flush()
        return

    # Reconcile aliases without losing existing interests or post-tag links.
    for duplicate in candidates:
        if duplicate.id == row.id:
            continue
        if model is Category:
            await db.execute(
                update(Post)
                .where(Post.category_id == duplicate.id)
                .values(category_id=row.id)
            )
        else:
            for table, owner in (
                (post_tags, "post_id"),
                (student_interests, "student_id"),
            ):
                owners = list(
                    await db.scalars(
                        select(table.c[owner]).where(table.c.tag_id == duplicate.id)
                    )
                )
                existing = set(
                    await db.scalars(
                        select(table.c[owner]).where(table.c.tag_id == row.id)
                    )
                )
                for owner_id in owners:
                    if owner_id not in existing:
                        await db.execute(
                            table.insert().values({owner: owner_id, "tag_id": row.id})
                        )
                await db.execute(delete(table).where(table.c.tag_id == duplicate.id))
        await db.delete(duplicate)
        await db.flush()

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
