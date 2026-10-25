import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models  # noqa: F401
from app.db.base import Base
from app.services.dictionaries import sync_reference_data
from app.services.normalization import (
    normalize_category,
    normalize_classification,
    normalize_tag,
    normalize_tags,
)


def test_normalize_category_from_codes_and_aliases():
    import asyncio

    assert asyncio.run(normalize_category("OPPORTUNITY")) == "OPPORTUNITY"
    assert asyncio.run(normalize_category("opportunity")) == "OPPORTUNITY"
    assert asyncio.run(normalize_category("Возможности")) == "OPPORTUNITY"
    assert asyncio.run(normalize_category("  новости ")) == "NEWS"
    assert asyncio.run(normalize_category("квантовая физика")) is None


def test_normalize_tag_maps_known_values_else_none():
    import asyncio

    assert asyncio.run(normalize_tag("HACKATHON")) == "HACKATHON"
    assert asyncio.run(normalize_tag("хакатон")) == "HACKATHON"
    assert asyncio.run(normalize_tag("стажировки")) == "INTERNSHIP"
    assert asyncio.run(normalize_tag("unknown-tag")) is None


def test_normalize_tags_dedupes_reports_unresolved_and_caps_at_five():
    import asyncio

    result = asyncio.run(
        normalize_tags(["CAREER", "карьера", "INTERNSHIP", "nonsense"])
    )
    assert result.tags == ["CAREER", "INTERNSHIP"]
    assert result.unresolved_tags == ["nonsense"]
    assert result.is_fully_resolved is False

    capped = asyncio.run(
        normalize_tags(["CAREER", "INTERNSHIP", "JOB", "SCIENCE", "RESEARCH", "SPORT"])
    )
    assert capped.tags == ["CAREER", "INTERNSHIP", "JOB", "SCIENCE", "RESEARCH"]


def test_normalize_classification_reports_unresolved_category():
    import asyncio

    result = asyncio.run(
        normalize_classification({"category": "что-то", "tags": ["CAREER"]})
    )
    assert result.category is None
    assert result.unresolved_categories == ["что-то"]
    assert result.tags == ["CAREER"]


@pytest.mark.asyncio
async def test_normalization_uses_db_rows():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await sync_reference_data(session)
            await session.commit()
            # Resolvable only through the DB code, not the static alias table.
            assert await normalize_category("Учёба", db=session) == "ACADEMIC"
            assert await normalize_tag("SCIENTIFIC", db=session) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sync_reference_data_is_idempotent():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await sync_reference_data(session)
            await sync_reference_data(session)
            await session.commit()

            from sqlalchemy import func, select

            from app.models.dictionaries import Category, Tag

            cats = await session.execute(select(func.count()).select_from(Category))
            tags = await session.execute(select(func.count()).select_from(Tag))
            assert cats.scalar() == 5
            assert tags.scalar() == 25
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_legacy_tag_keeps_id_and_gets_canonical_code():
    from sqlalchemy import select
    from app.models import Tag

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            legacy = Tag(name="Волонтерство")
            db.add(legacy)
            await db.flush()
            original_id = legacy.id
            await sync_reference_data(db)
            await sync_reference_data(db)
            tags = list(await db.scalars(select(Tag).where(Tag.code == "VOLUNTEERING")))
            assert len(tags) == 1
            assert tags[0].id == original_id
            assert tags[0].name == "Волонтёрство"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_legacy_tag_merges_interests_and_post_links():
    from sqlalchemy import select
    from app.models import (
        Category,
        Post,
        StudentProfile,
        Tag,
        User,
        post_tags,
        student_interests,
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            await sync_reference_data(db)
            canonical = await db.scalar(select(Tag).where(Tag.code == "VOLUNTEERING"))
            legacy = Tag(name="Волонтерство")
            user = User(
                email="legacy@example.test",
                password_hash="unused",
                full_name="Legacy",
                role="student",
            )
            db.add_all([legacy, user])
            await db.flush()
            legacy_id = legacy.id
            db.add(StudentProfile(user_id=user.id))
            category_id = await db.scalar(
                select(Category.id).where(Category.code == "NEWS")
            )
            post = Post(
                title="Legacy",
                content="Text",
                category_id=category_id,
                author_id=user.id,
                importance="standard",
            )
            db.add(post)
            await db.flush()
            for tag_id in [legacy.id, canonical.id]:
                await db.execute(
                    student_interests.insert().values(student_id=user.id, tag_id=tag_id)
                )
                await db.execute(
                    post_tags.insert().values(post_id=post.id, tag_id=tag_id)
                )
            await sync_reference_data(db)
            assert await db.get(Tag, legacy_id) is None
            assert list(await db.scalars(select(student_interests.c.tag_id))) == [
                canonical.id
            ]
            assert list(await db.scalars(select(post_tags.c.tag_id))) == [canonical.id]
    finally:
        await engine.dispose()
