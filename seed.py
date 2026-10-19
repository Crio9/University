"""Seed reference data and Sprint 1 demo fixtures."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.dictionaries import CANONICAL_CATEGORIES, CANONICAL_TAGS
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.dictionaries import Category, Tag
from app.models.post import Post
from app.models.profile import StaffProfile, StudentProfile
from app.models.user import User, UserRole
from app.services.dictionaries import slug_for_code, sync_reference_data

def _get_or_create_user(
    db: Session,
    *,
    email: str,
    password: str,
    role: UserRole,
) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(email=email, hashed_password=hash_password(password), role=role)
    db.add(user)
    db.flush()
    return user


def seed(db: Session) -> None:
    # Reconcile the canonical reference vocabulary (idempotent).
    sync_reference_data(db)
    categories = {
        entry.code: db.query(Category).filter(Category.slug == slug_for_code(entry.code)).one()
        for entry in CANONICAL_CATEGORIES
    }
    tags = {
        entry.code: db.query(Tag).filter(Tag.slug == slug_for_code(entry.code)).one()
        for entry in CANONICAL_TAGS
    }

    staff = _get_or_create_user(
        db, email="staff@example.com", password="staff123", role=UserRole.STAFF
    )
    if staff.staff_profile is None:
        db.add(
            StaffProfile(
                user_id=staff.id,
                full_name="Анна Сотрудникова",
                department="Деканат",
                position="Специалист по работе со студентами",
            )
        )

    student_it = _get_or_create_user(
        db, email="student.it@example.com", password="student123", role=UserRole.STUDENT
    )
    if student_it.student_profile is None:
        profile = StudentProfile(
            user_id=student_it.id,
            full_name="Иван Иванов",
            faculty="ФИТ",
            course=3,
            group_name="ФИТ-301",
        )
        profile.interests = [tags["CAREER"], tags["INTERNSHIP"], tags["SCIENCE"]]
        db.add(profile)

    student_law = _get_or_create_user(
        db, email="student.law@example.com", password="student123", role=UserRole.STUDENT
    )
    if student_law.student_profile is None:
        profile = StudentProfile(
            user_id=student_law.id,
            full_name="Мария Петрова",
            faculty="Юрфак",
            course=1,
            group_name="Ю-101",
        )
        profile.interests = [tags["SCHOLARSHIP"], tags["VOLUNTEERING"]]
        db.add(profile)

    db.flush()

    existing_posts = db.query(Post).count()
    if existing_posts == 0:
        now = datetime.now(timezone.utc)
        demo_posts = [
            Post(
                title="Открытие карьерной ярмарки",
                body="Приглашаем студентов ФИТ на ярмарку вакансий и стажировок.",
                category_id=categories["OPPORTUNITY"].id,
                author_id=staff.id,
                target_roles=["student"],
                target_faculties=["ФИТ"],
                target_courses=[],
                deadline=now + timedelta(days=14),
                summary="Ярмарка вакансий и стажировок для студентов ФИТ.",
                ai_confidence=0.95,
                tags=[tags["CAREER"], tags["INTERNSHIP"]],
            ),
            Post(
                title="Срок подачи документов на стипендию",
                body="Не забудьте подать пакет документов до конца месяца.",
                category_id=categories["ADMINISTRATIVE"].id,
                author_id=staff.id,
                target_roles=["student"],
                target_faculties=[],
                target_courses=[1, 2],
                deadline=now + timedelta(days=10),
                summary="Подать пакет документов на стипендию до конца месяца.",
                tags=[tags["SCHOLARSHIP"], tags["DOCUMENTS"]],
            ),
            Post(
                title="Университетские новости недели",
                body="Короткий дайджест событий кампуса для всех студентов.",
                category_id=categories["NEWS"].id,
                author_id=staff.id,
                target_roles=["student"],
                target_faculties=[],
                target_courses=[],
                tags=[tags["SPORT"], tags["VOLUNTEERING"]],
            ),
            Post(
                title="Научная конференция по ИИ",
                body="Приём тезисов на студенческую конференцию по искусственному интеллекту.",
                category_id=categories["EVENT"].id,
                author_id=staff.id,
                target_roles=["student"],
                target_faculties=["ФИТ"],
                target_courses=[3, 4],
                deadline=now + timedelta(days=30),
                summary="Приём тезисов на студенческую конференцию по ИИ.",
                tags=[tags["SCIENCE"], tags["CONFERENCE"], tags["RESEARCH"]],
            ),
            Post(
                title="Правила проживания в общежитии",
                body="Обновлённый регламент для проживающих в общежитии №2.",
                category_id=categories["ADMINISTRATIVE"].id,
                author_id=staff.id,
                target_roles=["student"],
                target_faculties=[],
                target_courses=[],
                tags=[tags["DORMITORY"], tags["DOCUMENTS"]],
            ),
        ]
        db.add_all(demo_posts)

    db.commit()
    print("Seed completed:")
    print("  categories:", db.query(Category).count())
    print("  tags:", db.query(Tag).count())
    print("  users:", db.query(User).count())
    print("  posts:", db.query(Post).count())


if __name__ == "__main__":
    session = SessionLocal()
    try:
        seed(session)
    finally:
        session.close()
