"""Regression coverage missing in the initial sprint3 merge.

A linked profile may retain legacy strings; Feed must use its StudyGroup.
"""
import pytest
from sqlalchemy import select

from app.models.dictionaries import Category
from app.models.post import Post
from app.models.profile import StudentProfile
from app.models.university import Faculty, StudyGroup, StudyProgram, University
from app.models.user import User
from app.services.audience import normalize_audience
from app.services.university import load_profile, student_context
from tests.test_ingest import env  # noqa: F401 - shared SQLite API fixture


@pytest.mark.asyncio
async def test_linked_student_feed_uses_orm_group_and_canonical_names(env):
    async with env["Session"]() as db:
        student = await db.scalar(select(User).where(User.email == "student@uni.test"))
        staff = await db.scalar(select(User).where(User.email == "staff@uni.test"))
        news = await db.scalar(select(Category).where(Category.code == "NEWS"))
        assert student is not None and staff is not None and news is not None

        # Emulate an already-applied migration where FIST is called ФИСТ,
        # whereas app/core/university.py calls the same code ФИТ.
        uni = University(code="DSTU", name="Донской государственный технический университет")
        faculty = Faculty(code="FIST", name="ФИСТ", university=uni)
        program = StudyProgram(code="PMI", name="ПМИ", faculty=faculty)
        group = StudyGroup(code="IVT-31", name="ИВТ-31", program=program)
        db.add(group)
        await db.flush()
        group_id = group.id
        student_id = student.id

        profile = await db.get(StudentProfile, student_id)
        assert profile is not None
        profile.study_group_id = group_id
        profile.university = "УСТАРЕВШИЙ ВУЗ"
        profile.faculty = "УСТАРЕВШИЙ ФАКУЛЬТЕТ"
        profile.study_program = "УСТАРЕВШАЯ ПРОГРАММА"
        profile.study_group = "СТАРАЯ ГРУППА"
        profile.course = 2

        item = Post(
            title="Объявление для группы",
            content="Важная новость",
            category_id=news.id,
            author_id=staff.id,
            importance="standard",
            target_audience={
                "faculty": ["ФИТ"], "program": ["ПМИ"],
                "course": [2], "group": ["ИВТ-31"],
            },
        )
        db.add(item)
        await db.commit()
        post_id = item.id

    async with env["Session"]() as db:
        profile = await load_profile(db, student_id)
        assert profile is not None
        assert profile.group_entity is not None
        assert profile.group_entity.id == group_id
        context = student_context(profile)
        assert context.faculty == "ФИТ"
        assert context.group == "ИВТ-31"
        normalized, unresolved = await normalize_audience(db, {
            "faculty": ["ФИСТ"], "program": [], "course": [], "group": [],
        })
        assert unresolved == []
        assert normalized.faculty == ["ФИТ"]

    feed = await env["client"].get("/api/v1/posts/feed", headers=env["student"])
    assert feed.status_code == 200, feed.text
    assert [item["id"] for item in feed.json()] == [post_id]

    me = await env["client"].get("/api/v1/profile/me", headers=env["student"])
    assert me.status_code == 200, me.text
    assert me.json()["profile"]["faculty"] == "ФИТ"
    assert me.json()["profile"]["study_group_id"] == group_id
