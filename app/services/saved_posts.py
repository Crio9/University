"""Saved (bookmarked) publications for the current user."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.models.saved_post import UserSavedPost


async def saved_post_ids(db: AsyncSession, user_id: int) -> set[int]:
    """Return the set of post ids the user has saved."""
    result = await db.execute(
        select(UserSavedPost.post_id).where(UserSavedPost.user_id == user_id)
    )
    return set(result.scalars().all())


async def is_saved(db: AsyncSession, user_id: int, post_id: int) -> bool:
    result = await db.execute(
        select(UserSavedPost).where(
            UserSavedPost.user_id == user_id,
            UserSavedPost.post_id == post_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def save_post(db: AsyncSession, user_id: int, post_id: int) -> bool:
    """Idempotently save a post. Returns ``True`` if newly created."""
    if await is_saved(db, user_id, post_id):
        return False
    db.add(UserSavedPost(user_id=user_id, post_id=post_id))
    await db.flush()
    return True


async def unsave_post(db: AsyncSession, user_id: int, post_id: int) -> bool:
    """Idempotently remove a saved post. Returns ``True`` if a row was removed."""
    result = await db.execute(
        select(UserSavedPost).where(
            UserSavedPost.user_id == user_id,
            UserSavedPost.post_id == post_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        return False
    await db.delete(link)
    await db.flush()
    return True


async def list_saved_posts(db: AsyncSession, user_id: int) -> list[Post]:
    result = await db.execute(
        select(Post)
        .join(UserSavedPost, UserSavedPost.post_id == Post.id)
        .where(UserSavedPost.user_id == user_id)
        .order_by(UserSavedPost.created_at.desc())
    )
    return list(result.scalars().all())
