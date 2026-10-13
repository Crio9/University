import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.db.base import Base
from app.db.database import get_db
from app.main import app as fastapi_app


@pytest.mark.asyncio
async def test_auth_register_and_login():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async def override_get_db():
            async with Session() as session:
                yield session

        fastapi_app.dependency_overrides[get_db] = override_get_db
        transport = ASGITransport(app=fastapi_app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            reg_resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "test@student.com",
                    "password": "secretpassword",
                    "full_name": "Test Student",
                    "role": "student",
                },
            )
            assert reg_resp.status_code == 200

            dup_resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "test@student.com",
                    "password": "secretpassword",
                    "full_name": "Test Student",
                    "role": "student",
                },
            )
            assert dup_resp.status_code == 409

            login_resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "test@student.com",
                    "password": "secretpassword",
                },
            )
            assert login_resp.status_code == 200
            data = login_resp.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"

            bad_login = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "test@student.com",
                    "password": "wrongpassword",
                },
            )
            assert bad_login.status_code == 401
    finally:
        fastapi_app.dependency_overrides.clear()
        await engine.dispose()
