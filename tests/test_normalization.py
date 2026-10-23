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
        normalize_tags(
            ["CAREER", "INTERNSHIP", "JOB", "SCIENCE", "RESEARCH", "SPORT"]
        )
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
