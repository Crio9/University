from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.db.database import get_db
from app.dependencies.auth import get_current_user, require_staff
from app.models.dictionaries import Category, Tag
from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostCreate, PostRead
from app.services.feed import get_personalized_feed

router = APIRouter(prefix="/posts", tags=["posts"])


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
    return PostRead.model_validate(post)


@router.get("/feed", response_model=list[PostRead])
def posts_feed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PostRead]:
    posts = get_personalized_feed(db, current_user)
    return [PostRead.model_validate(post) for post in posts]
