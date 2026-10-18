"""Series term fill into other projects (D45, item 1): the registry, the backup write, and the fill per project."""
import json
from pathlib import Path

from core.project_library import plugin_facts
from core.translation import series_fill
from core.translation.series_memory import REGISTRY_NAME


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_registry_names_every_project_registered_beside_a_series_glossary(tmp_path):
    series = tmp_path / "_glossary" / "glossary.json"
    series.parent.mkdir()
    series.write_text("[]", encoding="utf-8")
    (series.parent / REGISTRY_NAME).write_text(json.dumps({"TP": str(tmp_path / "tp" / "m.json")}), encoding="utf-8")
    other = tmp_path / "other" / "_glossary" / "glossary.json"
    other.parent.mkdir(parents=True)
    other.write_text("[]", encoding="utf-8")
    (other.parent / REGISTRY_NAME).write_text(json.dumps({"TP": str(tmp_path / "x.json"), "WW": str(tmp_path / "ww.json")}),
                                              encoding="utf-8")

    found = series_fill.registered_memories([series, other])

    assert found == {"TP": tmp_path / "tp" / "m.json", "WW": tmp_path / "ww.json"}


def test_a_backup_write_keeps_an_existing_entry_and_copies_the_first_backup_once(tmp_path):
    (tmp_path / "saved_translations.json").write_text(json.dumps({"a::k::0": "Старе"}), encoding="utf-8")

    first = series_fill.write_backup(tmp_path, {"a::k::0": "Нове", "a::k::1": "Пікачу"})
    series_fill.write_backup(tmp_path, {"a::k::2": "Івуй"})

    assert first == {"written": 1, "kept": 1}
    assert _json(tmp_path / "saved_translations.json") == {"a::k::0": "Старе", "a::k::1": "Пікачу", "a::k::2": "Івуй"}
    assert _json(tmp_path / "saved_translations.before_terms.json") == {"a::k::0": "Старе"}


def test_a_project_fill_writes_only_the_untranslated_lines_and_keeps_its_own_translation(tmp_path, monkeypatch):
    (tmp_path / "project.uiproj").write_text("{}", encoding="utf-8")
    source = ["Pikachu", "Hello there", "Pikachu", "Pikachu"]
    translation = ["", "", "Пікачу (зроблено)", "Pikachu"]  # the third is the owner's translation; the fourth copies the source
    monkeypatch.setattr(plugin_facts, "project_block_strings", lambda *a, **k: {
        "plugin": "fake", "blocks": [("romfs/x.dat", "", source, translation)],
    })
    monkeypatch.setattr(plugin_facts, "default_load_rules", lambda name: object())

    result = series_fill.fill_project(tmp_path, [("Pikachu", "Пікачу")], lambda: False)

    assert result["status"] == "done"
    assert result["by_status"] == {"fill": 2, "conflict": 1}
    assert result["written"] == 2 and result["kept"] == 0
    assert _json(tmp_path / "saved_translations.json") == {
        "romfs/x.dat::::0": "Пікачу",
        "romfs/x.dat::::3": "Пікачу",
    }


def test_a_project_without_a_term_is_reported_and_written_nowhere(tmp_path, monkeypatch):
    (tmp_path / "project.uiproj").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(plugin_facts, "project_block_strings", lambda *a, **k: {
        "plugin": "fake", "blocks": [("romfs/x.dat", "", ["Hello"], None)],
    })
    monkeypatch.setattr(plugin_facts, "default_load_rules", lambda name: object())

    assert series_fill.fill_project(tmp_path, [], lambda: False) == {"status": "no terms"}
    result = series_fill.fill_project(tmp_path, [("Pikachu", "Пікачу")], lambda: False)
    assert (result["status"], result["planned"], result["written"]) == ("done", 0, 0)
    assert not (tmp_path / "saved_translations.json").exists()


def test_a_folder_without_a_project_file_is_reported(tmp_path):
    assert series_fill.fill_project(tmp_path, [("Pikachu", "Пікачу")], lambda: False) == {"status": "no project file"}
