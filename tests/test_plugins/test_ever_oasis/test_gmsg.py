"""Ever Oasis GMSG v3: control-code grammar on synthetic messages, then the real English file (skipped when the
workspace is not on this machine)."""
import romhacking_root
import json
import struct
from pathlib import Path

import pytest

from plugins.ever_oasis import gmsg
from plugins.ever_oasis.gmsg import Gmsg, decode, encode


def _file(messages):
    """A tiny GMSG v3: header, no style rows, table at 0x40."""
    table = 0x40
    head = bytearray(table)
    gmsg.HEADER.pack_into(head, 0, b"GMSG", 3, 0x10, len(messages), table, 16)
    body, records = bytearray(), bytearray()
    start = table + 16 * len(messages)
    for i, raw in enumerate(messages):
        body += bytes(-len(body) % 4)
        records += struct.pack("<4I", 0x100 + i, 0x26, start + len(body), len(raw))
        body += raw
    return bytes(head + records + body)


def test_plain_text_and_end_code():
    raw = encode("Hello")
    assert raw == b"Hello" + b"\x7f\x00\x00" and decode(raw) == "Hello"


def test_pad_byte_when_the_code_sits_at_an_odd_offset():
    # "Hi": 7f at offset 2, the code would start at 3 -> a pad byte; the end code at offset 8 -> pad again
    assert encode("Hi\nYo") == b"Hi" + bytes([0x7F, 0, 1, 0]) + b"Yo" + bytes([0x7F, 0, 0, 0])
    # "A": 7f at offset 1, the code starts at 2: no pad
    assert encode("A\nB") == b"A" + bytes([0x7F, 1, 0]) + b"B" + bytes([0x7F, 0, 0])
    assert decode(encode("Abc\nd")) == "Abc\nd"


def test_four_byte_arguments_are_aligned():
    text = "You get {style:02000000}Seeds{style:ffffffff}!{wait}"
    raw = encode(text)
    assert decode(raw) == text
    assert struct.unpack_from("<I", raw, raw.index(b"\x19\x00") + 2 + (-(raw.index(b"\x19\x00") + 2) % 4))[0] == 2


def test_gender_and_plural_strings():
    text = "Thanks, {c15:guy}{c16:gal}! {c14:00000000|Travelers|Traveler|Travelers}{wait}"
    assert decode(encode(text)) == text


def test_unknown_layout_stays_raw():
    odd = b"abc\x01\x02def"                      # control bytes in text: not the grammar
    assert decode(odd) == "{raw:" + odd.hex() + "}"
    assert encode(decode(odd)) == odd


def test_file_round_trip_and_growth():
    messages = [encode("One"), b"", encode("Two{wait}"), encode("T{c05:00000000}x")]
    data = _file(messages)
    g = Gmsg(data)
    assert g.texts() == ["One", "", "Two{wait}", "T{c05:00000000}x"]
    assert g.build(g.texts()) == data
    grown = g.build(["One и ще", "", "Two{wait}", "T{c05:00000000}x"])
    again = Gmsg(grown)
    assert again.texts()[0] == "One и ще" and again.texts()[2:] == g.texts()[2:]
    assert again.ids == g.ids and again.flags == g.flags
    assert again.build(again.texts()) == grown


def test_refuses_other_versions():
    data = bytearray(_file([encode("x")]))
    data[4] = 1
    with pytest.raises(gmsg.FormatError):
        Gmsg(bytes(data))


WS = romhacking_root.under('Ever Oasis')
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "ever_oasis"


def _need(path):
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_real_main_gmsg_saves_back_byte_for_byte():
    raw = _need(SOURCE / "romfs/data/Region_EU/English/main.gmsg").read_bytes()
    g = Gmsg(raw)
    texts = g.texts()
    assert len(texts) == 8515
    assert not any(t.startswith("{raw:") for t in texts)
    assert g.build(texts) == raw
    texts[300] += " ЇєҐ"                         # a longer text moves the others, ids and flags stay
    again = Gmsg(g.build(texts))
    assert again.ids == g.ids and again.flags == g.flags and again.texts()[301] == g.texts()[301]


def test_real_font_and_pictures_open_and_write_back():
    from core import font_formats, texture_formats
    font = _need(SOURCE / "romfs/data/Region_EU/main.gzf").read_bytes()
    metadata, sheets = font_formats.extract("gzf", font)
    assert font_formats.pack("gzf", metadata, sheets, font) == font
    chars = font_formats.char_map(metadata)
    assert "Ж" in chars and "Ґ" not in chars
    found = sorted(_need(SOURCE / "romfs/data/Region_EU/English").rglob("*.ctxb"))
    assert len(found) == 666
    for path in found[::37]:
        data = path.read_bytes()
        textures = texture_formats.read("ctxb", data)
        assert texture_formats.write("ctxb", data, {i: t.image for i, t in enumerate(textures)}) == data, path.name


def test_descriptors_are_valid_json():
    for name in ("font_sources.json", "texture_sources.json"):
        assert isinstance(json.loads((PLUGIN / name).read_text(encoding="utf-8")), list)
