
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dictionaries import Category, Tag
from app.models.post import Post
from app.schemas.ai_classification import AIClassificationResult


IMPORTANCE_MAP = {
    "LOW": "low",
    "NORMAL": "standard",
    "HIGH": "high",
    "CRITICAL": "critical",
}

CATEGORY_MAP = {
    "ACADEMIC": "ACADEMIC",
    "ADMINISTRATIVE": "ADMINISTRATIVE",
    "OPPORTUNITY": "OPPORTUNITY",
    "EVENT": "EVENT",
    "NEWS": "NEWS",
}


async def get_or_create_category(
    db: AsyncSession,
    name: str,
) -> Category:
    result = await db.execute(
        select(Category).where(Category.name == name)
    )
    category = result.scalar_one_or_none()

    if category is None:
        category = Category(name=name)
        db.add(category)
        await db.flush()

    return category


async def get_or_create_tag(
    db: AsyncSession,
    name: str,
) -> Tag:
    normalized_name = name.strip()[:100]

    result = await db.execute(
        select(Tag).where(Tag.name == normalized_name)
    )
    tag = result.scalar_one_or_none()

    if tag is None:
        tag = Tag(name=normalized_name)
        db.add(tag)
        await db.flush()

    return tag


async def create_post_from_classification(
    db: AsyncSession,
    *,
    title: str,
    content: str,
    author_id: int,
    classification: AIClassificationResult,
) -> Post:
    """Создаёт публикацию из проверенного результата AI."""

    category_name = CATEGORY_MAP[classification.category]
    category = await get_or_create_category(db, category_name)

    audience = classification.target_audience

    post = Post(
        title=title[:255],
        content=content,
        author_id=author_id,
        category_id=category.id,
        importance=IMPORTANCE_MAP[classification.importance],
        deadline=classification.deadline,
        target_faculty=(
            audience.faculty[0][:255]
            if audience.faculty else None
        ),
        target_program=(
            audience.program[0][:255]
            if audience.program else None
        ),
        target_course=(
            audience.course[0]
            if audience.course else None
        ),
    )

    for tag_name in classification.tags:
        normalized_name = tag_name.strip()[:100]
        if normalized_name:
            tag = await get_or_create_tag(db, normalized_name)
            if all(existing.name != tag.name for existing in post.tags):
                post.tags.append(tag)

    db.add(post)
    await db.flush()
    await db.refresh(post)

    return post