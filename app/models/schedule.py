"""Schedule ORM. Canonical group FK plus temporary legacy key/snapshot.

The group ID is nullable until the next migration backfills existing rows.
Legacy columns remain NOT NULL to be compatible with 0004_schedule.
"""
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Table,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


staff_schedule_groups = Table(
    "staff_schedule_groups",
    Base.metadata,
    Column("staff_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_key", String(64), primary_key=True),
    Column("study_group_id", ForeignKey("study_groups.id", ondelete="RESTRICT"), nullable=True),
    UniqueConstraint("staff_id", "study_group_id", name="uq_staff_schedule_groups_staff_group_id"),
)


class ScheduleEntry(Base):
    __tablename__ = "schedule_entries"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_schedule_ends_after_start"),
        CheckConstraint("status IN ('NORMAL', 'MOVED', 'CANCELLED')", name="ck_schedule_status"),
        Index("ix_schedule_group_start", "group_key", "starts_at"),
        Index("ix_schedule_group_original", "group_key", "original_starts_at"),
        Index("ix_schedule_group_id_start", "study_group_id", "starts_at"),
        Index("ix_schedule_group_id_original", "study_group_id", "original_starts_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # NULL is temporary, until existing Schedule rows have been backfilled.
    study_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_groups.id", ondelete="RESTRICT"), nullable=True
    )
    group_entity = relationship("StudyGroup", foreign_keys=[study_group_id], lazy="selectin")
    group_key: Mapped[str] = mapped_column(String(64), nullable=False)
    university: Mapped[str] = mapped_column(String(255), nullable=False)
    faculty: Mapped[str] = mapped_column(String(255), nullable=False)
    study_program: Mapped[str] = mapped_column(String(255), nullable=False)
    study_group: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    room: Mapped[str | None] = mapped_column(String(100), nullable=True)
    teacher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="NORMAL", server_default="NORMAL")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
