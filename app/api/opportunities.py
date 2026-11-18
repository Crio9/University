"""Reviewed opportunities use the source ID as their stable public ID."""
from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import HttpUrl, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.auth import require_roles
from app.models import RawContent, StudentProfile, Tag
from app.models.student_interest import student_interests
from app.schemas.opportunity import ReviewedOpportunity, OpportunityType
from app.services.university import audience_key

router = APIRouter(tags=["opportunities"])
staff = Depends(require_roles("staff", "admin"))
student = Depends(require_roles("student"))


def draft(raw):
    data = raw.opportunity_review
    if data is None:
        # Invalid provider payloads remain inspectable and editable by staff.
        proposal = (raw.ai_result or {}).get("opportunity")
        try:
            return ReviewedOpportunity.model_validate(proposal or {})
        except ValidationError:
            return ReviewedOpportunity()
    return ReviewedOpportunity.model_validate(data)


def active(card, now):
    cutoffs = [v for v in (card.deadline, card.event_cutoff(), card.review_by) if v]
    return card.status == "published" and bool(cutoffs) and min(cutoffs) >= now


def serialize(raw, card, reasons):
    return dict(card.model_dump(mode="json"), id=raw.id, source_url=raw.source_url,
                source_published_at=raw.source_published_at, match_reasons=reasons)


@router.get("/staff/opportunities")
async def review_queue(_=staff, db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(RawContent).order_by(RawContent.id.desc()))
    return [dict(serialize(raw, draft(raw), []), original=raw.raw_text,
                 metadata=raw.ingest_metadata, processing_status=raw.status) for raw in rows]


@router.patch("/staff/opportunities/{raw_id}")
async def review(raw_id: int, changes: dict, _=staff, db: AsyncSession = Depends(get_db)):
    raw = await db.scalar(select(RawContent).where(RawContent.id == raw_id).with_for_update())
    if raw is None:
        raise HTTPException(404, "Source not found")
    try:
        card = ReviewedOpportunity.model_validate(draft(raw).model_dump() | changes)
        if card.status == "published":
            TypeAdapter(HttpUrl).validate_python(raw.source_url)
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    if card.status == "published":
        local = audience_key(card.city or "") == "ростов-на-дону"
        if not (card.format == "online" or local and card.format in ("onsite", "hybrid")):
            raise HTTPException(422, "Confirm online participation or Rostov venue")
        if not (card.type and card.title and card.summary and card.kind in ("open_call", "announcement")
                and (card.contact or card.action_url or card.instructions_in_source)
                and active(card, datetime.now(timezone.utc))):
            raise HTTPException(422, "Confirm content, next action and validity dates")
    raw.opportunity_review = card.model_dump(mode="json")
    await db.commit()
    return serialize(raw, card, [])


def match(card, profile, topics):
    unknown = False
    for allowed, selected in [(card.faculties, profile.faculty), (card.programs, profile.study_program),
                              (card.courses, profile.course)]:
        if allowed and selected is None:
            unknown = True
        elif allowed and audience_key(str(selected)) not in {audience_key(str(v)) for v in allowed}:
            return None
    overlap = sorted(set(card.topics) & topics)
    preferred = card.type in (profile.preferred_types or [])
    reasons = [f"По интересу {topic}" for topic in overlap]
    if preferred:
        reasons.append("Вы выбрали этот тип возможности")
    if unknown:
        reasons.append("Уточните условия участия")
    return unknown, 2 * len(overlap) + int(preferred), reasons


@router.get("/opportunities")
async def catalog(view: Literal["personalized", "all"] = "personalized", type: OpportunityType | None = None,
                  limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                  user=student, db: AsyncSession = Depends(get_db)):
    profile = await db.get(StudentProfile, user.id)
    topics = set(await db.scalars(select(Tag.code).join(student_interests, student_interests.c.tag_id == Tag.id)
                                  .where(student_interests.c.student_id == user.id)))
    complete = bool(profile and (profile.catalog_program_id or profile.study_group_id) and topics)
    now = datetime.now(timezone.utc)
    ranked = []
    if view == "all" or complete:
        for raw in await db.scalars(select(RawContent).where(RawContent.opportunity_review.is_not(None))):
            card = draft(raw)
            if not active(card, now) or type and type != card.type:
                continue
            matched = match(card, profile, topics) if view == "personalized" else (False, 0, [])
            if matched is None:
                continue
            unknown, score, reasons = matched
            urgent = card.deadline and card.deadline <= now + timedelta(days=7)
            stamp = raw.source_published_at or raw.created_at
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            key = (unknown, -score, card.deadline.timestamp() if urgent else float("inf"), -stamp.timestamp(), raw.id)
            ranked.append((key, serialize(raw, card, reasons)))
    ranked.sort(key=lambda pair: pair[0])
    return {"profile_complete": complete, "items": [item for _, item in ranked[offset:offset + limit]]}


@router.get("/opportunities/{raw_id}")
async def detail(raw_id: int, _=student, db: AsyncSession = Depends(get_db)):
    raw = await db.get(RawContent, raw_id)
    if raw is None or not active(draft(raw), datetime.now(timezone.utc)):
        raise HTTPException(404, "Opportunity unavailable")
    return serialize(raw, draft(raw), [])
