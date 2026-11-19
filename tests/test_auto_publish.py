from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from tests.test_sprint2_flow import flow_env
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


@pytest.mark.asyncio
async def test_import_appears_without_staff_patch_and_respects_archive(flow_env):
    from tests.test_ai_classification import valid_result

    client = flow_env["client"]
    staff = flow_env["staff"]
    student = flow_env["users"]["iot3"]
    proposal = dict(type="hackathon", format="online", title="Хакатон",
                    summary="Онлайн-хакатон", kind="open_call", topics=["AI_DATA"],
                    deadline=(datetime.now(timezone.utc) + timedelta(days=3)).isoformat())
    flow_env["provider"].result = valid_result(opportunity=proposal)
    raw = dict(source_type="website", source_url="https://example.org/registration",
               raw_text="Онлайн-хакатон. Регистрация открыта.")
    response = await client.post("/api/v1/ingest/raw", json=raw, headers=staff)
    assert response.status_code == 201
    key = response.json()["id"]
    feed = await client.get("/api/v1/opportunities?view=all", headers=student)
    assert [item["id"] for item in feed.json()["items"]] == [key]
    detail = f"/api/v1/opportunities/{key}"
    assert (await client.get(detail, headers=student)).json()["source_url"] == raw["source_url"]
    archive = await client.patch(f"/api/v1/staff/opportunities/{key}", headers=staff, json={"status": "archived"})
    assert archive.is_success
    assert (await client.post("/api/v1/ingest/raw", json=raw, headers=staff)).json()["id"] == key
    assert (await client.get(detail, headers=student)).status_code == 404
