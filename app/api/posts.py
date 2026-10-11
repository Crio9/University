
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.dictionaries import Category, Tag
from app.models.post import Post, post_tags
from app.models.profile import StudentProfile
from app.models.student_interest import student_interests
from app.models.user import User
from app.schemas.post import PostCreate, PostRead, PostUpdate


router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("/feed", response_model=list[PostRead])
async def get_smart_feed(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access the smart feed",
        )

    profile = await db.get(StudentProfile, current_user.id)

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found",
        )

   

    now = datetime.now(timezone.utc)
    deadline_limit = now + timedelta(days=7)

    query = select(Post).where(
        (Post.target_faculty.is_(None))
        | (Post.target_faculty == profile.faculty),
        (Post.target_course.is_(None))
        | (Post.target_course == profile.course),
        (Post.target_program.is_(None))
        | (Post.target_program == profile.study_program),
    ).order_by(
        case(
            (
                (Post.deadline >= now)
                & (Post.deadline <= deadline_limit),
                0,
            ),
            else_=1,
        ),
        case(
            (Post.importance == "critical", 0),
            else_=1,
        ),
        Post.created_at.desc(),
    )


    result = await db.execute(query)
    posts = result.scalars().all()

    interest_query = (
        select(Tag.id)
        .join(
            student_interests,
            student_interests.c.tag_id == Tag.id,
        )
        .where(student_interests.c.student_id == current_user.id)
    )
    interest_result = await db.execute(interest_query)
    interest_tag_ids = set(interest_result.scalars().all())

   
   
    matching_post_ids = set()

    if interest_tag_ids:
        post_tag_query = select(post_tags.c.post_id).where(
            post_tags.c.tag_id.in_(interest_tag_ids)
        )
        post_tag_result = await db.execute(post_tag_query)
        matching_post_ids = set(post_tag_result.scalars().all())

    category_query = select(Category.id, Category.name)
    category_result = await db.execute(category_query)
    category_names = {
        category_id: name.lower()
        for category_id, name in category_result.all()
    }

    filtered_posts = []

    for post in posts:
        category_name = category_names.get(post.category_id, "")
        is_important = post.importance == "critical"

        is_news_or_admin = (
            "news" in category_name
            or "admin" in category_name
            or "новост" in category_name
            or "админ" in category_name
        )

        is_opportunity = (
            "opportunit" in category_name
            or "возможност" in category_name
        )


        has_matching_interest = post.id in matching_post_ids

        if (
            is_important
            or is_news_or_admin
            or not is_opportunity
            or has_matching_interest
        ):
            filtered_posts.append(post)

    return filtered_posts




@router.get("", response_model=list[PostRead])
async def list_posts(
    current_user: User = Depends(require_roles("staff", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post).order_by(Post.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "",
    response_model=PostRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_post(
    post_data: PostCreate,
    current_user: User = Depends(require_roles("staff", "admin")),
    db: AsyncSession = Depends(get_db),
):
    post = Post(
        **post_data.model_dump(),
        author_id=current_user.id,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    return post


@router.get("/{post_id}", response_model=PostRead)
async def get_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post).where(Post.id == post_id)
    )
    post = result.scalar_one_or_none()

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    return post


@router.put("/{post_id}", response_model=PostRead)
async def update_post(
    post_id: int,
    post_data: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post).where(Post.id == post_id)
    )
    post = result.scalar_one_or_none()

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    if post.author_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot edit this post",
        )

    updates = post_data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(post, field, value)

    await db.commit()
    await db.refresh(post)

    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post).where(Post.id == post_id)
    )
    post = result.scalar_one_or_none()

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    if post.author_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete this post",
        )

    await db.delete(post)
    await db.commit()
