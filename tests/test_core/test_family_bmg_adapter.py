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
