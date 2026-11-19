"""Shared eligibility checks for staff review and automatic publication."""
import re
from datetime import datetime, timezone

from pydantic import HttpUrl, TypeAdapter, ValidationError

from app.schemas.opportunity import ReviewedOpportunity
from app.services.university import audience_key


def active(card, now):
    cutoffs = [value for value in (card.deadline, card.event_cutoff(), card.review_by) if value]
    return card.status == "published" and bool(cutoffs) and min(cutoffs) >= now


def publication_error(card, source_url):
    try:
        TypeAdapter(HttpUrl).validate_python(source_url)
    except ValidationError:
        return "Provide a valid source URL"
    local = audience_key(card.city or "") == "ростов-на-дону"
    if not (card.format == "online" or local and card.format in ("onsite", "hybrid")):
        return "Confirm online participation or Rostov venue"
    if not (card.type and card.title and card.summary and card.kind in ("open_call", "announcement")
            and (card.contact or card.action_url or card.instructions_in_source)
            and active(card, datetime.now(timezone.utc))):
        return "Confirm content, next action and validity dates"
    return None


def classify_publication(raw, proposal):
    card = ReviewedOpportunity.model_validate(proposal.model_dump())
    text = raw.raw_text.casefold()
    # Do not infer remote participation from online registration alone.
    remote = re.search(r"(?:онлайн[- ](?:хакатон|стажировка|курс|лекция|митап|семинар|формат)|(?:формат|участие|пройд[её]т|работа)\s*[:—–-]?\s*(?:полностью\s+)?(?:онлайн|удал[её]нно)|полностью онлайн)", text)
    local = re.search(r"ростов[ае]?-на-дону", text)
    location_confirmed = remote if card.format == "online" else local
    call = re.search(r"регистраци[яию]|зарегистрир|подать заявку|при[её]м заявок|открыт набор", text)
    closed = re.search(r"(регистрация|набор|при[её]м заявок)\s+(?:уже\s+)?(?:закрыт|заверш)|отмен[её]н|подведены итоги", text)
    if location_confirmed and call and not closed:
        candidate = card.model_copy(update={"status": "published", "instructions_in_source": True})
        if publication_error(candidate, raw.source_url) is None:
            return candidate
    return card
