from datetime import datetime, time
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl

OpportunityType = Literal["internship", "junior_job", "hackathon", "grant", "event", "learning"]
PublicationState = Literal["draft", "published", "rejected", "archived"]


class OpportunityFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    type: OpportunityType | None = None
    title: str = Field(default="", max_length=255)
    summary: str = Field(default="", max_length=2000)
    format: Literal["online", "onsite", "hybrid", "unknown"] = "unknown"
    city: str | None = None
    kind: Literal["open_call", "announcement", "report", "cancelled", "unknown"] = "unknown"
    topics: list[Literal["BACKEND", "FRONTEND", "AI_DATA", "SECURITY", "RESEARCH"]] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    deadline: AwareDatetime | None = None
    event_start: AwareDatetime | None = None
    event_end: AwareDatetime | None = None
    courses: list[int] = Field(default_factory=list)
    faculties: list[str] = Field(default_factory=list)
    programs: list[str] = Field(default_factory=list)
    conditions: str = ""

    def event_cutoff(self):
        if self.event_end or not self.event_start:
            return self.event_end
        zone = ZoneInfo("Europe/Moscow")
        return datetime.combine(self.event_start.astimezone(zone).date(), time.max, zone)


class ReviewedOpportunity(OpportunityFields):
    status: PublicationState = "draft"
    action_url: HttpUrl | None = None
    contact: str | None = None
    instructions_in_source: bool = False
    review_by: AwareDatetime | None = None
