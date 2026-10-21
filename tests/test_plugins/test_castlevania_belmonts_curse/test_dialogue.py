"""The dialogue graphs of the narration bundle: the index of their lines (collection, key id -> scenes and speakers),
the metadata of the table files, and the bundle names the plugin reads. The tests write their own bundle; no game data
is used."""
from plugins.castlevania_belmonts_curse import dialogue, tables, ui_text
from plugins.castlevania_belmonts_curse.dialogue import collection_of, index

from .test_unity_objects import CAB, _bundle, _serialized, node

GUID = "05a631be53c84614894c2c69eb5c32ff"


def _graph_root():
    line = node("LocalizedLine", "Line", [
        node("LocalizedTable", "m_TableReference", [node("string", "m_TableCollectionName")]),
        node("LocalizedEntry", "m_TableEntryReference", [node("SInt64", "m_KeyId"), node("string", "m_Key")]),
    ])
    actor = node("ActorRef", "ActorRef", [node("string", "m_AssetGUID")])
    step = node("DialogueNode", "data", [actor, line])
    return node("MonoBehaviour", "Base", [
        node("string", "m_Name"),
        node("vector", "m_Nodes", [node("Array", "Array", [node("int", "size"), step])]),
    ])


def _graph(name, steps):
    """A graph MonoBehaviour: its scene name and (speaker GUID or '', collection, key id) per dialogue node."""
    nodes = [{"ActorRef": {"m_AssetGUID": guid}, "Line": {"m_TableReference": {"m_TableCollectionName": collection},
                                                       "m_TableEntryReference": {"m_KeyId": key, "m_Key": ""}}}
             for guid, collection, key in steps]
    return {"m_Name": name, "m_Nodes": nodes}


def _narration_bundle():
    objects = [(1, 0, _graph("Scene_A", [(GUID, "Narration_ACT1", 3972030972), ("", "GUID:abcd", 5)])),
               (2, 0, _graph("Scene_B", [("", "Narration_ACT1", 3972030972), (GUID, "Narration_ACT2", 7)]))]
    return _bundle(_serialized([(114, _graph_root())], objects))


def test_the_index_lists_the_scenes_and_speakers_of_each_line():
    found, outside = index(_narration_bundle())
    assert found == {
        "Narration_ACT1": {3972030972: {"scenes": ["Scene_A", "Scene_B"], "speakers": [GUID]}},
        "Narration_ACT2": {7: {"scenes": ["Scene_B"], "speakers": [GUID]}},
    }
    assert outside == 1


def test_a_collection_name_drops_the_language_suffix_of_its_table():
    assert collection_of("Narration_ACT1_en") == "Narration_ACT1"
    assert collection_of("Narration_ACT1") == "Narration_ACT1"


def test_the_table_file_carries_the_scenes_and_speakers_and_the_parser_ignores_them():
    meta = {3972030972: {"scenes": ["Scene_A"], "speakers": []}}
    data = tables.table_json("Narration_ACT1_en", [(3972030972, "Line")], meta)
    assert b'"scenes"' in data and b'"speakers"' not in data
    assert tables.parse_table_json(data) == ("Narration_ACT1_en", [(3972030972, "Line")])


def test_the_narration_bundle_is_a_dialogue_bundle_and_an_interface_bundle():
    name = "Data/StreamingAssets/aa/Switch/narration_assets_all_5031c29dcaffbc31d486e6ae74705d17.bundle"
    assert dialogue.BUNDLE.match(name)
    assert ui_text.UI_BUNDLE.match(name)
    assert ui_text.table_name(name.rsplit("/", 1)[-1]) == "narration"
    other = "Data/StreamingAssets/aa/Switch/narration-scriptablevariablebase_assets_all_dda2.bundle"
    assert not dialogue.BUNDLE.match(other) and not ui_text.UI_BUNDLE.match(other)


def test_the_narration_texts_are_read_as_interface_texts():
    entries, unread = ui_text.entries(_narration_text_bundle())
    assert unread == 0
    assert entries == [(f"{CAB}/5", "All is silent.")]


def _narration_text_bundle():
    from .test_unity_objects import _text_root

    objects = [(5, 0, {"m_Name": "Narration", "m_text": "All is silent.", "m_fontAsset": 9, "m_fontSize": 20.0})]
    return _bundle(_serialized([(114, _text_root())], objects))
