from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.db.database import get_db
from app.dependencies.auth import get_current_user, require_staff
from app.models.dictionaries import Category, Tag
from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostCreate, PostRead
from app.services.feed import get_personalized_feed
from app.services.saved_posts import (
    list_saved_posts,
    saved_post_ids,
    save_post,
    unsave_post,
)

router = APIRouter(prefix="/posts", tags=["posts"])


def _to_read(post: Post, *, is_saved: bool = False) -> PostRead:
    data = PostRead.model_validate(post)
    data.is_saved = is_saved
    return data


@router.post("", response_model=PostRead, status_code=201)
def create_post(
    data: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
) -> PostRead:
    category = db.query(Category).filter(Category.id == data.category_id).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown category")

    tags: list[Tag] = []
    if data.tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(data.tag_ids)).all()
        if len(tags) != len(set(data.tag_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown tag id")

    post = Post(
        title=data.title,
        body=data.body,
        category_id=data.category_id,
        author_id=current_user.id,
        target_roles=data.target_roles,
        target_faculties=data.target_faculties,
        target_courses=data.target_courses,
        deadline=data.deadline,
        is_published=data.is_published,
        tags=tags,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    post = (
        db.query(Post)
        .options(joinedload(Post.category), joinedload(Post.tags))
        .filter(Post.id == post.id)
        .one()
    )
    return _to_read(post, is_saved=False)


@router.get("/saved", response_model=list[PostRead])
def saved_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PostRead]:
    posts = list_saved_posts(db, current_user.id)
    return [_to_read(post, is_saved=True) for post in posts]


@router.get("/feed", response_model=list[PostRead])
def posts_feed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PostRead]:
    posts = get_personalized_feed(db, current_user)
    saved = saved_post_ids(db, current_user.id)
    return [_to_read(post, is_saved=post.id in saved) for post in posts]


@router.post("/{post_id}/save", response_model=PostRead)
def save_post_endpoint(
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostRead:
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    save_post(db, current_user.id, post_id)
    db.commit()
    db.refresh(post)
    return _to_read(post, is_saved=True)


@router.delete("/{post_id}/save", response_model=PostRead)
def unsave_post_endpoint(
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostRead:
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    unsave_post(db, current_user.id, post_id)
    db.commit()
    db.refresh(post)
    return _to_read(post, is_saved=False)
