import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.database import get_db
from app.main import app as fastapi_app
from app.models.dictionaries import Tag
from app.models.profile import StudentProfile
from app.models.user import User


@pytest.mark.asyncio
async def test_profiles_flow():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as session:
            from app.models.university import (
                Faculty,
                StudyGroup,
                StudyProgram,
                University,
            )

            student = User(
                email="student@uni.test",
                password_hash=hash_password("pass123"),
                full_name="Студент Профиль",
                role="student",
            )
            tag = Tag(name="ИТ")
            university = University(code="DSTU", name="ДГТУ")
            faculty = Faculty(university=university, code="FIST", name="ФИТ")
            program = StudyProgram(faculty=faculty, code="PMI", name="ПМИ")
            group = StudyGroup(program=program, code="IVT-21", name="ИВТ-21")
            session.add_all([student, tag, university, faculty, program, group])
            await session.flush()
            group_id = group.id
            session.add(StudentProfile(user_id=student.id))
            await session.commit()
            student_id = student.id
            tag_id = tag.id

        async def override_get_db():
            async with Session() as session:
                yield session

        fastapi_app.dependency_overrides[get_db] = override_get_db
        transport = ASGITransport(app=fastapi_app)

        token = create_access_token(str(student_id))
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            me_resp = await client.get("/api/v1/profile/me", headers=headers)
            assert me_resp.status_code == 200
            assert me_resp.json()["email"] == "student@uni.test"

            update_resp = await client.put(
                "/api/v1/profile/student",
                headers=headers,
                json={
                    "study_group_id": group_id,
                    "course": 2,
                    "interest_ids": [tag_id],
                },
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["profile"]["faculty"] == "ФИТ"
            assert update_resp.json()["profile"]["study_group_id"] == group_id
            assert update_resp.json()["profile"]["interest_ids"] == [tag_id]

            me_after = await client.get("/api/v1/profile/me", headers=headers)
            assert me_after.status_code == 200
            assert me_after.json()["profile"]["course"] == 2
            assert me_after.json()["profile"]["interest_ids"] == [tag_id]

            unknown_group = await client.put(
                "/api/v1/profile/student",
                headers=headers,
                json={"study_group_id": 999999},
            )
            assert unknown_group.status_code == 400

            text_without_group = await client.put(
                "/api/v1/profile/student",
                headers=headers,
                json={"faculty": "ФИТ"},
            )
            assert text_without_group.status_code == 422
    finally:
        fastapi_app.dependency_overrides.clear()
        await engine.dispose()
