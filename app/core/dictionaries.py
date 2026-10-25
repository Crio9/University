"""Canonical content dictionaries shared by seed, migrations and AI normalisation.

The single source of truth for the approved category and tag vocabulary
described in "Правила классификации университетского контента".

Machine identifiers (``code``) are upper-case and match the AI contract, e.g.
``category = "OPPORTUNITY"`` or ``tags = ["CAREER", "INTERNSHIP"]``. The ``name``
is the human-readable (Russian) label stored in the DB and shown in the UI.
"""

from __future__ import annotations

import enum
from typing import NamedTuple


class DictionaryEntry(NamedTuple):
    code: str
    name: str


class CategoryCode(str, enum.Enum):
    ACADEMIC = "ACADEMIC"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    OPPORTUNITY = "OPPORTUNITY"
    EVENT = "EVENT"
    NEWS = "NEWS"


class TagCode(str, enum.Enum):
    CAREER = "CAREER"
    INTERNSHIP = "INTERNSHIP"
    JOB = "JOB"
    SCIENCE = "SCIENCE"
    RESEARCH = "RESEARCH"
    CONFERENCE = "CONFERENCE"
    SCHOLARSHIP = "SCHOLARSHIP"
    GRANT = "GRANT"
    COMPETITION = "COMPETITION"
    OLYMPIAD = "OLYMPIAD"
    HACKATHON = "HACKATHON"
    INTERNATIONAL = "INTERNATIONAL"
    EXCHANGE = "EXCHANGE"
    VOLUNTEERING = "VOLUNTEERING"
    STUDENT_LIFE = "STUDENT_LIFE"
    SPORT = "SPORT"
    CULTURE = "CULTURE"
    SCHEDULE = "SCHEDULE"
    EXAM = "EXAM"
    PRACTICE = "PRACTICE"
    THESIS = "THESIS"
    DOCUMENTS = "DOCUMENTS"
    DORMITORY = "DORMITORY"
    FINANCE = "FINANCE"
    CAMPUS = "CAMPUS"


CANONICAL_CATEGORIES: tuple[DictionaryEntry, ...] = (
    DictionaryEntry("ACADEMIC", "Учёба"),
    DictionaryEntry("ADMINISTRATIVE", "Административное"),
    DictionaryEntry("OPPORTUNITY", "Возможности"),
    DictionaryEntry("EVENT", "События"),
    DictionaryEntry("NEWS", "Новости"),
)

CANONICAL_TAGS: tuple[DictionaryEntry, ...] = (
    DictionaryEntry("CAREER", "Карьера"),
    DictionaryEntry("INTERNSHIP", "Стажировки"),
    DictionaryEntry("JOB", "Вакансии"),
    DictionaryEntry("SCIENCE", "Наука"),
    DictionaryEntry("RESEARCH", "Исследования"),
    DictionaryEntry("CONFERENCE", "Конференции"),
    DictionaryEntry("SCHOLARSHIP", "Стипендии"),
    DictionaryEntry("GRANT", "Гранты"),
    DictionaryEntry("COMPETITION", "Конкурсы"),
    DictionaryEntry("OLYMPIAD", "Олимпиады"),
    DictionaryEntry("HACKATHON", "Хакатоны"),
    DictionaryEntry("INTERNATIONAL", "Международные программы"),
    DictionaryEntry("EXCHANGE", "Обмены"),
    DictionaryEntry("VOLUNTEERING", "Волонтёрство"),
    DictionaryEntry("STUDENT_LIFE", "Студенческая жизнь"),
    DictionaryEntry("SPORT", "Спорт"),
    DictionaryEntry("CULTURE", "Культура"),
    DictionaryEntry("SCHEDULE", "Расписание"),
    DictionaryEntry("EXAM", "Экзамены"),
    DictionaryEntry("PRACTICE", "Практика"),
    DictionaryEntry("THESIS", "ВКР"),
    DictionaryEntry("DOCUMENTS", "Документы"),
    DictionaryEntry("DORMITORY", "Общежитие"),
    DictionaryEntry("FINANCE", "Финансы"),
    DictionaryEntry("CAMPUS", "Кампус"),
)

CATEGORY_CODES: frozenset[str] = frozenset(c.value for c in CategoryCode)
TAG_CODES: frozenset[str] = frozenset(t.value for t in TagCode)

CATEGORY_NAMES: dict[str, str] = {c.code: c.name for c in CANONICAL_CATEGORIES}
TAG_NAMES: dict[str, str] = {t.code: t.name for t in CANONICAL_TAGS}

# Aliases (already normalised) -> canonical code. Used to map the free-form
# strings an AI might return onto the approved vocabulary. Unknown values are
# intentionally NOT added to the dictionary.
_RAW_ALIASES: dict[str, str] = {
    "academic": "ACADEMIC",
    "учёба": "ACADEMIC",
    "учеба": "ACADEMIC",
    "учебный": "ACADEMIC",
    "учебный процесс": "ACADEMIC",
    "administrative": "ADMINISTRATIVE",
    "admin": "ADMINISTRATIVE",
    "административное": "ADMINISTRATIVE",
    "организационное": "ADMINISTRATIVE",
    "opportunity": "OPPORTUNITY",
    "opportunities": "OPPORTUNITY",
    "возможности": "OPPORTUNITY",
    "возможность": "OPPORTUNITY",
    "event": "EVENT",
    "events": "EVENT",
    "событие": "EVENT",
    "события": "EVENT",
    "мероприятие": "EVENT",
    "news": "NEWS",
    "новости": "NEWS",
    "новость": "NEWS",
    "career": "CAREER",
    "карьера": "CAREER",
    "карьерный": "CAREER",
    "internship": "INTERNSHIP",
    "internships": "INTERNSHIP",
    "стажировка": "INTERNSHIP",
    "стажировки": "INTERNSHIP",
    "job": "JOB",
    "jobs": "JOB",
    "вакансия": "JOB",
    "вакансии": "JOB",
    "работа": "JOB",
    "science": "SCIENCE",
    "наука": "SCIENCE",
    "научный": "SCIENCE",
    "research": "RESEARCH",
    "исследование": "RESEARCH",
    "исследования": "RESEARCH",
    "conference": "CONFERENCE",
    "conferences": "CONFERENCE",
    "конференция": "CONFERENCE",
    "конференции": "CONFERENCE",
    "scholarship": "SCHOLARSHIP",
    "scholarships": "SCHOLARSHIP",
    "стипендия": "SCHOLARSHIP",
    "стипендии": "SCHOLARSHIP",
    "grant": "GRANT",
    "grants": "GRANT",
    "грант": "GRANT",
    "гранты": "GRANT",
    "competition": "COMPETITION",
    "competitions": "COMPETITION",
    "конкурс": "COMPETITION",
    "конкурсы": "COMPETITION",
    "olympiad": "OLYMPIAD",
    "olympiads": "OLYMPIAD",
    "олимпиада": "OLYMPIAD",
    "олимпиады": "OLYMPIAD",
    "hackathon": "HACKATHON",
    "hackathons": "HACKATHON",
    "хакатон": "HACKATHON",
    "хакатоны": "HACKATHON",
    "international": "INTERNATIONAL",
    "международный": "INTERNATIONAL",
    "международные": "INTERNATIONAL",
    "exchange": "EXCHANGE",
    "обмен": "EXCHANGE",
    "обмены": "EXCHANGE",
    "volunteering": "VOLUNTEERING",
    "волонтёрство": "VOLUNTEERING",
    "волонтерство": "VOLUNTEERING",
    "student life": "STUDENT_LIFE",
    "студенческая жизнь": "STUDENT_LIFE",
    "sport": "SPORT",
    "sports": "SPORT",
    "спорт": "SPORT",
    "culture": "CULTURE",
    "культура": "CULTURE",
    "schedule": "SCHEDULE",
    "расписание": "SCHEDULE",
    "exam": "EXAM",
    "exams": "EXAM",
    "экзамен": "EXAM",
    "экзамены": "EXAM",
    "зачёт": "EXAM",
    "зачет": "EXAM",
    "practice": "PRACTICE",
    "практика": "PRACTICE",
    "thesis": "THESIS",
    "вкр": "THESIS",
    "диплом": "THESIS",
    "document": "DOCUMENTS",
    "documents": "DOCUMENTS",
    "документ": "DOCUMENTS",
    "документы": "DOCUMENTS",
    "dormitory": "DORMITORY",
    "общежитие": "DORMITORY",
    "finance": "FINANCE",
    "финансы": "FINANCE",
    "оплата": "FINANCE",
    "campus": "CAMPUS",
    "кампус": "CAMPUS",
}


def normalise_key(value: str) -> str:
    """Lower-case, strip and collapse separators so aliases match reliably."""
    return " ".join(
        value.strip().lower().replace("_", " ").replace("-", " ").split()
    )


ALIASES: dict[str, str] = {
    normalise_key(alias): code for alias, code in _RAW_ALIASES.items()
}
