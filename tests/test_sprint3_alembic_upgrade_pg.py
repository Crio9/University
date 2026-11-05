"""Real Alembic upgrade and historical backfill on disposable PostgreSQL schemas.

Requires TEST_DATABASE_URL to point to a dedicated TEST database, never the
application DB. Unlike ORM create_all tests, these execute SQL migrations.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import settings

ROOT = Path(__file__).resolve().parents[1]


def _test_db_urls() -> tuple[str, str]:
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("TEST_DATABASE_URL must point to a dedicated PostgreSQL test database")
    url = make_url(raw)
    if not url.drivername.startswith("postgresql+"):
        pytest.skip("This test requires a PostgreSQL test database")
    db_name = url.database or ""
    if "test" not in db_name.lower() and "ci" not in db_name.lower():
        pytest.fail("Unsafe TEST_DATABASE_URL: database name must include 'test' or 'ci'")
    sync = url.set(drivername="postgresql+psycopg2")
    if sync.query:
        pytest.fail("Use a plain TEST_DATABASE_URL without query options for migration isolation")
    return sync.render_as_string(hide_password=False), db_name


def _original_group_key(parts: tuple[str, str, str, str]) -> str:
    values = [" ".join(value.strip().casefold().replace("ё", "е").split()) for value in parts]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


@pytest.mark.parametrize("start_revision", ["0004_schedule", "0004_university"])
def test_upgrade_from_either_sprint3_branch_preserves_schedule_and_staff_grants(
    start_revision: str, monkeypatch: pytest.MonkeyPatch,
):
    """Both historical branches converge; unique rows are linked, unknown retained."""
    base_url, _ = _test_db_urls()
    schema = "s3_mig_" + uuid.uuid4().hex
    # Postgres libpq accepts -cNAME=VALUE; avoid URL % escapes because
    # alembic.ini uses configparser interpolation on sqlalchemy.url.
    scoped_url = f"{base_url}?options=-csearch_path={schema}"
    admin_engine = create_engine(base_url)
    scoped_engine = create_engine(scoped_url)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    monkeypatch.setattr(settings, "ALEMBIC_DATABASE_URL", scoped_url)

    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        # Exercise both published 0004 heads before converging on 0005.
        command.upgrade(cfg, start_revision)
        command.upgrade(cfg, "0005_merge_s3")

        group_values = ("ДГТУ", "ФИСТ", "ПМИ", "ИВТ-31")
        group_key = _original_group_key(group_values)
        unknown_values = ("ДГТУ", "ФИСТ", "ПМИ", "НЕИЗВЕСТНАЯ-99")
        unknown_key = _original_group_key(unknown_values)
        start = datetime(2026, 11, 9, 10, tzinfo=timezone(timedelta(hours=3)))
        end = datetime(2026, 11, 9, 11, 30, tzinfo=timezone(timedelta(hours=3)))

        with scoped_engine.begin() as connection:
            admin_id = connection.execute(text("""
                INSERT INTO users (email, password_hash, full_name, role)
                VALUES ('s3-migration-admin@example.test', 'unused', 'Admin', 'admin')
                RETURNING id
            """)).scalar_one()
            staff_id = connection.execute(text("""
                INSERT INTO users (email, password_hash, full_name, role)
                VALUES ('s3-migration-staff@example.test', 'unused', 'Staff', 'staff')
                RETURNING id
            """)).scalar_one()

            def insert_legacy(parts: tuple[str, str, str, str], key: str) -> int:
                return connection.execute(text("""
                    INSERT INTO schedule_entries
                        (group_key, university, faculty, study_program, study_group,
                         subject, starts_at, ends_at, status, created_by)
                    VALUES
                        (:key, :university, :faculty, :program, :group,
                         'Backend', :start, :end, 'NORMAL', :admin_id)
                    RETURNING id
                """), {
                    "key": key, "university": parts[0], "faculty": parts[1],
                    "program": parts[2], "group": parts[3],
                    "start": start, "end": end, "admin_id": admin_id,
                }).scalar_one()

            matched_id = insert_legacy(group_values, group_key)
            unknown_id = insert_legacy(unknown_values, unknown_key)
            connection.execute(text("""
                INSERT INTO staff_schedule_groups (staff_id, group_key)
                VALUES (:staff_id, :group_key)
            """), {"staff_id": staff_id, "group_key": group_key})

        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")  # Reapplying must not erase data.

        with scoped_engine.connect() as connection:
            heads = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            assert heads == ["0007_merge_appeals_schedule"]
            linked = connection.execute(text("""
                SELECT s.id, s.group_key, s.university, s.faculty, s.study_program,
                       s.study_group, s.study_group_id, g.code
                FROM schedule_entries s
                LEFT JOIN study_groups g ON g.id = s.study_group_id
                WHERE s.id = :id
            """), {"id": matched_id}).mappings().one()
            assert linked["study_group_id"] is not None
            assert linked["code"] == "IVT-31"
            assert (linked["university"], linked["faculty"], linked["study_program"],
                    linked["study_group"]) == group_values
            assert linked["group_key"] == group_key

            unknown = connection.execute(text("""
                SELECT group_key, study_group, study_group_id FROM schedule_entries
                WHERE id = :id
            """), {"id": unknown_id}).mappings().one()
            assert unknown["group_key"] == unknown_key
            assert unknown["study_group"] == "НЕИЗВЕСТНАЯ-99"
            assert unknown["study_group_id"] is None

            grant = connection.execute(text("""
                SELECT study_group_id, group_key FROM staff_schedule_groups
                WHERE staff_id = :staff_id
            """), {"staff_id": staff_id}).mappings().one()
            assert grant["study_group_id"] == linked["study_group_id"]
            assert grant["group_key"] == group_key
    finally:
        scoped_engine.dispose()
        try:
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            admin_engine.dispose()
