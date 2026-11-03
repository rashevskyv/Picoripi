"""The Super Metroid text.json as a translation table: the import reads, refuses and writes it by item id."""
import json

import pytest

from core.project_library.translation_import import import_translations
from plugins.super_metroid import rules as sm_rules

SOURCE = "text.json"
SAMPLE = json.dumps({"format": sm_rules.FORMAT, "groups": [
    {"name": "Message boxes", "items": [{"id": "msg.01.EnergyTank", "text": "ENERGY TANK", "width": 19, "lines": 1,
                                         "symbol": "kMessageBox_1_EnergyTank"}]},
    {"name": "Intro", "items": [{"id": "intro.page1", "text": "I FIRST BATTLED\nTHE METROIDS", "width": 30, "lines": 7,
                                 "symbol": "addr_kCinematicBgObjectDef_8BCF3F"}]}]}, ensure_ascii=False, indent=1) + "\n"
EN = {"msg.01.EnergyTank": "ENERGY TANK", "intro.page1": "I FIRST BATTLED\nTHE METROIDS"}


def _table(raw=SAMPLE.encode("utf-8")):
    return sm_rules.GameRules().parse_table(raw)


def test_the_table_lists_every_item_text_and_id_in_group_order():
    table = _table()
    assert table.ids() == ["msg.01.EnergyTank", "intro.page1"]
    assert table.texts() == ["ENERGY TANK", "I FIRST BATTLED\nTHE METROIDS"]


def test_build_puts_the_texts_back_by_position_and_keeps_the_layout():
    doc = json.loads(_table().build(["ЕНЕРГОРЕЗЕРВУАР", "ПЕРШИЙ\nРЯДОК"]).decode("utf-8"))
    items = [item for group in doc["groups"] for item in group["items"]]
    assert [item["text"] for item in items] == ["ЕНЕРГОРЕЗЕРВУАР", "ПЕРШИЙ\nРЯДОК"]
    assert [(item["id"], item["width"], item["lines"]) for item in items] == [
        ("msg.01.EnergyTank", 19, 1), ("intro.page1", 30, 7)]
    assert [group["name"] for group in doc["groups"]] == ["Message boxes", "Intro"]


def test_build_refuses_a_text_count_that_does_not_match():
    with pytest.raises(ValueError):
        _table().build(["ONLY ONE"])


@pytest.mark.parametrize("raw", [b"not json", b'{"format": "other", "groups": []}', b'{"format": "%s"}' % sm_rules.FORMAT.encode()])
def test_a_file_that_is_not_the_workspace_text_is_not_a_table(raw):
    assert _table(raw) is None


def test_import_writes_the_translation_text_json_by_item_id(tmp_path):
    unpacked = tmp_path / "source"
    unpacked.mkdir()
    (unpacked / SOURCE).write_text(SAMPLE, encoding="utf-8")
    project = tmp_path / "project.uiproj"
    project.write_text(json.dumps({
        "plugin_name": "super_metroid",
        "metadata": {"source_path": str(unpacked), "translation_path": str(tmp_path / "translation")},
        "blocks": [{"name": "Text", "source_file": SOURCE, "translation_file": SOURCE}],
    }), encoding="utf-8")
    lines = {key: {"id": key, "en": en, "file": SOURCE} for key, en in EN.items()}
    translations = {"msg.01.EnergyTank": "ЕНЕРГОРЕЗЕРВУАР", "intro.page1": "ПЕРШИЙ\nРЯДОК"}

    report = import_translations(project, lines, translations, apply=True)

    assert report["applied"] == 2 and report["problems"] == []
    written = json.loads((tmp_path / "translation" / SOURCE).read_text(encoding="utf-8"))
    assert [item["text"] for g in written["groups"] for item in g["items"]] == ["ЕНЕРГОРЕЗЕРВУАР", "ПЕРШИЙ\nРЯДОК"]
