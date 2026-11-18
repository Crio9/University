from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select

from app.models import Tag
from tests.test_sprint2_flow import flow_env
from tests.test_ai_classification import valid_result


@pytest.mark.asyncio
async def test_three_profiles_and_publication(flow_env):
    env = flow_env
    client, staff = env["client"], env["staff"]
    path = "/api/v1"
    structure = (await client.get(path + "/universities")).json()
    faculty = structure[0]["faculties"][0]
    program = faculty["programs"][0]
    topics = ["BACKEND", "AI_DATA", "RESEARCH"]
    users = [env["users"][key] for key in ("iot3", "fit3", "law3")]
    async with env["Session"]() as db:
        ids = dict((await db.execute(select(Tag.code, Tag.id))).all())
    cards = []
    for i, (topic, token) in enumerate(zip(topics, users)):
        profile = {"faculty_id": faculty["id"], "study_program_id": program["id"],
                   "interest_ids": [ids[topic]], "course": 3}
        assert (await client.put(path + "/profile/student", headers=token, json=profile)).status_code == 200
        proposal = dict(title=topic, summary="Workshop", type="event", topics=[topic],
                        format="online", kind="open_call", deadline=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat())
        env["provider"].result = valid_result(opportunity=proposal)
        body = {"source_type":"web","source_url":f"https://example.org/{i}","raw_text":topic}
        raw = (await client.post(path + "/ingest/raw", headers=staff, json=body)).json()
        key = raw["id"]
        assert raw["status"] == "processed"
        assert (await client.post(path + "/ingest/raw", headers=staff, json=body)).json()["id"] == key
        route = path + f"/staff/opportunities/{key}"
        assert (await client.get(path + f"/opportunities/{key}",headers=token)).status_code == 404
        patch = {"instructions_in_source":True, "status":"published"}
        assert (await client.patch(route, headers=token,json=patch)).status_code == 403
        assert (await client.patch(route, headers=staff,json=patch)).status_code == 200
        cards.append(key)
    for token, key in zip(users, cards):
        result = (await client.get(path + "/opportunities", headers=token)).json()
        assert result["profile_complete"] and result["items"][0]["id"] == key
        assert result["items"][0]["match_reasons"]
    assert len((await client.get(path + "/opportunities?view=all",headers=users[0])).json()["items"]) == 3
    # Changing only interests must reorder the existing material without a model call.
    profile["interest_ids"] = [ids["AI_DATA"]]
    calls = env["provider"].calls
    assert (await client.put(path + "/profile/student", headers=users[0], json=profile)).is_success
    assert (await client.get(path + "/opportunities", headers=users[0])).json()["items"][0]["id"] == cards[1]
    assert calls == env["provider"].calls
    route = path + f"/staff/opportunities/{cards[1]}"
    assert (await client.patch(route, headers=staff, json={"courses": [4]})).is_success
    feed = (await client.get(path + "/opportunities", headers=users[0])).json()["items"]
    assert cards[1] not in {row["id"] for row in feed}
    assert (await client.patch(route, headers=staff, json={"status": "archived"})).is_success
    assert (await client.get(path + f"/opportunities/{cards[1]}", headers=users[0])).status_code == 404
