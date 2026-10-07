"""Policenauts plugin: dialogue (PNV voice-chunk headers), codec tags, the proportional fonts, the PAK pictures.

The real-data tests read the workspace's ``source`` folder (1_unpack.bat) and skip when it is missing.
"""
import json
import struct
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats, texture_formats
from core.texture_formats import policenauts_pak
from plugins.policenauts import codec, doc, voice
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "policenauts"
SOURCE = Path(r"E:\Emulators\RomHacking\Policenauts\source")
needs_data = pytest.mark.skipif(not (SOURCE / "PN_VOX1.PNV").is_file(), reason="Policenauts not unpacked here")


def _records(texts):
    out = b""
    for i, text in enumerate(texts):
        size = 16 + ((len(text) + 4) & ~3)
        out += struct.pack("<4I", 0 if i == len(texts) - 1 else size, 10 * i, 30, 0) + text
        out += bytes(size - 16 - len(text))
    return out


def sample_chunk(size=0x800) -> bytes:
    """A voice chunk header with two clips: ("  ", "Hello, Jonathan.") and ("CO\\x80#2 \\xd0\\x06 ok",)."""
    first = _records([b"  ", b"Hello, Jonathan.\nHi."])
    second = _records([b"CO\x80#2 \xd0\x06 ok"])
    start = 0x70
    head = bytearray(size)
    head[0:4] = b'"jXS'
    struct.pack_into("<III", head, 4, size, 0x10000, 0xFFFFFFFF)
    struct.pack_into("<4I", head, 0x20, 2, 0x70, start, 0)
    struct.pack_into("<8I", head, 0x30, size, 0x800, 0, 0x70, 6, 0, start, 0)
    struct.pack_into("<8I", head, 0x50, size + 0x800, 0x800, 0, 0x70, 6, 0, start + len(first), 0)
    head[start:start + len(first) + len(second)] = first + second
    return bytes(head)


def sample_pnv() -> bytes:
    chunks = [sample_chunk(), sample_chunk(0x1000)]
    return (b"PNVX" + struct.pack("<III", 2, 100, 0) + struct.pack("<IIII", 0, 0x800, 40, 0x1000)
            + b"".join(chunks))


def test_the_plugin_loads_and_validates():
    check_loads(PLUGIN)
    check_validator(PLUGIN)


def test_dialogue_survives_load_and_save():
    check_round_trip(PLUGIN, sample_pnv())
    blocks, names = doc.read(sample_pnv())
    assert blocks[0] == ["Hello, Jonathan.\nHi.", "CO{x80}#2 {dash} ok"]
    assert names["1"] == "Voice chunk 40"


def test_an_edit_relays_the_clips_and_a_too_long_text_is_refused():
    data = sample_pnv()
    blocks, _names = doc.read(data)
    blocks[0][0] = "Longer line, UA TEST, and more words."
    out = doc.write(data, blocks, set())
    again, _ = doc.read(out)
    assert again[0] == blocks[0] and again[1] == doc.read(data)[0][1]
    chunk = voice.parse(out)[0]
    assert chunk.clips[1][0].text == b"CO\x80#2 \xd0\x06 ok"
    assert out[16 + 16 + 0x800:] == data[16 + 16 + 0x800:]          # the second chunk keeps its bytes
    blocks[0][0] = "x" * 2000
    with pytest.raises(voice.VoiceError):
        doc.write(data, blocks, set())


def test_a_chunk_whose_text_runs_past_its_header_is_read_cut_and_kept():
    head = bytearray(sample_chunk())
    struct.pack_into("<I", head, 0x30 + 0x18, 0x7F0)            # the first clip's text starts at the end
    head[0x7F0:0x800] = struct.pack("<4I", 0x30, 0, 0, 0)
    chunk = voice.parse_chunk(0, bytes(head))
    assert chunk.cut and chunk.clips[1] == []


def test_codec_tags_and_missing_characters():
    assert codec.decode(b"a\nb\xd0\x06c\x80\xb1") == "a\nb{dash}c{x80}\uff71"
    missing = set()
    assert codec.encode("a\nb{dash}c{x80}\uff71", missing) == b"a\nb\xd0\x06c\x80\xb1" and not missing
    assert codec.encode("Привіт", missing) == b"??????" and missing == set("Привіт")


def _font() -> bytes:
    widths = [3, 5]
    table = b"".join(bytes([w]) + (3 * sum(widths[:i])).to_bytes(3, "big") for i, w in enumerate(widths))
    start = 8 + len(table)
    pixels = bytes(range(3 * sum(widths)))
    return struct.pack(">II", start, start + len(pixels) + 6) + table + pixels + bytes(6) + b"KANJI"


def test_the_proportional_font_packs_back_and_takes_edits():
    data = _font()
    metadata, sheets = font_formats.extract("policenauts", data)
    assert font_formats.pack("policenauts", metadata, sheets, data) == data
    assert [p["width"] for p in metadata["WID1"][0]["packets"]] == [3, 5]
    ImageDraw.Draw(sheets[0]).rectangle((16, 0, 20, 11), fill=(255, 255, 255, 255))
    metadata["WID1"][0]["packets"][0]["width"] = 2
    out = font_formats.pack("policenauts", metadata, sheets, data)
    assert out[8] == 2 and out[13:16] == (6).to_bytes(3, "big")         # the second glyph moved up
    assert out[16 + 6:16 + 21] == b"\xff" * 15 and out.endswith(b"KANJI")
    metadata["WID1"][0]["packets"][0]["width"] = 9
    with pytest.raises(ValueError):
        font_formats.pack("policenauts", metadata, sheets, data)


def _picture(mode: int, width: int, height: int, rows: bytes, palette=()) -> bytes:
    head = struct.pack(">4H", 0x8000, (height - 1) << 6 | mode, 0, 0x1000 | (width - 1))
    return head + struct.pack(">32H", *(list(palette) + [0] * (32 - len(palette)))) + rows


def _pack(items):
    offsets, pos = [], 0
    for item in items:
        offsets.append(pos)
        pos += len(item)
    return struct.pack(f">I{len(items)}I", len(items), *offsets) + b"".join(items)


def test_pak_pictures_read_write_and_reencode():
    direct = _picture(0x16, 4, 2, bytes.fromhex("0000c17fff817c00") + bytes.fromhex("0000c27fff00ffff"))
    nibble = _picture(0x03, 6, 3, bytes.fromhex("00c1142231000000") + bytes.fromhex("0000000000000000"),
                      palette=(0, 0x7FFF, 0x001F, 0x03E0))
    data = _pack([b"\x01\x01\x02\x0b\xb8\x00\xff\x00", direct, nibble])
    textures = texture_formats.read("policenauts_pak", data)
    assert [t.name for t in textures] == ["001", "002"]
    assert textures[0].image.getpixel((0, 0)) == (255, 255, 255, 255)
    assert textures[0].image.getpixel((2, 0)) == (0, 0, 0, 0) and textures[0].image.getpixel((0, 1))[3] == 255
    assert textures[1].image.getpixel((0, 0)) == (255, 255, 255, 255)
    assert textures[1].image.getpixel((2, 0)) == (255, 0, 0, 255) and textures[1].image.getpixel((5, 2))[3] == 0
    assert texture_formats.write("policenauts_pak", data, {i: t.image for i, t in enumerate(textures)}) == data
    image = textures[1].image.copy()
    image.putpixel((5, 2), (0, 250, 0, 255))
    out = texture_formats.write("policenauts_pak", data, {1: image})
    again = texture_formats.read("policenauts_pak", out)
    assert again[1].image.getpixel((5, 2)) == (0, 255, 0, 255)
    assert list(again[0].image.getdata()) == list(textures[0].image.getdata())


# ---------------------------------------------------------------- real data

@needs_data
def test_both_dialogue_files_rebuild_byte_for_byte_and_take_edits():
    rules = load_rules(PLUGIN)
    total = 0
    for name in ("PN_VOX1.PNV", "PN_VOX2.PNV"):
        data = (SOURCE / name).read_bytes()
        blocks, names = rules.load_data_from_json_obj(data)
        total += sum(map(len, blocks))
        assert rules.save_data_to_json_obj(blocks, names) == data, name
        assert all(c.cut or voice.build_chunk(c) == c.header for c in voice.parse(data))
        edited = [["UA TEST"] + block[1:] for block in blocks]
        assert doc.read(doc.write(data, edited, set()))[0] == edited
    assert total == 5190


@needs_data
def test_every_font_round_trips():
    fonts = json.loads((Path(__file__).parents[3] / "plugins" / PLUGIN / "font_sources.json").read_text("utf-8"))
    assert len(fonts) == 6
    for font in fonts:
        data = (SOURCE / font["path"]).read_bytes()
        metadata, sheets = font_formats.extract("policenauts", data)
        assert font_formats.pack("policenauts", metadata, sheets, data) == data, font["path"]


@needs_data
def test_listed_pictures_round_trip_and_reencode():
    listed = json.loads((Path(__file__).parents[3] / "plugins" / PLUGIN / "texture_sources.json").read_text("utf-8"))
    count = 0
    for entry in listed:
        data = (SOURCE / entry["path"]).read_bytes()
        textures = texture_formats.read(entry["format"], data)
        assert texture_formats.write(entry["format"], data, {i: t.image for i, t in enumerate(textures)}) == data
        if entry["format"] != "policenauts_pak":
            continue
        items = policenauts_pak._items(data)
        for number in policenauts_pak._pictures(items):
            width, height, values = policenauts_pak.decode(items[number])
            assert policenauts_pak.decode(policenauts_pak.encode(items[number], values))[2] == values
            count += 1
    assert count >= 50
