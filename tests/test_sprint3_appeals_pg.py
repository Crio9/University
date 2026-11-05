"""PostgreSQL FK and scope integration for appeals (not replaced by SQLite tests)."""
import asyncio
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.engine.url import make_url

from app import models  # noqa: F401
from app.core.security import create_access_token
from app.db.base import Base
from app.db.database import get_db
from app.main import app
from app.models.user import User


@pytest.mark.asyncio
async def test_appeals_pg_enforces_recipient_and_student_ownership():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL must target a separate PostgreSQL test DB")
    parsed = make_url(url)
    if not parsed.drivername.startswith("postgresql") or not any(x in (parsed.database or "").lower() for x in ("test", "ci")):
        pytest.fail("Unsafe TEST_DATABASE_URL: use an isolated PostgreSQL test DB")
    schema = "appeals_test_" + uuid.uuid4().hex
    admin_engine = create_async_engine(url)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            students = [User(email=f"pg-appeals-student-{i}@example.test", password_hash="unused", full_name=f"Student {i}", role="student") for i in range(2)]
            staff = [User(email=f"pg-appeals-staff-{i}@example.test", password_hash="unused", full_name=f"Staff {i}", role="staff") for i in range(2)]
            db.add_all([*students,*staff]); await db.flush()
            ids = [x.id for x in (*students, *staff)]
            await db.commit()
        async def override_db():
            async with Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        hdr = lambda id: {"Authorization": "Bearer " + create_access_token(str(id))}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/appeals", headers=hdr(ids[0]), json={"recipient_id": ids[2], "category": "TECHNICAL", "subject": "Нет доступа", "message": "Не могу войти в университетскую систему"})
            assert response.status_code == 201, response.text
            key = response.json()["id"]
            assert (await client.get(f"/api/v1/appeals/{key}", headers=hdr(ids[1]))).status_code == 404
            assert (await client.get(f"/api/v1/appeals/{key}", headers=hdr(ids[3]))).status_code == 404
            assert (await client.patch(f"/api/v1/appeals/{key}/status", headers=hdr(ids[3]), json={"status":"IN_REVIEW"})).status_code == 404
            # Concurrent Staff requests must not both perform CREATED -> IN_REVIEW.
            async def transition():
                return await client.patch(f"/api/v1/appeals/{key}/status", headers=hdr(ids[2]), json={"status": "IN_REVIEW"})
            one, two = await asyncio.gather(transition(), transition())
            assert sorted([one.status_code, two.status_code]) == [200, 409], (one.text, two.text)
            assert (await client.get(f"/api/v1/appeals/{key}", headers=hdr(ids[0]))).json()["status"] == "IN_REVIEW"
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin_engine.dispose()
