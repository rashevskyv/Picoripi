"""Fantasy Life plugin: the text table codec and ztex / FNT formats on synthetic data, then on the real EU game files
(skipped where the workspace is not on this machine)."""
import json
import struct
from pathlib import Path

import pytest
from PIL import Image

from plugins.fantasy_life import l5text
from plugins.fantasy_life.l5text import L5Text, decode, encode
from plugins.fantasy_life.rules import GameRules


def _table(strings, pad4=True, container=False):
    """A text table (and optionally a container with a second item) from raw string entries."""
    entries = [s + (bytes(-len(s) % 4) if pad4 else b"") for s in strings]
    head = bytearray(0x38)
    struct.pack_into("<I", head, 0, l5text.TABLE_MAGIC)
    struct.pack_into("<I", head, 0x10, 0x20)
    struct.pack_into("<IIIIII", head, 0x20, 0x10A, 0, 0, len(entries), 4, 0x38)
    at = 0x38 + 4 * len(entries)
    offsets = []
    for e in entries:
        offsets.append(at)
        at += len(e)
    table = bytes(head) + struct.pack(f"<{len(entries)}I", *offsets) + b"".join(entries)
    table = bytearray(table)
    struct.pack_into("<I", table, 0x0C, len(table) - 0x20)
    if not container:
        return bytes(table)
    other = b"OTHER-ITEM!"
    first = 4 + 4 * 3
    return (struct.pack("<I", 2) + struct.pack("<III", first, first + len(table), first + len(table) + len(other))
            + bytes(table) + other)


def _u(text):
    return text.encode("utf-16-le")


BREAK = struct.pack("<4H", 0xFFF0, 0xFFFF, 4, 0)


def test_codec_text_line_break_and_tags():
    even = _u("Hello") + b"\0\0"[:0]                   # 5 units: the break needs a pad unit before it
    raw = even + struct.pack("<H", 0xFFFF) + BREAK + _u("World") + b"\0\0"
    assert decode(raw) == "Hello\nWorld"
    assert encode("Hello\nWorld", pad4=False) == raw
    raw = _u("Four") + BREAK + _u("x") + struct.pack("<2H", 0xFFF6, 0xFFFF) + struct.pack("<4H", 8, 0, 1, 0)
    assert decode(raw) == "Four\nx{c:fff6.ffff.0008.0000.0001.0000}"
    assert encode(decode(raw), pad4=False) == raw + b"\0\0"


def test_command_with_zero_units_keeps_its_zeros():
    raw = _u("A") + struct.pack("<H", 0xFFFF) + BREAK + b"\0\0\0\0"
    assert decode(raw) == "A\n"
    assert encode("A\n", pad4=True) == raw


def test_table_round_trip_growth_and_container():
    strings = [_u("Alpha") + b"\0\0", _u("Beta") + BREAK + _u("two") + b"\0\0"]
    for container in (False, True):
        data = _table(strings, container=container)
        f = L5Text(data)
        assert f.strings == ["Alpha", "Beta\ntwo"]
        assert f.build(f.strings) == data
        grown = L5Text(f.build(["Альфа і ще", "Beta\ntwo"]))
        assert grown.strings == ["Альфа і ще", "Beta\ntwo"]
        assert grown.build(grown.strings) == f.build(["Альфа і ще", "Beta\ntwo"])
        if container:
            assert f.build(["Альфа і ще", "Beta\ntwo"]).endswith(b"OTHER-ITEM!")


def test_not_a_table():
    with pytest.raises(l5text.FormatError):
        L5Text(b"\0" * 64)


def test_rules_load_and_save():
    data = _table([_u("Alpha") + b"\0\0", _u("Beta") + b"\0\0"])
    rules = GameRules()
    blocks, _ = rules.load_data_from_json_obj(data)
    assert blocks == [["Alpha", "Beta"]]
    assert rules.save_data_to_json_obj(blocks, {}) == data
    assert L5Text(rules.save_data_to_json_obj([["Альфа", "Beta"]], {})).strings == ["Альфа", "Beta"]


def test_ztex_reads_and_writes_a_picture():
    from core import texture_formats
    pixels = bytearray(8 * 8 * 4)                       # RGBA8, one 8x8 level
    head = bytearray(0x0C + 0x58)
    head[:4] = b"ztex"
    struct.pack_into("<HHI", head, 4, 1, 2, 0)
    head[0x0C:0x0C + 4] = b"logo"
    struct.pack_into("<IIIIHHBB", head, 0x0C + 0x40, 0, 0x80, 0, len(pixels), 8, 8, 1, 0x09)
    data = bytes(head) + bytes(0x80 - len(head)) + bytes(pixels)
    textures = texture_formats.read("ztex", data)
    assert textures[0].name == "logo" and textures[0].image.size == (8, 8) and textures[0].pixel_format == "RGBA8"
    image = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    written = texture_formats.write("ztex", data, {0: image})
    assert len(written) == len(data) and texture_formats.read("ztex", written)[0].image.getpixel((1, 1)) == (255, 0, 0, 255)


def test_l5_fnt_edit_changes_one_glyph():
    from core import font_formats
    count, w, h = 4, 4, 2
    codes = [10, 10, 0x41, 0x42]
    head = bytearray(b"FNT ") + struct.pack("<4H", w, h, count, 2 * count) + struct.pack(f"<{count}H", *codes)
    head += bytes(-len(head) % 4) + struct.pack("<I", count)
    table_at = len(head)
    head += bytes(4 * count)
    records = []
    for i in range(count):
        records.append(struct.pack("<II", 3, 4) + bytes([0x10 * i, 0x21 + i, 0x32, 0x43]))
    pos = len(head)
    for i, rec in enumerate(records):
        struct.pack_into("<I", head, table_at + 4 * i, pos - (table_at + 4 * i))
        pos += len(rec)
    data = bytes(head) + b"".join(records)
    meta, sheets = font_formats.extract("l5_fnt", data)
    assert font_formats.pack("l5_fnt", meta, sheets, data) == data
    g = font_formats.char_map(meta)["A"]
    sheets[0].putpixel(((g % 64) * w, (g // 64) * h), (255, 255, 255, 255))
    out = font_formats.pack("l5_fnt", meta, sheets, data)
    assert out != data and len(out) == len(data)


WS = Path(r"E:\Emulators\RomHacking\Fantasy Life")
SOURCE = WS / "source" / "romfs" / "_file_archive"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "fantasy_life"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_real_text_files_save_back_byte_for_byte():
    files = sorted(_need(SOURCE).glob("*.l5txt"))
    assert len(files) == 940
    strings = 0
    for path in files[::9]:
        raw = path.read_bytes()
        f = L5Text(raw)
        assert f.build(f.strings) == raw, path.name
        assert f.exact.count(False) <= 2
        strings += f.count
    assert strings > 5000


def test_real_fonts_and_pictures_round_trip():
    from core import font_formats, texture_formats
    fonts = sorted(_need(SOURCE).glob("*.fnt"))
    assert len(fonts) == 12
    for path in fonts:
        raw = path.read_bytes()
        meta, sheets = font_formats.extract("l5_fnt", raw)
        assert font_formats.pack("l5_fnt", meta, sheets, raw) == raw, path.name
    pictures = sorted(SOURCE.glob("*.ztex"))
    assert pictures
    for path in pictures:
        raw = path.read_bytes()
        textures = texture_formats.read("ztex", raw)
        assert texture_formats.write("ztex", raw, {i: t.image for i, t in enumerate(textures)}) == raw, path.name


def test_descriptors_are_valid_json():
    for name in ("font_sources.json", "texture_sources.json"):
        assert isinstance(json.loads((PLUGIN / name).read_text(encoding="utf-8")), list)
