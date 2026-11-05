"""Pure migration resolver tests; require no PostgreSQL connection."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0006_schedule_group_fk.py"
spec = importlib.util.spec_from_file_location("sprint3_0006", MIGRATION)
assert spec is not None and spec.loader is not None
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def _groups():
    def g(group_id, u_code, u_name, f_code, f_name, p_code, p_name, g_code, g_name):
        return dict(group_id=group_id, university_code=u_code, university_name=u_name,
                    faculty_code=f_code, faculty_name=f_name,
                    program_code=p_code, program_name=p_name,
                    group_code=g_code, group_name=g_name)
    return [
        g(1, "DSTU", "Донской государственный технический университет",
          "FIST", "ФИСТ", "PMI", "ПМИ", "IVT-31", "ИВТ-31"),
        g(2, "DSTU", "Донской государственный технический университет",
          "IOT", "ИОТ", "PMI-IOT", "ПМИ", "IOT-IVT-31", "ИВТ-31"),
        g(3, "SFEDU", "Южный федеральный университет",
          "SFEDU-IOT", "ИОТ", "SFEDU-IOT-PMI", "ПМИ", "SFEDU-IVT-31", "ИВТ-31"),
    ]


def test_migration_resolves_legacy_fist_by_full_context():
    assert migration._lookup_group({
        "university": "ДГТУ", "faculty": " ФИСТ ",
        "study_program": "ПМИ", "study_group": "ИВТ-31"
    }, _groups()) == 1


def test_migration_resolves_current_fist_alias():
    assert migration._lookup_group({
        "university": "ДГТУ", "faculty": "ФИТ",
        "study_program": "ПМИ", "study_group": "ИВТ-31"
    }, _groups()) == 1


def test_migration_resolves_iot_alias_without_conflating_universities():
    assert migration._lookup_group({
        "university": "ДГТУ", "faculty": "ИОТ",
        "study_program": "ПМИ ИОТ", "study_group": "ИОТ-31"
    }, _groups()) == 2
    assert migration._lookup_group({
        "university": "ЮФУ", "faculty": "ИОТ ЮФУ",
        "study_program": "ПМИ ЮФУ", "study_group": "ЮФУ-ИВТ-31"
    }, _groups()) == 3


def test_migration_does_not_guess_ambiguous_or_unknown_group():
    assert migration._lookup_group({"study_group": "ИВТ-31"}, _groups()) is None
    assert migration._lookup_group({"study_group": "Несуществующая"}, _groups()) is None
    assert migration._lookup_group({"study_group": ""}, _groups()) is None


def test_staff_key_matches_original_hash_and_known_aliases():
    import hashlib
    import json
    parts = ("ДГТУ", "ФИСТ", "ПМИ", "ИВТ-31")
    legacy = hashlib.sha256(json.dumps(
        [s.casefold() for s in parts], ensure_ascii=False
    ).encode()).hexdigest()
    assert migration._legacy_key(parts) == legacy
    assert legacy in migration._candidate_keys(_groups()[0])


def test_only_one_alembic_head_after_merge():
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert heads == ["0007_merge_appeals_schedule"]
