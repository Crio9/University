"""One contract shared by the NVIDIA client and the ingestion pipeline."""

from datetime import datetime, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

AudienceName = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=255),
]
Course = Annotated[int, Field(strict=True, ge=1, le=6)]


class TargetAudience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    faculty: list[AudienceName]
    program: list[AudienceName]
    course: list[Course]
    group: list[AudienceName]

    @field_validator("faculty", "program", "course", "group")
    @classmethod
    def deduplicate(cls, values):
        return list(dict.fromkeys(values))


class AIClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal[
        "ACADEMIC",
        "ADMINISTRATIVE",
        "OPPORTUNITY",
        "EVENT",
        "NEWS",
    ]

    tags: list[
        Annotated[
            str,
            StringConstraints(
                strict=True, strip_whitespace=True, min_length=1, max_length=100
            ),
        ]
    ]

    importance: Literal[
        "LOW",
        "NORMAL",
        "HIGH",
        "CRITICAL",
    ]

    deadline: datetime | None = None

    target_audience: TargetAudience

    summary: Annotated[
        str,
        StringConstraints(
            strict=True, strip_whitespace=True, min_length=1, max_length=1000
        ),
    ]

    confidence: float = Field(strict=True, ge=0.0, le=1.0)

    @field_validator("deadline", mode="before")
    @classmethod
    def require_date_or_datetime(cls, value):
        if value is not None and not isinstance(value, (str, datetime)):
            raise ValueError("deadline must be an ISO date/datetime or null")
        if isinstance(value, str) and len(value) == 10:
            return datetime.fromisoformat(value).replace(hour=23, minute=59, second=59)
        return value

    @field_validator("deadline")
    @classmethod
    def normalize_deadline(cls, value):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo("Europe/Moscow"))
        return value.astimezone(timezone.utc)
