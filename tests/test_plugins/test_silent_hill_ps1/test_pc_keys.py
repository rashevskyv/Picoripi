"""PC-port menu keys (not on the disc): the document, its blocks, and the pack lines. Synthetic data only."""
from plugins.silent_hill_ps1 import pc_keys


RAW = {
    "MENU.PC_Options": "PC_Options",
    "MENU.On": "On",                  # a disc key: left out when the disc supplies it
    "QUICK.Save": "Save",
    "COMMON.0": "not a menu key",
    "MENU.Odd=Key": "Odd=Key",
    "MENU.Number": 5,                 # not a string: left out
}


def test_only_port_menu_and_quick_keys_that_the_disc_does_not_carry_are_listed():
    doc = pc_keys.from_port_english(RAW, disc_keys={"MENU.On"})
    assert [e["key"] for e in doc["entries"]] == ["MENU.PC_Options", "QUICK.Save", "MENU.Odd=Key"]
    assert doc["format"] == pc_keys.FORMAT


def test_the_document_is_recognised_and_other_json_is_not():
    doc = pc_keys.from_port_english(RAW, disc_keys={"MENU.On"})
    assert pc_keys.is_document(doc)
    assert not pc_keys.is_document({"format": "other", "entries": []})
    assert not pc_keys.is_document(["MENU.PC_Options"])


def test_blocks_hold_the_english_and_a_translation_keeps_its_place():
    doc = pc_keys.from_port_english(RAW, disc_keys={"MENU.On"})
    blocks, names = pc_keys.blocks(doc)
    assert blocks == [["PC_Options", "Save", "Odd=Key"]]
    assert names == {"0": "PC port menu (not on the disc)"}
    edited = pc_keys.with_texts(doc, [["UA_Options", "", None]])
    assert [e["text"] for e in edited["entries"]] == ["UA_Options", "", "Odd=Key"]
    assert [e["key"] for e in edited["entries"]] == [e["key"] for e in doc["entries"]]


def test_pack_lines_use_the_translation_and_fall_back_to_the_english():
    doc = pc_keys.from_port_english(RAW, disc_keys={"MENU.On"})
    tr = pc_keys.with_texts(doc, [["UA_Options", "Зберегти", "Odd=Key"]])
    pairs = pc_keys.pack_pairs(doc, tr)
    assert pairs == [("MENU.PC_Options", "UA_Options"), ("QUICK.Save", "Зберегти"), ("MENU.Odd-Key", "Odd=Key")]
    assert pc_keys.pack_pairs(doc) == [("MENU.PC_Options", "PC_Options"), ("QUICK.Save", "Save"),
                                       ("MENU.Odd-Key", "Odd=Key")]


def test_a_line_break_in_a_value_becomes_a_space():
    doc = {"format": pc_keys.FORMAT, "entries": [{"key": "MENU.Two", "text": "one\ntwo"}]}
    assert pc_keys.pack_pairs(doc) == [("MENU.Two", "one two")]


def test_the_plugin_loads_the_document_as_blocks_and_saves_it_back_with_the_translation():
    from plugins.silent_hill_ps1.rules import GameRules

    rules = GameRules()
    doc = pc_keys.from_port_english(RAW, disc_keys={"MENU.On"})
    blocks, names = rules.load_data_from_json_obj(doc)
    assert blocks == pc_keys.blocks(doc)[0] and names == {"0": "PC port menu (not on the disc)"}
    saved = rules.save_data_to_json_obj([["UA_Options", "Зберегти", "Odd=Key"]], names)
    assert saved == pc_keys.with_texts(doc, [["UA_Options", "Зберегти", "Odd=Key"]])
