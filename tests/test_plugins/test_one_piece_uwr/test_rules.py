"""One Piece: Unlimited World Red (3DS) plugin: jMSG tables, jfnt fonts and jIMG pictures (synthetic and the real
game's files when they are unpacked here)."""
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from plugins.one_piece_uwr import jmsg
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "one_piece_uwr"
ROMFS = Path(r"E:\Emulators\RomHacking\One Piece Unlimited World Red\3DS\romfs")


def make_jmsg(blocks, mask=0x10, tail=b"") -> bytes:
    """``blocks``: per language a list of (key, text) sorted by key."""
    count = len(blocks[0])
    pool, entries, at = b"", [], 0
    for block in blocks:
        for key, text in block:
            entries.append((key, at))
            pool += text.encode("utf-16-le") + b"\0\0"
            at += len(text) * 2 + 2
    base = 8 * len(entries)
    body = b"".join(struct.pack("<II", key, base + off) for key, off in entries) + pool + tail
    return b"jMSG" + struct.pack("<III", 16 + len(body), count, mask) + body


SAMPLE = make_jmsg([[(0x10, "Hello\u1a00\uf000\uf001\uf000 world\nbye"), (0x20, "Luffy"), (0x30, "Zoro")]])
MULTI = make_jmsg([[(0x10, "Hi"), (0x20, "Yes")], [(0x10, "Hallo"), (0x20, "Ja")]], mask=0x11)


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert ".jmsg" in {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_commands_are_tags_and_texts_round_trip():
    table = jmsg.Table(SAMPLE)
    assert table.texts() == ["Hello{c:000100} world\nbye", "Luffy", "Zoro"]
    assert jmsg.from_editor(jmsg.to_editor("a\u1a00\uf0dc\uf000\uf015\uf0ff{b}\ue001")) == "a\u1a00\uf0dc\uf000\uf015\uf0ff{b}\ue001"
    assert table.build(table.texts()) == SAMPLE
    changed = jmsg.Table(table.build(["A longer greeting{c:000100}", "Rufy", "Zoro"]))
    assert changed.texts() == ["A longer greeting{c:000100}", "Rufy", "Zoro"]
    assert struct.unpack_from("<I", changed.raw, 4)[0] == len(changed.raw)


def test_other_languages_stay_and_shared_strings_are_split():
    table = jmsg.Table(MULTI)
    assert table.block == 1 and table.texts() == ["Hallo", "Ja"]
    grown = jmsg.Table(table.build(["Hello there", "Ja"]))
    assert grown.texts() == ["Hello there", "Ja"]
    assert grown.strings[grown.entries[0][1]] == "Hi"             # the first language's block is untouched
    with pytest.raises(ValueError):
        table.build(["too few"])


def test_jimg_picture_round_trip_and_edit():
    header = b"jIMG" + struct.pack("<I", 0x80 + 16 * 16) + struct.pack("<HH", 16, 16) + bytes([16, 1, 4, 0x11]) + bytes(0x70)
    data = header + bytes(16 * 16)
    texture = texture_formats.read("jimg", data, {})[0]
    assert texture.image.size == (16, 16)
    assert texture_formats.write("jimg", data, {0: texture.image}, {}) == data
    image = texture.image.copy()
    image.paste((255, 255, 255, 255), (0, 0, 8, 8))
    changed = texture_formats.write("jimg", data, {0: image}, {})
    assert changed != data and len(changed) == len(data)
    assert texture_formats.read("jimg", changed, {})[0].image.getpixel((1, 1))[3] == 255
    assert texture_formats.detect(data) == "jimg"


def test_jfnt_model_and_pack():
    picture = b"jIMG" + struct.pack("<I", 0x80 + 64 * 16) + struct.pack("<HH", 64, 16) + bytes([16, 1, 4, 0x11]) + bytes(0x70) + bytes(64 * 16)
    head = b"JFNT" + struct.pack("<I", 0) + bytes([0, 0x0B, 0x54, 0x42]) + bytes([10, 14, 4, 2])
    head += struct.pack("<H", 1) + struct.pack("<HHH", 0x41, 0x44, 0) + struct.pack("<H", 4) + bytes([7, 8, 9, 10])
    head += bytes(-len(head) % 0x80)
    data = bytearray(head + picture)
    struct.pack_into("<I", data, 4, len(data))
    data = bytes(data)
    metadata, sheets = font_formats.extract("jfnt", data, {})
    assert [p["width"] for p in metadata["WID1"][0]["packets"]] == [7, 8, 9, 10]
    assert font_formats.pack("jfnt", metadata, sheets, data, {}) == data
    sheet = sheets[0].copy()
    sheet.paste((255, 255, 255, 255), (0, 0, 4, 4))
    metadata["WID1"][0]["packets"][1]["width"] = 12
    edited = font_formats.pack("jfnt", metadata, [sheet], data, {})
    assert edited != data and len(edited) == len(data)
    assert font_formats.extract("jfnt", edited, {})[1][0].getpixel((1, 1))[3] == 255
    assert font_formats.extract("jfnt", edited, {})[0]["WID1"][0]["packets"][1]["width"] == 12


@pytest.mark.skipif(not ROMFS.is_dir(), reason="One Piece UWR (3DS) is not unpacked here")
def test_real_game_files_round_trip():
    for name in ("msg_en", "system", "tutorial"):
        raw = (ROMFS / "message_eu" / f"{name}.jmsg").read_bytes()
        table = jmsg.Table(raw)
        assert table.build(table.texts()) == raw and len(table.texts()) >= 15
    for path in sorted((ROMFS / "font_eu").glob("*.jfnt")):
        raw = path.read_bytes()
        metadata, sheets = font_formats.extract("jfnt", raw, {})
        assert font_formats.pack("jfnt", metadata, sheets, raw, {}) == raw
    sample = sorted((ROMFS / "menu_eu" / "localize").glob("*_en_eu.jtex"))[:5]
    assert sample
    for path in sample:
        raw = path.read_bytes()
        image = texture_formats.read("jimg", raw, {})[0].image
        assert texture_formats.write("jimg", raw, {0: image}, {}) == raw
    assert isinstance(Image.new("RGBA", (1, 1)), Image.Image)


def test_switch_jimg_is_linear_rgba8():
    header = b"jIMG" + struct.pack("<I", 0x80 + 8 * 4 * 4) + struct.pack("<HH", 8, 4) + bytes([0, 1, 0, 0x11]) + bytes(0x70)
    data = header + bytes(8 * 4 * 4)
    texture = texture_formats.read("jimg", data, {})[0]
    assert texture.image.size == (8, 4)
    image = texture.image.copy()
    image.putpixel((3, 1), (10, 200, 30, 255))
    changed = texture_formats.write("jimg", data, {0: image}, {})
    at = 0x80 + (1 * 8 + 3) * 4
    assert changed[at:at + 4] == bytes([10, 200, 30, 255]) and len(changed) == len(data)
    assert texture_formats.read("jimg", changed, {})[0].image.getpixel((3, 1)) == (10, 200, 30, 255)
