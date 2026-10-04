"""Series glossary: import, project link, copy/promote, conflicts and prompt precedence."""
import json
from pathlib import Path

import pytest

import utils.constants as constants
from core.glossary.series import (
    entries_from_json,
    find_conflicts,
    import_series_glossary,
    link_series,
    linked_series_path,
    series_rows_for,
)
from core.glossary_manager import (
    STATUS_CONFIRMED,
    STATUS_TRANSLATED,
    DescriptionFragment,
    GlossaryEntry,
    GlossaryManager,
)
from core.project_models import Project

SERIES_DOC = {
    "generated": "2026-10-03",
    "sources": {"TP": "TP project", "MC": "Minish Cap"},
    "terms": [
        {
            "term": "Beedle", "category": "Character", "games": ["WW", "MC"],
            "renderings": [
                {"source": "TP", "uk": "Бідл", "forms": ["Бідл"]},
                {"source": "MC", "uk": "Бідл", "forms": ["Бідл", "Бідла"]},
            ],
            "recommended": "Бідл", "status": "agreed", "reason": "", "options": [],
            "note": "Travelling merchant.", "aliases": ["BEEDLE"],
        },
        {
            "term": "Nabooru", "category": "Character", "games": ["OoT"], "renderings": [],
            "recommended": "Набору", "status": "decision", "reason": "No source.",
            "options": ["Набору (Japanese, Kovalenko)", "Набуру (English spelling)"],
            "note": "Gerudo thief.", "aliases": [],
        },
    ],
}


def _manager(path: Path, rows) -> GlossaryManager:
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=path, raw_text=path.read_text(encoding="utf-8"))
    return manager


def test_series_document_maps_to_glossary_entries_keeping_variants_and_status():
    beedle, nabooru = entries_from_json(SERIES_DOC)

    assert beedle["original"] == "Beedle" and beedle["translation"] == "Бідл"
    assert beedle["section"] == "Character" and beedle["notes"] == "Travelling merchant."
    assert beedle["status"] == STATUS_CONFIRMED
    assert beedle["aliases"] == ["BEEDLE"]
    # One variant per distinct rendering, every source and extra form kept.
    assert beedle["translation_variants"] == [{"translation": "Бідл", "rationale": "TP, MC; forms: Бідла"}]
    assert "Series status: agreed" in beedle["user_notes"]

    assert nabooru["status"] == STATUS_TRANSLATED  # a decision still needs a person
    assert [v["translation"] for v in nabooru["translation_variants"]] == ["Набору", "Набуру"]
    assert nabooru["translation_variants"][0]["rationale"] == "Japanese, Kovalenko"
    assert "Reason: No source." in nabooru["user_notes"]


def test_project_glossary_list_imports_unchanged_and_garbage_is_refused():
    rows = [{"original": "Link", "translation": "Лінк", "notes": ""}]
    assert entries_from_json(rows) == rows
    with pytest.raises(ValueError):
        entries_from_json({"something": 1})


def test_import_writes_into_settings_series_folder_and_loads_as_glossary(tmp_path):
    source = tmp_path / "zelda_series_glossary.json"
    source.write_text(json.dumps(SERIES_DOC, ensure_ascii=False), encoding="utf-8")

    target = import_series_glossary(source)

    assert target == constants.SETTINGS_DIR / "series_glossaries" / "zelda_series_glossary.json"
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=target, raw_text=target.read_text(encoding="utf-8"))
    assert {e.original for e in manager.get_entries()} == {"Beedle", "Nabooru"}
    assert manager.get_entry("BEEDLE").translation == "Бідл"  # aliases survive
    manager.update_entry("Nabooru", "Набуру", "Gerudo thief.")
    assert "Набуру" in target.read_text(encoding="utf-8")  # edits persist to the series file


def test_project_link_round_trips_and_old_projects_have_none(tmp_path):
    old = Project.from_dict({"name": "old"})
    assert linked_series_path(old) is None

    link_series(old, tmp_path / "zelda.json")
    reloaded = Project.from_dict(json.loads(json.dumps(old.to_dict())))
    assert linked_series_path(reloaded) == tmp_path / "zelda.json"

    link_series(reloaded, None)
    assert linked_series_path(reloaded) is None
    assert "series_glossary" not in reloaded.metadata


def test_import_entry_adds_new_terms_and_updates_existing_without_losing_project_data(tmp_path):
    project = _manager(tmp_path / "glossary.json", [
        {"original": "Hylian Shield", "translation": "Гілійський щит", "notes": "old note",
         "user_notes": "mine", "fragments": [{"text": "seen", "block_idx": 3, "string_idx": 4}]},
    ])
    series_shield = GlossaryEntry("Hylian Shields", "Хайлійський щит", "", section="Item", status=STATUS_CONFIRMED)
    series_beedle = GlossaryEntry(
        "Beedle", "Бідл", "merchant", fragments=(DescriptionFragment("elsewhere", 1, 2),), id="series-id"
    )

    with project.transaction():
        project.import_entry(series_shield)
        project.import_entry(series_beedle)

    shield = project.get_entry("Hylian Shield")
    assert shield.translation == "Хайлійський щит" and shield.status == STATUS_CONFIRMED
    assert shield.notes == "old note" and shield.user_notes == "mine"  # empty source notes keep ours
    assert shield.fragments and shield.section == "Item"
    beedle = project.get_entry("Beedle")
    assert beedle.translation == "Бідл" and beedle.fragments == () and beedle.id != "series-id"
    saved = json.loads((tmp_path / "glossary.json").read_text(encoding="utf-8"))
    assert {row["original"] for row in saved} == {"Hylian Shield", "Beedle"}


def test_conflicts_are_terms_both_translate_differently():
    project = [
        GlossaryEntry("Cucco", "Кукко", ""),
        GlossaryEntry("Beedle", "Бідл", ""),
        GlossaryEntry("Epona", "", "", status="seeded"),
    ]
    series = [
        GlossaryEntry("cuccos", "Кокко", ""),   # same term by canonical key
        GlossaryEntry("Beedle", "бідл", ""),    # case only: no conflict
        GlossaryEntry("Epona", "Епона", ""),    # project has no translation yet
    ]
    assert find_conflicts(project, series) == {"cucco": ("Кукко", "Кокко")}


def test_series_rows_only_for_terms_the_project_does_not_translate(tmp_path):
    project = _manager(tmp_path / "glossary.json", [
        {"original": "Link", "translation": "Лінк", "notes": ""},
        {"original": "Epona", "translation": "", "notes": "", "status": "seeded"},
    ])
    series = _manager(tmp_path / "series.json", [
        {"original": "Link", "translation": "Лiнк-серія", "notes": ""},
        {"original": "Epona", "translation": "Епона", "notes": ""},
        {"original": "Beedle", "translation": "Бідл", "notes": ""},
    ])

    rows = series_rows_for("Link rides Epona to Beedle", series, project)

    assert [e.original for e in rows] == ["Epona", "Beedle"]
    assert series_rows_for("Link", None, project) == []
