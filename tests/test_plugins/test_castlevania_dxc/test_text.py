"""Castlevania: The Dracula X Chronicles text codecs on small files made here."""
from plugins.castlevania_dxc import text
from plugins.castlevania_dxc.rules import GameRules

STD = b"Gasp!\\nHow lovely...\r\nNo!\\nNever!\r\n"


def _overlay():
    """An MWo3 overlay: an item name (cells, FF 00), its description (00-ended, padded) and a script line."""
    head = b"MWo3" + bytes(0x1C) + b"test.bin" + bytes(0x80 - 0x28)
    name = bytes(c - 0x20 for c in b"Short sword") + b"\xff\x00"            # 13 bytes, room to 16
    name += bytes(-len(name) % 4)
    desc = b"Common short sword\0" + bytes(-19 % 4) + bytes(4)
    script = b"\x0b\x06\x0a\x02\x06That voice...\x01Maria?\x03\x08\x00\x00\x00"
    return head + name + desc + script


def test_std_lines_read_and_save():
    assert text.std_lines(STD) == ["Gasp!\nHow lovely...", "No!\nNever!"]
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(STD)
    assert rules.save_data_to_json_obj(blocks, names) == STD
    missing = set()
    out = text.std_build(STD, ["Ой!\nЯк гарно...", None], missing)
    assert missing == {"О", "й", "Я", "к", "г", "а", "р", "н", "о"}
    assert out.endswith(b"\r\nNo!\\nNever!\r\n")


def test_ukrainian_codes_from_the_translation_map_are_bytes():
    out = text.std_build(STD, ["\x80\xde", None], set())
    assert out.startswith(b"\x80\xde\r\n")
    assert text.std_lines(out)[0] == "\x80\xde"


def test_overlay_units_and_their_room():
    data = _overlay()
    units = text.units(data)
    assert [u.kind for u in units] == ["cell", "string", "script"]
    assert text.overlay_texts(data) == ["Short sword", "Common short sword", "That voice...\nMaria?"]
    cell, string, script = units
    assert (cell.length, cell.room) == (11, 14)
    assert (string.length, string.room) == (18, 19)          # up to the 4-byte slot
    assert script.room == script.length


def test_overlay_edits_stay_in_place():
    data = _overlay()
    missing, too_long = set(), []
    out = text.overlay_build(data, ["Long sword", "A sword for all battles!!", "Hi.\nMaria!"], missing, too_long)
    assert len(out) == len(data)
    assert text.overlay_texts(out) == ["Long sword", "A sword for all bat", "Hi.\nMaria!          "]
    assert too_long == ["A sword for all battles!!"]
    assert out[-5:] == data[-5:]                    # the commands after the script line stay
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(data)
    assert rules.save_data_to_json_obj(blocks, names) == data


def test_boot_strings():
    block = (b"\0".join(["セーブデータ".encode()] + [b"Castlevania The Dracula X Chronicles", b"Save data",
                                                       b"Unlocked Original Game"]) + b"\0\0\0Sauvegarde\0")
    data = b"\x7fELF" + bytes(12) + block
    assert text.boot_texts(data) == ["Castlevania The Dracula X Chronicles", "Save data", "Unlocked Original Game"]
    too_long = []
    out = text.boot_build(data, [None, "UA TEST", "Unlocked Original Game, really"], too_long)
    assert len(out) == len(data)
    assert text.boot_texts(out)[1:] == ["UA TEST", "Unlocked Original Game, "]   # the zeros before the next block are room too
    assert too_long == ["Unlocked Original Game, really"]
