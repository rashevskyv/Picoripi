"""Headless translation import on a small real project: the plugin's table format writes the file, mismatches are refused."""
import json

from core.project_library.translation_import import import_translations
from plugins.luigis_mansion_1_gc.messages import Table

SOURCE = "files/Event/event01.szp/message/message01.csv"


def _project(tmp_path):
    unpacked = tmp_path / "unpacked"
    (unpacked / SOURCE).parent.mkdir(parents=True)
    (unpacked / SOURCE).write_bytes(b"one\r\ntwo\r\n")
    project = tmp_path / "project.uiproj"
    project.write_text(json.dumps({
        "plugin_name": "luigis_mansion_1_gc",
        "metadata": {"source_path": str(unpacked), "translation_path": str(tmp_path / "translation")},
        "blocks": [{"name": "message01", "source_file": SOURCE, "translation_file": SOURCE}],
    }), encoding="utf-8")
    return project


def _lines(en_two="two"):
    return {
        "event01:1": {"id": "event01:1", "en": "one", "file": SOURCE},
        "event01:2": {"id": "event01:2", "en": en_two, "file": SOURCE},
    }


def test_apply_writes_the_translation_through_the_plugin_table(tmp_path):
    project = _project(tmp_path)
    report = import_translations(project, _lines(), {"event01:2": "Їжа"}, apply=True)
    written = tmp_path / "translation" / SOURCE
    assert report["applied"] == 1 and report["problems"] == []
    assert Table(written.read_bytes()).texts() == ["one", "Їжа"]
    assert list((tmp_path / "data" / "backups").glob("project.uiproj.*.bak"))


def test_dry_run_writes_nothing(tmp_path):
    project = _project(tmp_path)
    report = import_translations(project, _lines(), {"event01:2": "Їжа"}, apply=False)
    assert report["applied"] == 1
    assert not (tmp_path / "translation").exists()
    assert not (tmp_path / "data").exists()


def test_english_that_differs_from_the_project_is_refused_and_not_written(tmp_path):
    project = _project(tmp_path)
    report = import_translations(project, _lines(en_two="tw0"), {"event01:2": "Їжа"}, apply=True)
    assert report["applied"] == 0
    assert report["problems"] == [{"id": "event01:2", "problem": "English differs from the project"}]
    assert not (tmp_path / "translation" / SOURCE).exists()


def test_id_missing_from_the_lines_file_is_reported(tmp_path):
    project = _project(tmp_path)
    report = import_translations(project, _lines(), {"event01:9": "x"}, apply=False)
    assert report["problems"] == [{"id": "event01:9", "problem": "id not in the lines file"}]


def test_a_character_without_a_code_is_substituted_with_a_warning_and_the_line_is_written(tmp_path):
    project = _project(tmp_path)
    report = import_translations(project, _lines(), {"event01:1": "Їжа", "event01:2": "Zen trè"}, apply=True)
    assert report["applied"] == 2 and report["problems"] == []
    assert report["warnings"] == [{"id": "event01:2",
                                   "warning": "record 2: the character 'è' has no Shift-JIS code; written as 'e'"}]
    assert Table((tmp_path / "translation" / SOURCE).read_bytes()).texts() == ["Їжа", "Zen tre"]


def test_a_character_with_no_base_letter_is_written_as_question_mark_with_a_warning(tmp_path):
    project = _project(tmp_path)
    report = import_translations(project, _lines(), {"event01:2": "ђ"}, apply=False)
    assert report["applied"] == 1 and report["problems"] == []
    assert [item["id"] for item in report["warnings"]] == ["event01:2"]
