from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TargetAudience(BaseModel):
    faculty: list[str] = Field(default_factory=list)
    program: list[str] = Field(default_factory=list)
    course: list[int] = Field(default_factory=list)
    group: list[str] = Field(default_factory=list)


class AIClassificationResult(BaseModel):
    category: Literal[
        "ACADEMIC",
        "ADMINISTRATIVE",
        "OPPORTUNITY",
        "EVENT",
        "NEWS",
    ]

    tags: list[str] = Field(default_factory=list)

    importance: Literal[
        "LOW",
        "NORMAL",
        "HIGH",
        "CRITICAL",
    ]

    deadline: datetime | None = None

    target_audience: TargetAudience = Field(
        default_factory=TargetAudience
    )

    summary: str

    confidence: float = Field(ge=0.0, le=1.0)
