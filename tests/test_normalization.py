import pytest

from app.services.dictionaries import sync_reference_data
from app.services.normalization import (
    normalize_category,
    normalize_classification,
    normalize_tag,
    normalize_tags,
)


def test_normalize_category_from_codes_and_aliases():
    assert normalize_category("OPPORTUNITY") == "OPPORTUNITY"
    assert normalize_category("opportunity") == "OPPORTUNITY"
    assert normalize_category("Возможности") == "OPPORTUNITY"
    assert normalize_category("  новости ") == "NEWS"
    assert normalize_category("квантовая физика") is None


def test_normalize_tag_maps_known_values_else_none():
    assert normalize_tag("HACKATHON") == "HACKATHON"
    assert normalize_tag("хакатон") == "HACKATHON"
    assert normalize_tag("стажировки") == "INTERNSHIP"
    assert normalize_tag("unknown-tag") is None


def test_normalize_tags_dedupes_truncates_and_reports_unresolved():
    result = normalize_tags(["CAREER", "карьера", "INTERNSHIP", "nonsense"])
    assert result.tags == ["CAREER", "INTERNSHIP"]
    assert result.unresolved_tags == ["nonsense"]
    assert result.is_fully_resolved is False


def test_normalize_tags_caps_at_five():
    raw = ["CAREER", "INTERNSHIP", "JOB", "SCIENCE", "RESEARCH", "SPORT"]
    result = normalize_tags(raw)
    assert result.tags == ["CAREER", "INTERNSHIP", "JOB", "SCIENCE", "RESEARCH"]


def test_normalize_classification_reports_unresolved_category():
    result = normalize_classification({"category": "что-то", "tags": ["CAREER"]})
    assert result.category is None
    assert result.unresolved_categories == ["что-то"]
    assert result.tags == ["CAREER"]
    assert result.is_fully_resolved is False


def test_normalization_uses_db_reference_rows(db):
    sync_reference_data(db)
    db.commit()
    # Value resolvable only through the DB row (not the static alias table).
    assert normalize_category("Учёба", db=db) == "ACADEMIC"
