"""Mario vs. Donkey Kong (GBA) plugin: text.json loads, round-trips and validates; byte tags stay as they are."""
import json

from plugins.mario_vs_donkey_kong_gba import rules as mvdk_rules
from plugins.mario_vs_donkey_kong_gba.tag_manager import TagManager
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "mario_vs_donkey_kong_gba"
SAMPLE = json.dumps({"format": mvdk_rules.FORMAT, "groups": [
    {"name": "Block 0x078B94", "items": [
        {"id": "s078b94", "text": "English"},
        {"id": "s078bb4", "text": "SWAP BOXES TO\nSAVE YOUR PRIZE{C3}{A9}"}]}]},
    ensure_ascii=False, indent=1) + "\n"


def test_the_plugin_loads_round_trips_and_validates():
    check_loads(PLUGIN)
    check_round_trip(PLUGIN, SAMPLE)
    check_validator(PLUGIN)


def test_a_save_keeps_the_candidate_key_and_writes_texts_by_position():
    rules = mvdk_rules.GameRules()
    doc = json.loads(SAMPLE)
    doc["groups"][0]["items"][0]["candidate"] = "Англійська"
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    blocks, _names = rules.load_data_from_json_obj(text)
    blocks[0][0] = "UA TEST"
    saved = json.loads(rules.save_data_to_json_obj(blocks))
    item = saved["groups"][0]["items"][0]
    assert item["text"] == "UA TEST"
    assert item["candidate"] == "Англійська"
    assert item["id"] == "s078b94"


def test_byte_tags_are_recognised_and_lowercase_is_not_a_tag():
    tags = TagManager()
    assert tags.is_tag_legitimate("{C3}")
    assert not tags.is_tag_legitimate("{C3A9}")
    assert not tags.is_tag_legitimate("{7b}")
