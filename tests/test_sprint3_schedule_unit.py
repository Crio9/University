"""Fast checks for Schedule contracts; PostgreSQL API tests are below."""
from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.schedule import GroupSelector, ScheduleAccessGrant, ScheduleCreate, ScheduleUpdate
from app.services.schedule import group_key, period_bounds


def test_same_group_independent_of_case_spacing():
    a = GroupSelector(university="ДГТУ", faculty="ФИСТ", study_program="ПМИ", study_group="ИВТ-31")
    b = GroupSelector(university=" дгту ", faculty=" фист", study_program="пми", study_group=" ивт-31 ")
    c = GroupSelector(university="ЮФУ", faculty="ФИСТ", study_program="ПМИ", study_group="ИВТ-31")
    assert group_key(a) == group_key(b)
    assert group_key(a) != group_key(c)


def test_missing_group_returns_409():
    class P:
        university = "ДГТУ"
        faculty = "ФИСТ"
        study_program = "ПМИ"
        study_group = None
    with pytest.raises(HTTPException) as error:
        group_key(P())
    assert error.value.status_code == 409


def test_day_week_bounds_are_exclusive_and_monday_based():
    start, end = period_bounds(week=date(2026, 11, 4))
    assert start.date() == date(2026, 11, 1)  # Moscow midnight -> previous UTC date
    assert (end - start).days == 7
    with pytest.raises(HTTPException):
        period_bounds(day=date(2026, 11, 4), week=date(2026, 11, 4))


def test_time_validation():
    fields = dict(study_group_id=12, subject="Math")
    with pytest.raises(ValidationError):
        ScheduleCreate(**fields, starts_at="2026-11-04T10:00:00", ends_at="2026-11-04T12:00:00")
    with pytest.raises(ValidationError):
        ScheduleCreate(**fields, starts_at="2026-11-04T12:00:00+03:00", ends_at="2026-11-04T10:00:00+03:00")
    assert ScheduleUpdate(status="CANCELLED").status == "CANCELLED"


def test_new_requests_use_positive_canonical_group_id():
    with pytest.raises(ValidationError):
        ScheduleAccessGrant(staff_id=2, study_group_id=0)
    with pytest.raises(ValidationError):
        ScheduleCreate(
            study_group_id=-1, subject="Math",
            starts_at="2026-11-04T10:00:00+03:00",
            ends_at="2026-11-04T11:30:00+03:00",
        )
    assert ScheduleAccessGrant(staff_id=2, study_group_id=12).study_group_id == 12
