
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # Machine code from the approved vocabulary (ACADEMIC, OPPORTUNITY, ...).
    # Nullable so pre-existing rows and manually created content keep working.
    code: Mapped[str | None] = mapped_column(
        String(32), unique=True, nullable=True, index=True
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # Machine code from the approved vocabulary (CAREER, HACKATHON, ...).
    code: Mapped[str | None] = mapped_column(
        String(32), unique=True, nullable=True, index=True
    )
