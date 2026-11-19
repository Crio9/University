from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.schemas.opportunity import OpportunityFields
from app.services.publication import classify_publication


@pytest.mark.parametrize("text,fmt,city,days,expected", [
    ("Онлайн-хакатон, регистрация открыта", "online", None, 3, "published"),
    ("В Ростове-на-Дону открыт набор на стажировку", "onsite", "Ростов-на-Дону", 4, "published"),
    ("Открыт набор, регистрация онлайн", "online", None, 3, "draft"),
    ("Онлайн-хакатон, регистрация закрыта", "online", None, 3, "draft"),
    ("Онлайн-хакатон, регистрация открыта", "online", None, -3, "draft"),
    ("Приём заявок на грант", "onsite", None, 3, "draft"),
])
def test_source_evidence(text, fmt, city, days, expected):
    raw = SimpleNamespace(source_url="https://example.org/call", raw_text=text)
    proposal = OpportunityFields(type="hackathon", kind="open_call", title="Тест",
                                 summary=text, city=city, format=fmt,
                                 deadline=datetime.now(timezone.utc) + timedelta(days=days))
    card = classify_publication(raw, proposal)
    assert card.status == expected
    assert card.instructions_in_source == (expected == "published")
