"""Family BMG adapter: the character map comes from the project folder, as in the app."""
import json

from plugins.zelda_bmg.family import make_rules


def test_make_rules_reads_the_character_map_of_the_project_folder(tmp_path):
    (tmp_path / "translation_map.json").write_text(json.dumps({"А": "¿"}), encoding="utf-8")
    rules = make_rules(tmp_path)
    rules.load_translation_map()
    assert rules.translation_map == {"А": "¿"}


def test_make_rules_without_a_project_uses_the_plugin_folder_map():
    rules = make_rules(None)
    rules.load_translation_map()
    assert isinstance(rules.translation_map, dict)


def test_recognise_uses_the_message_count_of_the_files_not_the_folder_name():
    from plugins.zelda_bmg.family import Unit, _member_key, recognise
    from pathlib import Path

    def units(file_counts):
        return [Unit(f"a.arc/{name}#{i}", "a.arc", name, i, "x") for name, n in file_counts.items() for i in range(n)]

    assert recognise(units({"zel_01.bmg": 1820, "zel_04.bmg": 1607})) == "gc"
    assert recognise(units({"zel_01.bmg": 1820, "zel_04.bmg": 1606})) == "wii"
    assert recognise(units({"zel_01.bmg": 1807})) == "hd"
    assert recognise(units({"zel_01.bmg": 5})) is None
    assert _member_key(Path("res/Msgus"), "hd") == "hd_msgus"
    assert _member_key(Path("res/Msguk"), "hd") == "hd_msguk"
    assert _member_key(Path("res/Msgus"), "gc") == "gc"
