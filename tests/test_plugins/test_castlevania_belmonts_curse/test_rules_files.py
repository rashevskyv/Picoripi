"""The plugin's project files load and save as bytes: a table file and an interface file each come back byte for byte, and
the format declares the bytes mode the loader needs."""
from plugins.castlevania_belmonts_curse import tables, ui_text
from plugins.castlevania_belmonts_curse.rules import GameRules


def test_the_plugin_declares_its_json_files_as_bytes():
    formats = GameRules(None).get_file_formats()
    assert [(item.extensions, item.mode) for item in formats] == [((".json",), "bytes")]


def test_a_table_file_round_trips_through_the_loader():
    data = tables.table_json("World_Catacombs_en", [(2522254586, "Catacombs"), (7, "")])
    rules = GameRules(None)
    blocks, names = rules.load_data_from_json_obj(data)
    assert blocks == [["Catacombs", ""]] and names == {}
    assert rules.save_data_to_json_obj(blocks, names) == data


def test_an_interface_file_round_trips_through_the_loader():
    data = ui_text.table_json("ui-hud", [("CAB-x/10", "Start"), ("CAB-x/13", "Options")])
    rules = GameRules(None)
    blocks, names = rules.load_data_from_json_obj(data)
    assert blocks == [["Start", "Options"]]
    assert rules.save_data_to_json_obj([["Почати", "Options"]], names) == \
        ui_text.table_json("ui-hud", [("CAB-x/10", "Почати"), ("CAB-x/13", "Options")])
