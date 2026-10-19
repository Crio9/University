"""Saved (bookmarked) publications for the current user."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.saved_post import UserSavedPost


def saved_post_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Return the set of post ids the user has saved."""
    rows = db.execute(
        select(UserSavedPost.post_id).where(UserSavedPost.user_id == user_id)
    ).scalars()
    return set(rows)


def is_saved(db: Session, user_id: uuid.UUID, post_id: uuid.UUID) -> bool:
    return (
        db.query(UserSavedPost)
        .filter(
            UserSavedPost.user_id == user_id,
            UserSavedPost.post_id == post_id,
        )
        .first()
        is not None
    )


def save_post(db: Session, user_id: uuid.UUID, post_id: uuid.UUID) -> bool:
    """Idempotently save a post. Returns ``True`` if newly created."""
    if is_saved(db, user_id, post_id):
        return False
    db.add(UserSavedPost(user_id=user_id, post_id=post_id))
    db.flush()
    return True


def unsave_post(db: Session, user_id: uuid.UUID, post_id: uuid.UUID) -> bool:
    """Idempotently remove a saved post. Returns ``True`` if a row was removed."""
    link = (
        db.query(UserSavedPost)
        .filter(
            UserSavedPost.user_id == user_id,
            UserSavedPost.post_id == post_id,
        )
        .first()
    )
    if link is None:
        return False
    db.delete(link)
    db.flush()
    return True


def list_saved_posts(db: Session, user_id: uuid.UUID) -> list[Post]:
    return (
        db.query(Post)
        .join(UserSavedPost, UserSavedPost.post_id == Post.id)
        .filter(UserSavedPost.user_id == user_id)
        .order_by(UserSavedPost.created_at.desc())
        .all()
    )
