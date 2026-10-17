"""Project cards from project.uiproj, the string counts, and the cached index."""
import json

import pytest

from core.project_library import index
from core.project_library.cards import count_strings, percent_translated, read_card


def _uiproj(folder, **fields):
    folder.mkdir(parents=True, exist_ok=True)
    project_file = folder / "project.uiproj"
    data = {"id": "p-1", "name": "Aria", "plugin_name": "", "blocks": [{"name": "a"}], "metadata": {},
            "modified_at": "2026-10-01T10:00:00"}
    data.update(fields)
    project_file.write_text(json.dumps(data), encoding="utf-8")
    return project_file


def test_count_strings_follows_the_translated_rule():
    original = [["Hello", "[tag]", "Bye"], ["Ok"]]
    translated_file = [["Hola", "", "Adios"]]
    edited = {(1, 0): "Vale"}

    counts = count_strings(original, translated_file, edited)

    # "[tag]" has no text after the tags are removed, so it needs no translation.
    assert counts == {"lines": 4, "needs_translation": 3, "translated": 3}


def test_a_translation_equal_to_the_source_is_not_counted():
    counts = count_strings([["Same"]], [["Same"]], {})

    assert counts == {"lines": 1, "needs_translation": 1, "translated": 0}


@pytest.mark.parametrize(("counts", "expected"), [
    ({"needs_translation": 0, "translated": 0}, None),
    ({"needs_translation": 3, "translated": 1}, 33),
    ({"needs_translation": 2, "translated": 2}, 100),
])
def test_percent_translated_is_none_when_nothing_needs_translation(counts, expected):
    assert percent_translated(counts) == expected


def test_card_reports_missing_plugin_and_paths(tmp_path):
    project = _uiproj(tmp_path / "picoripi", plugin_name="no_such_plugin_xyz",
                      metadata={"source_path": "sources/none", "translation_path": str(tmp_path / "gone")})

    card = read_card(project)

    assert card["name"] == "Aria"
    assert card["blocks"] == 1
    assert card["project_id"] == "p-1"
    assert set(card["issues"]) == {"plugin_missing", "source_missing", "translation_missing"}


def test_card_of_a_missing_file_raises_os_error(tmp_path):
    with pytest.raises(OSError):
        read_card(tmp_path / "picoripi" / "project.uiproj")


def test_card_of_a_broken_file_raises_value_error(tmp_path):
    folder = tmp_path / "picoripi"
    folder.mkdir()
    (folder / "project.uiproj").write_text("{ broken", encoding="utf-8")

    with pytest.raises(ValueError):
        read_card(folder / "project.uiproj")


def test_index_merge_keeps_the_fields_of_other_writers(tmp_path):
    index.merge(tmp_path, {"k": {"card": {"name": "Aria"}}})
    index.merge(tmp_path, {"k": {"counts": {"lines": 4}}})

    assert index.read(tmp_path) == {"k": {"card": {"name": "Aria"}, "counts": {"lines": 4}}}


def test_record_counts_stores_the_counts_under_the_project_key(tmp_path):
    counts = index.record_counts(tmp_path, "k", [["Hello"]], [["Hola"]], {})

    entry = index.read(tmp_path)["k"]
    assert entry["counts"] == counts == {"lines": 1, "needs_translation": 1, "translated": 1}
    assert entry["counted_at"]


def test_unreadable_index_is_set_aside(tmp_path):
    index.index_path(tmp_path).write_text("[1, 2", encoding="utf-8")

    assert index.read(tmp_path) == {}
    assert index.index_path(tmp_path).with_name("project_index.json.unreadable").exists()


def test_card_keeps_the_role_files_the_wizard_took_and_drops_anything_else(tmp_path):
    folder = tmp_path / "picoripi"
    folder.mkdir()
    project = folder / "project.uiproj"
    project.write_text(json.dumps({"plugin_name": "fake", "blocks": [], "metadata": {
        "source_roles": {"base": "/games/aria.iso", "": "/x", "update": ""}}}), encoding="utf-8")

    assert read_card(project)["source_roles"] == {"base": "/games/aria.iso"}

    project.write_text(json.dumps({"plugin_name": "fake", "blocks": [], "metadata": {"source_roles": ["a"]}}),
                       encoding="utf-8")
    assert read_card(project)["source_roles"] == {}
