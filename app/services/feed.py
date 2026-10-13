from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.post import Post
from app.models.user import User, UserRole


def get_personalized_feed(db: Session, user: User) -> list[Post]:
    query = (
        db.query(Post)
        .options(joinedload(Post.category), joinedload(Post.tags))
        .filter(Post.is_published.is_(True))
    )

    role_value = user.role.value
    query = query.filter(
        or_(
            func.cardinality(Post.target_roles) == 0,
            Post.target_roles.contains([role_value]),
        )
    )

    if user.role == UserRole.STUDENT and user.student_profile is not None:
        profile = user.student_profile
        query = query.filter(
            or_(
                func.cardinality(Post.target_faculties) == 0,
                Post.target_faculties.contains([profile.faculty]),
            )
        )
        query = query.filter(
            or_(
                func.cardinality(Post.target_courses) == 0,
                Post.target_courses.contains([profile.course]),
            )
        )

    return query.order_by(Post.published_at.desc()).all()
