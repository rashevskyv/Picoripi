"""Dragon Ball Fusions plugin: the jMSG and jFNT/jIMG formats on synthetic data and (skipped where the workspace is
not on this machine) the real game files."""
import romhacking_root
import json
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from plugins.dragon_ball_fusions import jmsg
from plugins.dragon_ball_fusions.rules import GameRules
from plugins.testing import check_loads, check_validator

PLUGIN_NAME = "dragon_ball_fusions"
WS = romhacking_root.under('Dragon Ball Fusions')
SOURCE = WS / "source" / "romfs" / "DOF.cpk"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN_NAME


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _jmsg(texts) -> bytes:
    start = 0x10 + (len(texts) + 1) * 8
    body, pairs = b"", struct.pack("<II", 0x202, 0)
    for i, text in enumerate(texts):
        pairs += struct.pack("<II", 100 + i * 7, start - 0x18 + len(body))
        body += text.encode("utf-16-le") + b"\0\0"
    raw = b"jMSG" + struct.pack("<III", 0, len(texts), 0x10) + pairs + body + bytes(4)
    return raw[:4] + struct.pack("<I", len(raw)) + raw[8:]


def test_the_plugin_loads_and_validates():
    check_loads(PLUGIN_NAME)
    check_validator(PLUGIN_NAME)


def test_jmsg_round_trips_and_grows():
    raw = _jmsg(["Hello!", "Two\nlines", ""])
    msg = jmsg.Jmsg(raw)
    assert msg.texts == ["Hello!", "Two\nlines", ""] and msg.keys == [100, 107, 114]
    assert msg.build(msg.texts) == raw
    edited = jmsg.Jmsg(msg.build(["Привіт, світе! ґєії", "Two\nlines", "x"]))
    assert edited.texts[0].startswith("Привіт") and edited.texts[2] == "x" and edited.keys == msg.keys
    assert struct.unpack_from("<I", edited.raw, 4)[0] == len(edited.raw)
    assert jmsg.Jmsg(edited.build(msg.texts)).texts == msg.texts


def test_plugin_load_and_save_round_trip():
    raw = _jmsg(["One", "Two"])
    rules = GameRules()
    blocks, _names = rules.load_data_from_json_obj(raw)
    assert blocks == [["One", "Two"]]
    assert rules.save_data_to_json_obj(blocks, {}) == raw
    assert jmsg.Jmsg(rules.save_data_to_json_obj([["One", "Dos?"]], {})).texts == ["One", "Dos?"]


def _jimg(width: int, height: int, fmt: int, body: bytes) -> bytes:
    head = b"jIMG" + struct.pack("<IHH", 0x80 + len(body), width, height) + bytes([fmt, 3, 4, 0x11])
    return head.ljust(0x80, b"\0") + body


def test_jimg_reads_writes_and_round_trips():
    raw = _jimg(16, 8, 5, bytes(16 * 8 * 2))      # RGBA4
    textures = texture_formats.read("jimg", raw)
    assert textures[0].image.size == (16, 8) and textures[0].pixel_format == "RGBA4"
    assert texture_formats.write("jimg", raw, {0: textures[0].image}) == raw
    marked = textures[0].image.copy()
    marked.paste((255, 0, 0, 255), (0, 0, 8, 8))
    assert texture_formats.write("jimg", raw, {0: marked}) != raw


def _jfnt() -> bytes:
    glyphs = 6
    ranges = [(0x21, 0x26, 0)]
    head = b"jFNT" + bytes(4) + b"\x00\x2c\x00\x01" + bytes([5, 5, 0, 0])      # cells 8 x 8
    head += struct.pack("<H", len(ranges)) + b"".join(struct.pack("<3H", *r) for r in ranges)
    head += struct.pack("<H", glyphs) + bytes(glyphs * 4)
    head = head.ljust(0x80, b"\0")
    atlas = _jimg(32, 16, 0x10, bytes(32 * 16))
    raw = head + atlas
    return raw[:4] + struct.pack("<I", len(raw)) + raw[8:]


def test_jfnt_atlas_font_round_trips_and_edits():
    raw = _jfnt()
    meta, sheets = font_formats.extract("asw_jfnt", raw)
    assert set(font_formats.char_map(meta)) == set("!\"#$%&")
    assert font_formats.pack("asw_jfnt", meta, sheets, raw) == raw
    sheet = sheets[0].copy()
    sheet.paste(Image.new("RGBA", (6, 6), (255, 255, 255, 255)), (0, 0))
    out = font_formats.pack("asw_jfnt", meta, [sheet], raw)
    assert out != raw and len(out) == len(raw)
    assert font_formats.extract("asw_jfnt", out)[1][0].tobytes() != sheets[0].tobytes()


def test_real_message_file_round_trips():
    raw = _need(SOURCE / "message" / "msg_en.jmsg").read_bytes()
    msg = jmsg.Jmsg(raw)
    assert msg.count == 18683 and msg.build(msg.texts) == raw
    texts = list(msg.texts)
    texts[5] += "!"
    assert jmsg.Jmsg(jmsg.Jmsg(msg.build(texts)).build(msg.texts)).raw == raw


def test_real_fonts_and_pictures():
    _need(SOURCE)
    for source in json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8")):
        data = (WS / "source" / source["path"]).read_bytes()
        meta, sheets = font_formats.extract("asw_jfnt", data)
        assert font_formats.pack("asw_jfnt", meta, sheets, data) == data, source["path"]
    files = sorted(SOURCE.rglob("*.jtex"))
    assert len(files) > 2000
    for path in files[::120]:
        data = path.read_bytes()
        textures = texture_formats.read("jimg", data)
        assert texture_formats.write("jimg", data, {0: textures[0].image}) == data, path.name
