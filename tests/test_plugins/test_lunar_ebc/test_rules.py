"""Lunar 2: Eternal Blue Complete plugin: codec, script blocks, tables, names, font and pictures.

The real-data tests read the workspace's ``source`` folder (1_unpack.bat) and the three USA discs, and
skip when they are missing.
"""
import json
import struct
import sys
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from plugins.lunar_ebc import codec, doc, es
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "lunar_ebc"
WORKSPACE = Path(r"E:\Emulators\RomHacking\Lunar\Eternal Blue")
SOURCE = WORKSPACE / "source"
SHARED = WORKSPACE.parent.parent / "_shared" / "scripts"
needs_data = pytest.mark.skipif(not (SOURCE / "DATA" / "EVENT").is_dir(), reason="Lunar 2 not unpacked here")
needs_discs = pytest.mark.skipif(not (WORKSPACE / "image").is_dir() or not (SHARED / "zt" / "lunar2.py").is_file(),
                                 reason="Lunar 2 discs or the workspace scripts are not here")


def _message(text: str) -> bytes:
    body = codec.pack(codec.Encoder().encode(text))
    return struct.pack("<H", len(body) + 2) + body


def sample_script(after: bytes = b"\x00\x00\x00\x00\x08\x00\x00\x00DATADATA") -> bytes:
    """An ES block: code (show message 1, show message 0, return), two messages; then 'voice' data."""
    first, second = _message("{B2C9}Hello, Hiro.\nWhere is Lucia?{3007}"), _message("Bye!")
    code = struct.pack("<3I", 0x1D << 24 | len(first), 0x1D << 24, 0x01 << 24)
    text = first + second
    text_off = 0x20 + len(code)
    size = (text_off + len(text) + 3) & ~3
    head = b"ES\x00\x01" + struct.pack("<7I", size, len(code), 0x20, 0, text_off, len(text), text_off)
    block = head + code + text
    return block + bytes(size - len(block)) + after


def sample_people() -> bytes:
    script = sample_script()
    a = b"PART" * 2
    es_at, d_at = 0x18 + len(a), 0x18 + len(a) + len(script)
    part_d = b"SPRITES!"
    total = d_at + len(part_d)
    return struct.pack("<6I", total, 3, 0x18, es_at, 0, d_at) + a + script + part_d


def sample_table() -> bytes:
    enc = codec.Encoder()
    return b"".join(codec.pack(enc.encode(t)) + b"\xff\xff" for t in ("Herb", "Recovers a bit of HP", "{06FF}"))


def test_the_plugin_loads_and_validates():
    check_loads(PLUGIN)
    check_validator(PLUGIN)


def test_the_codec_reads_lines_units_and_both_line_ends():
    units = codec.Encoder().encode("Herb\nNut{3007}")
    assert units[:3] == [0x0629, 0x4653, 0x43FF]                 # odd: the last unit ends with 0xFF
    assert units[3:] == [codec.NEWLINE, 0x062F, 0x56D5, 0x3007]  # even: the last character carries bit 7
    assert codec.decode(units) == "Herb\nNut{3007}"
    assert codec.decode(codec.Encoder().encode("a\u201cb\u201d_c")) == "a\u201cb\u201d_c"
    enc = codec.Encoder()
    enc.encode("Привіт")
    assert enc.missing == set("Привіт")


def test_a_script_survives_load_and_save_and_grows():
    data = sample_script()
    check_round_trip(PLUGIN, data)
    blocks, _ = doc.read(data)
    assert blocks == [["{B2C9}Hello, Hiro.\nWhere is Lucia?{3007}", "Bye!"]]
    assert doc.write(data, blocks, set()) == data
    blocks[0][0] = "{B2C9}A much longer greeting than before,\nHiro, and a second line too.{3007}"
    out = doc.write(data, blocks, set())
    assert doc.read(out)[0] == blocks
    block = es.parse(out)
    shows = [struct.unpack_from("<I", out, at)[0] & 0xFFFFFF for at in es.shows(out, block)]
    assert shows == [block.messages[1][0], 0]                     # the second message moved, the code follows it
    assert out.endswith(b"DATADATA") and out[block.size:block.size + 4] == bytes(4)


def test_people_files_move_the_part_after_the_script():
    data = sample_people()
    blocks, _ = doc.read(data)
    assert doc.write(data, blocks, set()) == data
    blocks[0][1] = "Goodbye, goodbye, and goodbye again!"
    out = doc.write(data, blocks, set())
    total, _people, _a, es_at, _c, d_at = struct.unpack_from("<6I", out, 0)
    assert total == len(out) and out[d_at:] == b"SPRITES!" and doc.read(out)[0] == blocks


def test_tables_and_fixed_names():
    data = sample_table()
    blocks, _ = doc.read(data)
    assert blocks == [["Herb", "Recovers a bit of HP", "{06FF}"]]
    blocks[0][0] = "Healing Herb"
    out = doc.write(data, blocks, set())
    assert doc.read(out)[0] == blocks and len(out) > len(data)
    with pytest.raises(doc.TooLong):
        doc._fixed_units("A name far too long for its field", codec.Encoder().encode("Slime" + "_" * 16),
                         codec.Encoder(), "Monster name")


def test_the_font_with_a_width_table_packs_back():
    glyphs = bytes(range(60)) + bytes(30)
    data = glyphs + bytes([0x42, 0x69])                           # widths: space 4, glyph 0 = 2, glyph 1 = 6
    params = {"offset": 0, "count": 3, "rows": 15, "row_order": "little", "widths_offset": 90, "widths_first": 1,
              "chars": "!\"#"}
    metadata, sheets = font_formats.extract("lunar", data, params)
    assert [p["width"] for p in metadata["WID1"][0]["packets"]] == [2, 6, 9]
    assert font_formats.pack("lunar", metadata, sheets, data, params) == data
    metadata["WID1"][0]["packets"][0]["width"] = 7
    assert font_formats.pack("lunar", metadata, sheets, data, params)[90] == 0x47


# ---------------------------------------------------------------- real data

@needs_data
def test_every_text_file_rebuilds_byte_for_byte_and_takes_edits():
    rules = load_rules(PLUGIN)
    total = files = 0
    for path in sorted((SOURCE / "DATA").rglob("*.bin")):
        data = path.read_bytes()
        try:
            kind = doc.kind(data)
        except ValueError:
            continue
        files += 1
        blocks, names = rules.load_data_from_json_obj(data)
        total += sum(map(len, blocks))
        assert rules.save_data_to_json_obj(blocks, names) == data, path.name
        if kind in ("script", "table") and path.stat().st_size < 0x8000:
            edited = [[s + " UA TEST" if s and i % 2 == 0 else s for i, s in enumerate(b)] for b in blocks]
            assert doc.read(doc.write(data, edited, set()))[0] == edited, path.name
    assert files == 969 and total == 11043


@needs_data
def test_the_game_font_and_pictures_round_trip():
    plugin = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN
    for source in json.loads((plugin / "font_sources.json").read_text(encoding="utf-8")):
        data = (SOURCE / source["path"]).read_bytes()
        metadata, sheets = font_formats.extract(source["format"], data, source["params"])
        assert font_formats.pack(source["format"], metadata, sheets, data, source["params"]) == data
    pictures = sorted((SOURCE / "DATA").rglob("*.tim"))
    assert len(pictures) == 55
    for path in pictures:
        data = path.read_bytes()
        textures = texture_formats.read("tim", data)
        assert texture_formats.write("tim", data, {i: t.image for i, t in enumerate(textures)}) == data, path.name


@needs_discs
def test_the_source_files_are_those_of_all_three_discs():
    sys.path.insert(0, str(SHARED))
    from zt import lunar2  # the workspace scripts: _shared\scripts\zt\lunar2.py
    cue = WORKSPACE / "image" / (lunar2.DISC_NAME.format(n=1) + ".cue")
    expected = None
    for n in (1, 2, 3):
        exe, idx, pak = lunar2._read_disc(cue.with_name(cue.name.replace("(Disc 1)", f"(Disc {n})")))
        files = lunar2.source_files(exe, idx, pak)
        if expected is None:
            expected = files
            for rel, data in files.items():
                assert (SOURCE / rel).read_bytes() == data, rel
        assert files == expected, f"disc {n}"
        entries = lunar2.parse_idx(idx)
        for number in lunar2.SECTIONED:                          # unchanged sections join back byte for byte
            member = lunar2.member(pak, entries[number])
            assert lunar2.rebuild_sectioned(member, lunar2.SECTIONED[number][1], {})[:len(member)] == member
