"""Professor Layton 3DS plugin: XSCR round trips, editor rows, names in the definitions file; the game's files when present."""
from pathlib import Path

import pytest

from core.containers import level5
from plugins.layton_3ds import xscr
from plugins.layton_3ds.rules import SPEAKERS, folder_of
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

LAYTON = Path(r"E:\Emulators\RomHacking\Professor Layton")
SOURCES = [LAYTON / "Miracle Mask" / "source", LAYTON / "Azran Legacy" / "source", LAYTON / "vs Phoenix Wright" / "source"]
UKRAINIAN = "Ґанок і їжак"   # not in cp932: the game's fonts and encoding need other codes for these letters


def dialogue(crlf=False):
    return xscr.make([(1000, [12, 12]), (1001, [10, "手紙", "Dearest Hershel,"]),
                      (1001, [20, "手紙", "I trust this letter\nfinds you well."]),
                      (1001, [30, "レイトン", "この街がモンテドールなんですね"]), (1001, [40, "ルーク", ""]),
                      (1001, [50, "ルーク", "I trust this letter\nfinds you well."])], crlf=crlf)


def definitions():
    return xscr.make([(2500, [0, "レイトン教授と奇跡の仮面"]), (2500, [1, "Professor Layton and the Mask of Miracle"]),
                      (2153, [1, "bridge", "ブリッジ", "The Alchemist's Lair", "Alchemist"]),
                      (2301, [5, "風船を飛ばそう", "Bungle's Balloons", 47, "Swap", 20, "南通り", "", ""]),
                      (2213, [1, "#OFF"]), (9901, [1, "LSY_000_003"])])


def test_plugin_loads_and_validates():
    rules = check_loads("layton_3ds")
    assert rules.get_display_name() == "Professor Layton (3DS)"
    assert ".xs" in {e for f in rules.get_file_formats() for e in f.extensions}
    assert rules.get_capabilities() == {"speaker_attribution"}
    check_validator("layton_3ds")


def test_dialogue_rows_hide_japanese_and_empty_lines_and_round_trip():
    data = dialogue()
    check_round_trip("layton_3ds", data)
    script = xscr.parse(data)
    assert script.texts() == ["Dearest Hershel,", "I trust this letter\nfinds you well.", "I trust this letter\nfinds you well."]
    assert [r.speaker for r in script.rows] == ["手紙", "手紙", "ルーク"] and [r.line_id for r in script.rows] == [10, 20, 50]
    assert script.build(script.texts()) == data
    rules = load_rules("layton_3ds")
    blocks, names = rules.load_data_from_json_obj(data)
    assert rules.save_data_to_json_obj(blocks, names) == data


def test_changed_rows_are_written_and_the_rest_stays():
    data = dialogue()
    script = xscr.parse(data)
    out = script.build(["Любий Гершелю,", "I trust this letter\nfinds you well.", "Two lines\nhere"])
    again = xscr.parse(out)
    assert again.texts() == ["Любий Гершелю,", "I trust this letter\nfinds you well.", "Two lines\nhere"]
    assert [r.speaker for r in again.rows] == ["手紙", "手紙", "ルーク"]
    assert again.string(again.args[again.commands[3][2] + 2][1]) == "この街がモンテドールなんですね"   # the hidden line
    assert again.commands == script.commands and len(again.args) == len(script.args)
    assert level5.decompress(out[xscr.HEADER:]) == level5.decompress(data[xscr.HEADER:])


def test_crlf_files_keep_their_line_ending():
    data = dialogue(crlf=True)
    script = xscr.parse(data)
    assert script.crlf and script.texts()[1] == "I trust this letter\nfinds you well."
    out = script.build(["Dearest Hershel,", "Two\nlines", "I trust this letter\nfinds you well."])
    again = xscr.parse(out)
    assert again.texts()[1] == "Two\nlines" and b"Two\r\nlines" in again.strings


def test_definitions_file_shows_only_the_names_the_game_displays():
    script = xscr.parse(definitions())
    assert script.texts() == ["Professor Layton and the Mask of Miracle", "The Alchemist's Lair", "Alchemist",
                              "Bungle's Balloons", "Swap"]
    assert {r.kind for r in script.rows} == {"name"}
    out = script.build(["Професор Лейтон", "The Alchemist's Lair", "Alchemist", "Bungle's Balloons", "Swap"])
    assert xscr.parse(out).texts()[0] == "Професор Лейтон"


def test_letters_outside_cp932_are_refused_not_mangled():
    script = xscr.parse(dialogue())
    with pytest.raises(UnicodeEncodeError):
        script.build([UKRAINIAN, "x", "y"])


def test_folder_and_speaker_helpers():
    assert folder_of("txt/uk/50/50_000001.xs") == "50" and folder_of("res\\uk\\lt5_def.xs") == "res"
    assert SPEAKERS["レイトン"] == "Layton"


@pytest.mark.parametrize("source", SOURCES, ids=["mm", "al", "vspw"])
def test_every_game_script_parses_and_builds_back_unchanged(source):
    files = sorted(source.glob("txt/uk/**/*.xs")) + sorted(source.glob("res/uk/*_def*.xs"))
    if not files:
        pytest.skip(f"needs the workspace {source.parent}")
    rows = 0
    for path in files:
        raw = path.read_bytes()
        script = xscr.parse(raw)
        rows += len(script.rows)
        assert script.build(script.texts()) == raw, path
        rebuilt = script.build([t + "!" for t in script.texts()])   # every row changed: the tables are rewritten
        again = xscr.parse(rebuilt)
        assert again.texts() == [t + "!" for t in script.texts()], path
        assert again.commands == script.commands and len(again.args) == len(script.args), path
    assert rows > 10000
    names = xscr.parse(next(source.glob("res/uk/*_def*.xs")).read_bytes()).texts()
    assert names and all(not xscr.is_japanese(n) for n in names)
