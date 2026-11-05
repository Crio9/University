"""Sprint 3 cross-module API regression tests.

Runs against an isolated in-memory SQLite DB; no deployed database is touched.
It verifies that Profile, Feed and Schedule refer to the same canonical group,
including a different university with an identically named group.
"""
from __future__ import annotations

from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models  # noqa: F401 - ensure all tables are registered
from app.core.security import create_access_token
from app.db.base import Base
from app.db.database import get_db
from app.main import app
from app.models.dictionaries import Category
from app.models.user import User
from app.models.university import Faculty, StudyGroup, StudyProgram, University


@pytest.mark.asyncio
async def test_canonical_profile_feed_schedule_permissions_and_moves():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        async with Session() as db:
            student_a = User(email="s3-student-a@example.test", password_hash="unused",
                             full_name="Student A", role="student")
            student_b = User(email="s3-student-b@example.test", password_hash="unused",
                             full_name="Student B", role="student")
            staff = User(email="s3-staff@example.test", password_hash="unused",
                         full_name="Staff", role="staff")
            admin = User(email="s3-admin@example.test", password_hash="unused",
                         full_name="Admin", role="admin")

            # Names overlap intentionally: ID, not a group-name string, must
            # distinguish the universities and their Schedule permissions.
            dstu = University(code="DSTU", name="Донской государственный технический университет")
            faculty_a = Faculty(code="FIST", name="ФИСТ", university=dstu)
            program_a = StudyProgram(code="PMI", name="ПМИ", faculty=faculty_a)
            group_a = StudyGroup(code="IVT-31", name="ИВТ-31", program=program_a)

            sfedu = University(code="SFEDU", name="Южный федеральный университет")
            faculty_b = Faculty(code="SFEDU-IOT", name="ИОТ", university=sfedu)
            program_b = StudyProgram(code="SFEDU-IOT-PMI", name="ПМИ", faculty=faculty_b)
            group_b = StudyGroup(code="S3-DUP-31", name="ИВТ-31", program=program_b)
            news = Category(name="Новости", code="NEWS")
            db.add_all([student_a, student_b, staff, admin, group_a, group_b, news])
            await db.flush()
            ids = {
                "student_a": student_a.id,
                "student_b": student_b.id,
                "staff": staff.id,
                "admin": admin.id,
                "group_a": group_a.id,
                "group_b": group_b.id,
                "news": news.id,
            }
            await db.commit()

        async def override_db():
            async with Session() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        headers = {
            name: {"Authorization": f"Bearer {create_access_token(str(ids[name]))}"}
            for name in ("student_a", "student_b", "staff", "admin")
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Profile derives its university/faculty/program from group ID.
            for username, group_name in (("student_a", "group_a"), ("student_b", "group_b")):
                response = await client.put(
                    "/api/v1/profile/student", headers=headers[username],
                    json={"study_group_id": ids[group_name], "course": 2, "interest_ids": []},
                )
                assert response.status_code == 200, response.text
                assert response.json()["profile"]["study_group_id"] == ids[group_name]

            profile = await client.get("/api/v1/profile/me", headers=headers["student_a"])
            assert profile.status_code == 200, profile.text
            assert profile.json()["profile"]["faculty"] == "ФИТ"  # code FIST's canonical label
            assert profile.json()["profile"]["study_group"] == "ИВТ-31"

            # Feed must use the same canonical profile context, not stale strings.
            post = await client.post(
                "/api/v1/posts", headers=headers["admin"],
                json={
                    "title": "Объявление для ФИТ", "content": "Новый материал для группы",
                    "category_id": ids["news"], "importance": "standard", "tag_ids": [],
                    "target_audience": {
                        "faculty": ["ФИТ"], "program": ["ПМИ"],
                        "course": [2], "group": ["ИВТ-31"],
                    },
                },
            )
            assert post.status_code == 201, post.text
            feed_a = await client.get("/api/v1/posts/feed", headers=headers["student_a"])
            feed_b = await client.get("/api/v1/posts/feed", headers=headers["student_b"])
            assert feed_a.status_code == feed_b.status_code == 200
            assert post.json()["id"] in {item["id"] for item in feed_a.json()}
            assert post.json()["id"] not in {item["id"] for item in feed_b.json()}

            lesson = {
                "study_group_id": ids["group_a"], "subject": "Backend",
                "starts_at": "2026-11-09T10:00:00+03:00",
                "ends_at": "2026-11-09T11:30:00+03:00",
            }
            bad = await client.post("/api/v1/schedule", json={**lesson, "study_group_id": 999999},
                                    headers=headers["admin"])
            assert bad.status_code == 404, bad.text
            denied = await client.post("/api/v1/schedule", json=lesson,
                                       headers=headers["staff"])
            assert denied.status_code == 403, denied.text

            created = await client.post("/api/v1/schedule", json=lesson, headers=headers["admin"])
            assert created.status_code == 201, created.text
            lesson_id = created.json()["id"]
            assert created.json()["study_group_id"] == ids["group_a"]
            assert created.json()["faculty"] == "ФИТ"

            for username, should_see in (("student_a", True), ("student_b", False)):
                response = await client.get("/api/v1/schedule/me?date=2026-11-09",
                                            headers=headers[username])
                assert response.status_code == 200, response.text
                assert [item["id"] for item in response.json()] == ([lesson_id] if should_see else [])

            # One staff grant must not authorize the identically named group at SFEDU.
            grant = await client.post(
                "/api/v1/schedule/access/grant", headers=headers["admin"],
                json={"staff_id": ids["staff"], "study_group_id": ids["group_a"]},
            )
            assert grant.status_code == 204, grant.text
            allowed = await client.get(
                f"/api/v1/schedule/group?study_group_id={ids['group_a']}&date=2026-11-09",
                headers=headers["staff"],
            )
            forbidden = await client.get(
                f"/api/v1/schedule/group?study_group_id={ids['group_b']}&date=2026-11-09",
                headers=headers["staff"],
            )
            assert allowed.status_code == 200 and len(allowed.json()) == 1, allowed.text
            assert forbidden.status_code == 403, forbidden.text

            moved = await client.patch(
                f"/api/v1/schedule/{lesson_id}", headers=headers["staff"],
                json={
                    "status": "MOVED", "starts_at": "2026-11-10T10:00:00+03:00",
                    "ends_at": "2026-11-10T11:30:00+03:00",
                },
            )
            assert moved.status_code == 200, moved.text
            for day in (date(2026, 11, 9), date(2026, 11, 10)):
                view = await client.get(f"/api/v1/schedule/me?date={day.isoformat()}",
                                        headers=headers["student_a"])
                assert view.status_code == 200, view.text
                assert [item["id"] for item in view.json()] == [lesson_id]

            cancelled = await client.patch(
                f"/api/v1/schedule/{lesson_id}", headers=headers["staff"],
                json={"status": "CANCELLED"},
            )
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["status"] == "CANCELLED"
            immutable = await client.patch(
                f"/api/v1/schedule/{lesson_id}", headers=headers["staff"],
                json={"status": "NORMAL"},
            )
            assert immutable.status_code == 409, immutable.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()
