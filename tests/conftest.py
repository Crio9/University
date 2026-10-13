import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

base_db_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:111@localhost:5432/uni_personal",
)
test_db_url = base_db_url.rsplit("/", 1)[0] + "/uni_personal_test"
os.environ["DATABASE_URL"] = test_db_url
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.core.config import get_settings
from app.db.base import Base
from app.db.database import get_db
from app.main import app
from app.models import *  # noqa: F401,F403

get_settings.cache_clear()
settings = get_settings()

engine = create_engine(settings.database_url, poolclass=NullPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    # Create test DB if missing (connect to default db first)
    admin_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    db_name = settings.database_url.rsplit("/", 1)[-1]
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
