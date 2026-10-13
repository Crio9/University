"""Seed reference data and Sprint 1 demo fixtures."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.dictionaries import Category, Tag
from app.models.post import Post
from app.models.profile import StaffProfile, StudentProfile
from app.models.user import User, UserRole

CATEGORIES = [
    ("Новости", "news"),
    ("Административное", "admin"),
    ("Возможности", "opportunities"),
]

TAGS = [
    ("Карьера", "career"),
    ("IT", "it"),
    ("Наука", "science"),
    ("Спорт", "sport"),
    ("Волонтёрство", "volunteering"),
    ("Стипендии", "scholarships"),
    ("Общежитие", "dormitory"),
    ("Документы", "documents"),
    ("Конференции", "conferences"),
    ("Стажировки", "internships"),
]


def _get_or_create_category(db: Session, name: str, slug: str) -> Category:
    item = db.query(Category).filter(Category.slug == slug).first()
    if item:
        return item
    item = Category(name=name, slug=slug)
    db.add(item)
    db.flush()
    return item


def _get_or_create_tag(db: Session, name: str, slug: str) -> Tag:
    item = db.query(Tag).filter(Tag.slug == slug).first()
    if item:
        return item
    item = Tag(name=name, slug=slug)
    db.add(item)
    db.flush()
    return item


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
    categories = {
        slug: _get_or_create_category(db, name, slug) for name, slug in CATEGORIES
    }
    tags = {slug: _get_or_create_tag(db, name, slug) for name, slug in TAGS}

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
        profile.interests = [tags["it"], tags["career"], tags["internships"]]
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
        profile.interests = [tags["scholarships"], tags["volunteering"]]
        db.add(profile)

    db.flush()

    existing_posts = db.query(Post).count()
    if existing_posts == 0:
        now = datetime.now(timezone.utc)
        demo_posts = [
            Post(
                title="Открытие карьерной ярмарки",
                body="Приглашаем студентов ФИТ на ярмарку вакансий и стажировок.",
                category_id=categories["opportunities"].id,
                author_id=staff.id,
                target_roles=["student"],
                target_faculties=["ФИТ"],
                target_courses=[],
                deadline=now + timedelta(days=14),
                tags=[tags["career"], tags["internships"], tags["it"]],
            ),
            Post(
                title="Срок подачи документов на стипендию",
                body="Не забудьте подать пакет документов до конца месяца.",
                category_id=categories["admin"].id,
                author_id=staff.id,
                target_roles=["student"],
                target_faculties=[],
                target_courses=[1, 2],
                deadline=now + timedelta(days=10),
                tags=[tags["scholarships"], tags["documents"]],
            ),
            Post(
                title="Университетские новости недели",
                body="Короткий дайджест событий кампуса для всех студентов.",
                category_id=categories["news"].id,
                author_id=staff.id,
                target_roles=["student"],
                target_faculties=[],
                target_courses=[],
                tags=[tags["sport"], tags["volunteering"]],
            ),
            Post(
                title="Научная конференция по ИИ",
                body="Приём тезисов на студенческую конференцию по искусственному интеллекту.",
                category_id=categories["opportunities"].id,
                author_id=staff.id,
                target_roles=["student"],
                target_faculties=["ФИТ"],
                target_courses=[3, 4],
                deadline=now + timedelta(days=30),
                tags=[tags["science"], tags["conferences"], tags["it"]],
            ),
            Post(
                title="Правила проживания в общежитии",
                body="Обновлённый регламент для проживающих в общежитии №2.",
                category_id=categories["admin"].id,
                author_id=staff.id,
                target_roles=["student"],
                target_faculties=[],
                target_courses=[],
                tags=[tags["dormitory"], tags["documents"]],
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
