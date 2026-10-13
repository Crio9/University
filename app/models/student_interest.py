
from sqlalchemy import Column, ForeignKey, Table

from app.db.base import Base


student_interests = Table(
    "student_interests",
    Base.metadata,
    Column(
        "student_id",
        ForeignKey("student_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
