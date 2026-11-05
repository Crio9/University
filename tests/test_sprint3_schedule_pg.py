"""PostgreSQL schema-scoped API test. Set TEST_DATABASE_URL to enable it."""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.db.base import Base
from app.db.database import get_db
from app.main import app
from app.models import User, StudentProfile, University, Faculty, StudyProgram, StudyGroup
from app.models.schedule import ScheduleEntry


@pytest.mark.asyncio
async def test_schedule_pg_full_flow():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL=postgresql+asyncpg://... to run integration tests")
    schema = "schedule_test_" + uuid.uuid4().hex
    admin = create_async_engine(url)
    async with admin.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        # Создаём все таблицы в изолированной тестовой схеме
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Создаём пользователей
        async with Session() as db:
            db.add_all([
                User(
                    id=1,
                    email="schedule-student@example.test",
                    password_hash="unused",
                    full_name="Student",
                    role="student",
                ),
                User(
                    id=2,
                    email="schedule-staff@example.test",
                    password_hash="unused",
                    full_name="Staff",
                    role="staff",
                ),
                User(
                    id=3,
                    email="schedule-admin@example.test",
                    password_hash="unused",
                    full_name="Admin",
                    role="admin",
                ),
            ])

            await db.flush()

            # A canonical StudyGroup is the source of identity for Schedule.
            university = University(code="DSTU", name="Донской государственный технический университет")
            faculty = Faculty(code="FIST", name="ФИТ", university=university)
            program = StudyProgram(code="PMI", name="ПМИ", faculty=faculty)
            study_group = StudyGroup(code="IVT-31", name="ИВТ-31", program=program)
            db.add(study_group)
            await db.flush()
            group_id = study_group.id
            db.add(StudentProfile(
                user_id=1,
                study_group_id=group_id,
                university="ДГТУ",
                faculty="ФИСТ",
                study_program="ПМИ",
                study_group="ИВТ-31",
                course=3,
            ))

            await db.commit()

        async def override_db():
            async with Session() as session:
                yield session
        app.dependency_overrides[get_db] = override_db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {role: {"Authorization": "Bearer " + create_access_token(str(i))} for role, i in [("student", 1), ("staff", 2), ("admin", 3)]}
            group = dict(study_group_id=group_id)
            lesson = dict(**group, subject="Backend", starts_at="2026-11-04T10:00:00+03:00", ends_at="2026-11-04T11:30:00+03:00")
            assert (await client.post("/api/v1/schedule", json=lesson, headers=headers["student"])).status_code == 403
            assert (await client.post("/api/v1/schedule", json=lesson, headers=headers["staff"])).status_code == 403
            unknown = await client.post("/api/v1/schedule", json={**lesson, "study_group_id": 999999}, headers=headers["admin"])
            assert unknown.status_code == 404, unknown.text
            created = await client.post("/api/v1/schedule", json=lesson, headers=headers["admin"])
            assert created.status_code == 201, created.text
            entry = created.json()["id"]
            assert created.json()["study_group_id"] == group_id
            group_view = await client.get(f"/api/v1/schedule/group?study_group_id={group_id}&date=2026-11-04", headers=headers["admin"])
            assert group_view.status_code == 200 and len(group_view.json()) == 1, group_view.text
            assert len((await client.get("/api/v1/schedule/me?date=2026-11-04", headers=headers["student"])).json()) == 1
            assert (await client.get("/api/v1/schedule/me?date=2026-11-05", headers=headers["student"])).json() == []
            allowed = await client.post("/api/v1/schedule/access/grant", headers=headers["admin"], json={**group, "staff_id": 2})
            assert allowed.status_code == 204
            permitted_view = await client.get(f"/api/v1/schedule/group?study_group_id={group_id}&date=2026-11-04", headers=headers["staff"])
            assert permitted_view.status_code == 200 and len(permitted_view.json()) == 1, permitted_view.text
            moved = await client.patch(f"/api/v1/schedule/{entry}", headers=headers["staff"], json={"status": "MOVED", "starts_at": "2026-11-05T10:00:00+03:00", "ends_at": "2026-11-05T11:30:00+03:00"})
            assert moved.status_code == 200, moved.text
            for day in ("2026-11-04", "2026-11-05"):
                response = await client.get(f"/api/v1/schedule/me?date={day}", headers=headers["student"])
                assert response.status_code == 200, response.text
                assert [x["id"] for x in response.json()] == [entry]
            cancelled = await client.patch(f"/api/v1/schedule/{entry}", headers=headers["staff"], json={"status":"CANCELLED"})
            assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
            assert (await client.patch(f"/api/v1/schedule/{entry}", headers=headers["staff"], json={"status":"NORMAL"})).status_code == 409
            async with Session() as db:
                assert (await db.scalar(select(ScheduleEntry).where(ScheduleEntry.id == entry))).status == "CANCELLED"
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()
