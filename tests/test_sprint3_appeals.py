"""FR-4/5 regressions: recipient scope, student ownership and status lifecycle."""
import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.user import User
from tests.test_ingest import env  # noqa: F401 -- same isolated SQLite fixture


def auth(user_id):
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


@pytest.mark.asyncio
async def test_appeal_lifecycle_and_idor_protection(env):
    async with env["Session"]() as db:
        student = await db.scalar(select(User).where(User.email == "student@uni.test"))
        staff = await db.scalar(select(User).where(User.email == "staff@uni.test"))
        assert student and staff
        other_student = User(email="other-appeals-student@example.test", password_hash="unused", full_name="Other Student", role="student")
        other_staff = User(email="other-appeals-staff@example.test", password_hash="unused", full_name="Other Staff", role="staff")
        admin = User(email="appeals-admin@example.test", password_hash="unused", full_name="Admin", role="admin")
        db.add_all([other_student, other_staff, admin])
        await db.flush()
        ids = {"student": student.id, "staff": staff.id, "other_student": other_student.id,
               "other_staff": other_staff.id, "admin": admin.id}
        await db.commit()
    client = env["client"]
    data = {"category": "ACADEMIC", "subject": "Проблема с зачётом",
            "message": "Прошу уточнить результаты зачёта по предмету", "recipient_id": ids["staff"]}
    assert (await client.post("/api/v1/appeals", json=data)).status_code == 401
    assert (await client.post("/api/v1/appeals", headers=auth(ids["staff"]), json=data)).status_code == 403
    assert (await client.post("/api/v1/appeals", headers=auth(ids["student"]), json={k: v for k,v in data.items() if k != "recipient_id"})).status_code == 422
    assert (await client.post("/api/v1/appeals", headers=auth(ids["student"]), json={**data, "recipient_id": 999999})).status_code == 404
    assert (await client.post("/api/v1/appeals", headers=auth(ids["student"]), json={**data, "recipient_id": ids["other_student"]})).status_code == 422

    created = await client.post("/api/v1/appeals", headers=auth(ids["student"]), json=data)
    assert created.status_code == 201, created.text
    item = created.json()
    appeal_id = item["id"]
    assert item["student_id"] == ids["student"]
    assert item["staff_id"] == ids["staff"]
    assert item["status"] == "CREATED"

    mine = await client.get("/api/v1/appeals/me", headers=auth(ids["student"]))
    assert mine.status_code == 200 and [x["id"] for x in mine.json()] == [appeal_id]
    legacy_mine = await client.get("/api/v1/appeals/my", headers=auth(ids["student"]))
    assert legacy_mine.status_code == 200
    assert (await client.get(f"/api/v1/appeals/{appeal_id}", headers=auth(ids["student"]))).status_code == 200
    assert (await client.get(f"/api/v1/appeals/{appeal_id}", headers=auth(ids["other_student"]))).status_code == 404
    assert (await client.get("/api/v1/appeals", headers=auth(ids["student"]))).status_code == 403
    assert (await client.get("/api/v1/appeals", headers=auth(ids["other_staff"]))).json() == []
    assert [x["id"] for x in (await client.get("/api/v1/appeals", headers=auth(ids["staff"]))).json()] == [appeal_id]
    assert (await client.get(f"/api/v1/appeals/{appeal_id}", headers=auth(ids["other_staff"]))).status_code == 404
    assert (await client.patch(f"/api/v1/appeals/{appeal_id}/status", headers=auth(ids["other_staff"]), json={"status": "IN_REVIEW"})).status_code == 404
    assert (await client.patch(f"/api/v1/appeals/{appeal_id}/status", headers=auth(ids["student"]), json={"status": "IN_REVIEW"})).status_code == 403
    assert (await client.patch(f"/api/v1/appeals/{appeal_id}/status", headers=auth(ids["staff"]), json={"status": "CLOSED"})).status_code == 409
    assert (await client.patch(f"/api/v1/appeals/{appeal_id}/status", headers=auth(ids["staff"]), json={"status": "UNKNOWN"})).status_code == 422

    reviewing = await client.patch(f"/api/v1/appeals/{appeal_id}/status", headers=auth(ids["staff"]), json={"status": "IN_REVIEW"})
    assert reviewing.status_code == 200 and reviewing.json()["status"] == "IN_REVIEW", reviewing.text
    assert (await client.get(f"/api/v1/appeals/{appeal_id}", headers=auth(ids["student"]))).json()["status"] == "IN_REVIEW"
    closed = await client.patch(f"/api/v1/appeals/{appeal_id}/status", headers=auth(ids["staff"]), json={"status": "CLOSED"})
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED"
    assert (await client.patch(f"/api/v1/appeals/{appeal_id}/status", headers=auth(ids["staff"]), json={"status": "IN_REVIEW"})).status_code == 409
    assert (await client.get(f"/api/v1/appeals/{appeal_id}", headers=auth(ids["student"]))).json()["status"] == "CLOSED"
    assert [x["id"] for x in (await client.get("/api/v1/appeals", headers=auth(ids["admin"]))).json()] == [appeal_id]
