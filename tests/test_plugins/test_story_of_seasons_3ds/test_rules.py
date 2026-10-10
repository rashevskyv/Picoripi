"""Harvest Moon 3D / Story of Seasons (3DS) plugin: PAPA tables and Tale of Two Towns message tables (synthetic and
the real games when their workspaces are unpacked here)."""
import struct
from pathlib import Path

import pytest

from plugins.story_of_seasons_3ds import papa, ttt
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "story_of_seasons_3ds"
ANB = Path(r"E:\Emulators\RomHacking\Story of Seasons\A New Beginning\source\romfs")
TTT = Path(r"E:\Emulators\RomHacking\Story of Seasons\Tale of Two Towns\3DS\source\romfs")


def make_papa(rows, slots=()) -> bytes:
    """A PAPA table of ``(tag, label, text)`` rows (text None = an empty field); ``slots`` adds value columns."""
    entries = []
    for tag, label, text in rows:
        fields = [tag.encode() + bytes(-len(tag) % 4 or 4), label.encode() + bytes(-len(label) % 4 or 4),
                  papa.encode(text) if text is not None else b""]
        offsets, pos = [], 8 + 4 * (3 + len(slots))
        for blob in fields:
            offsets.append(pos if blob else 0)
            pos += len(blob)
        entries.append(struct.pack(f"<II{3 + len(slots)}I", pos, 3 + len(slots), *offsets, *slots) + b"".join(fields))
    section = struct.pack("<II", 8 + 4 * len(entries), len(entries))
    first = 0x0C + len(section) + 4 * len(entries)
    offsets, at = [], first
    for entry in entries:
        offsets.append(at)
        at += len(entry)
    return b"PAPA" + bytes(4) + struct.pack("<I", 0x0C) + section + struct.pack(f"<{len(entries)}I", *offsets) + b"".join(entries)


SAMPLE = make_papa([("Msg", "MES_A", "Crops won't grow\nhere now."), ("Msg", "MES_B", "<RED>Echo</RED>{0D}\nok"),
                    ("Msg", "MES_C", None)], slots=(1, 2040))


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".papa", ".mes"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_papa_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_papa_texts_labels_and_rebuild():
    table = papa.Table(SAMPLE)
    assert table.columns == [2] and table.tag == "Msg"
    assert table.texts() == ["Crops won't grow\nhere now.", "<RED>Echo</RED>{0D}\nok", ""]
    assert table.ids() == ["MES_A", "MES_B", "MES_C"]
    assert table.build(table.texts()) == SAMPLE
    grown = papa.Table(table.build(["A much longer line of text", "x", "now filled"]))
    assert grown.texts() == ["A much longer line of text", "x", "now filled"]
    assert grown.entries[0].offsets[3:] == [1, 2040]                  # value slots stay as they were


def test_papa_rejects_identifier_and_number_columns():
    table = papa.Table(make_papa([("ItemData", "ITEM_1", "i_to_0001"), ("ItemData", "ITEM_2", "i_to_0002")]))
    assert table.columns == [] and table.texts() == []


def test_ttt_codes_and_tables():
    assert ttt.encode("Not in use") == [0x82E, 0x84F, 0x854, 0x800, 0x849, 0x84E, 0x800, 0x855, 0x853, 0x845]
    assert ttt.decode(ttt.encode("Löschen {1000}!\nÉ")) == "Löschen {1000}!\nÉ"
    assert ttt.encode("Ґ")[0] == 0x800 + ttt.FIRST_FREE + 4
    with pytest.raises(ValueError):
        ttt.encode("ы")
    strings = [ttt.encode("Yes") + [ttt.END], ttt.encode("No") + [ttt.END], [0x2330, ttt.END]]
    body = b"".join(struct.pack(f"<{len(s)}H", *s) for s in strings)
    ends, at = [], 4 * len(strings)
    for s in strings:
        at += 2 * len(s)
        ends.append(at + 4)
    raw = struct.pack("<3I", *ends) + body + b"\0\0"
    table = ttt.Table(raw)
    assert table.is_text() and table.texts() == ["Yes", "No", "{2330}"]
    assert table.build(table.texts()) == raw
    again = ttt.Table(table.build(["Так", "Ні", "{2330}"]))
    assert again.texts() == ["Так", "Ні", "{2330}"] and again.tail == b"\0\0"
    assert not ttt.Table(bytes(16)).is_text()
    pack = ttt.write_pack([raw, b"\x0f\x27"])
    assert ttt.read_pack(pack) == [raw, b"\x0f\x27"] and ttt.write_pack(ttt.read_pack(pack), pack) == pack


def test_mes_sample_survives_load_and_save():
    raw = ttt.Table(struct.pack("<I", 4 + 4 + 2 * 4) + struct.pack("<4H", *ttt.encode("Hi!"), ttt.END)).raw
    check_round_trip(PLUGIN, raw)


@pytest.mark.skipif(not (ANB / "Msg.xbb").is_dir(), reason="A New Beginning not unpacked here")
def test_real_anb_tables_round_trip_and_hold_the_game_text():
    rules = load_rules(PLUGIN)
    files = sorted(ANB.rglob("*.papa"))
    strings = 0
    for path in files:
        raw = path.read_bytes()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        strings += len(blocks[0])
    assert len(files) >= 370 and strings >= 47000
    talk = papa.Table((ANB / "Msg.xbb" / "Talk_ALLEN.papa").read_bytes())
    assert "Oh, <MYNAME>, it's you?" in talk.texts()[1] and talk.ids()[0] == "MES_MORNING_00"
    items = papa.Table((ANB / "GameData" / "ItemList.xbb" / "ItemDataBase.papa").read_bytes())
    assert items.texts()[:2] == ["Sickle", "Copper Sickle"] and items.ids()[0] == "ITEM_SICKLE"


@pytest.mark.skipif(not (TTT / "mes_data.bin").is_dir(), reason="The Tale of Two Towns not unpacked here")
def test_real_ttt_tables_round_trip_and_hold_the_game_text():
    rules = load_rules(PLUGIN)
    strings = tables = 0
    for path in sorted(TTT.glob("*mes_data.bin/*.mes")):
        raw = path.read_bytes()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        if blocks[0]:
            tables += 1
            strings += len(blocks[0])
    assert tables >= 550 and strings >= 30000
    menu = ttt.Table((TTT / "mes_data.bin" / "0042.mes").read_bytes()).texts()
    assert menu[1:4] == ["New Game", "Continue", "Multiplayer"]


SOS = Path(r"E:\Emulators\RomHacking\Story of Seasons\Story of Seasons\source\romfs")
TRIO = Path(r"E:\Emulators\RomHacking\Story of Seasons\Trio of Towns\source\romfs")


@pytest.mark.skipif(not (SOS / "MsgGB.xbb").is_dir(), reason="Story of Seasons not unpacked here")
def test_real_sos_tables_round_trip_and_hold_the_english_text():
    rules = load_rules(PLUGIN)
    files = sorted(SOS.rglob("*.papa"))
    strings = 0
    for path in files:
        raw = path.read_bytes()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        strings += len(blocks[0])
    assert len(files) >= 420 and strings >= 42000
    assert not list(SOS.glob("MsgDE.xbb")) and not list(SOS.glob("Layout/de"))      # the English set only
    menu = papa.Table((SOS / "MsgGB.xbb" / "GameInitSetting.papa").read_bytes())
    assert "New Game" in menu.texts() and "MSG_NEW_GAME" in menu.ids()


@pytest.mark.skipif(not (TRIO / "en" / "Msg.xbb").is_dir(), reason="Trio of Towns not unpacked here")
def test_real_trio_tables_round_trip_including_the_nested_data_text():
    rules = load_rules(PLUGIN)
    files = sorted(TRIO.rglob("*.papa"))
    strings = 0
    for path in files:
        raw = path.read_bytes()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        strings += len(blocks[0])
    assert len(files) >= 840 and strings >= 43000
    nested = sorted((TRIO / "en" / "DataText.xbb.gz").rglob("*.papa"))
    assert nested and all(p.parent.name.endswith(".xbb") for p in nested)
    menu = papa.Table((TRIO / "en" / "Msg.xbb" / "OtherScreen.papa").read_bytes())
    assert "New Game" in menu.texts() and "TitleNewGame" in menu.ids()
