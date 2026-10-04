"""Font formats of core/font_formats: synthetic files round-trip byte-exact, edits land where they belong."""
import struct

import pytest
from PIL import Image, ImageDraw

from core import font_formats
from core.containers import yaz0
from core.font_formats import bffnt, sources
from plugins.common.n64_rom import N64Rom, compute_crc


def _cell(metadata, glyph):
    gly = metadata["GLY1"][0]
    per_sheet = gly["glyph_horizontal_count"] * gly["glyph_vertical_count"]
    sheet, cell = divmod(glyph - gly["start_glyph"], per_sheet)
    x = (cell % gly["glyph_horizontal_count"]) * gly["cell_width"]
    y = (cell // gly["glyph_horizontal_count"]) * gly["cell_height"]
    return sheet, (x, y, x + gly["cell_width"], y + gly["cell_height"])


def _paint(sheets, metadata, glyph):
    sheet, (x, y, _x2, _y2) = _cell(metadata, glyph)
    ImageDraw.Draw(sheets[sheet]).rectangle((x + 1, y + 1, x + 4, y + 6), fill=(255, 255, 255, 255))
    return sheet, (x + 1, y + 1, x + 5, y + 7)


# -- characters and width maps ------------------------------------------------------------------


def test_char_codes_round_trip_cp1252_and_unicode():
    for char in ("A", "…", "é", "Ж", "€", "\x81"):
        assert font_formats.code_char(font_formats.char_code(char)) == char


def test_font_map_adds_translated_characters():
    metadata = {"INF1": [{"width": 5}], "MAP1": [font_formats.map_entries([(0x41, 0), (0xC6, 1)])],
                "WID1": [{"first_code_included": 0, "packets": [{"kerning": 0, "width": 9},
                                                                 {"kerning": 0, "width": 12}]}]}
    widths = font_formats.font_map(metadata, {"Ж": "Æ", "#g3": "x"})
    assert widths["A"] == {"width": 9}
    assert widths["Ж"] == {"width": 12} == widths["Æ"]
    assert "#g3" not in widths


def test_detect_by_magic():
    assert font_formats.detect(b"FONTbfn1" + bytes(8)) == "bfn"
    assert font_formats.detect(b"FFNT\xff\xfe\x14\x00") == "bffnt"
    assert font_formats.detect(b"GT1G0600") == "g1t"
    assert font_formats.detect(b"\x80\x37\x12\x40") is None


# -- G1T --------------------------------------------------------------------------------------

G1T_PARAMS = dict(cell_width=16, cell_height=16, columns=4, first_cell=4, first_code=0x41, last_code=0x44,
                  spacing=2, ink_threshold=64)


def _g1t(image):
    w, h = image.size
    texture = image.tobytes("bcn", 3)
    entry = bytes([0x10, 0x5B, (w.bit_length() - 1) | (h.bit_length() - 1) << 4, 0, 0, 0, 0, 0])
    header = b"GT1G0600" + struct.pack("<IIIII", 0, 0x20, 1, 0x10, 0) + bytes(4) + struct.pack("<I", 4)
    data = bytearray(header + entry + texture)
    struct.pack_into("<I", data, 8, len(data))
    return bytes(data)


def _letters_atlas():
    image = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    for index in range(4):            # cells 4..7 = A..D, ink 3 + index px wide at x=2
        x, y = (4 + index) % 4 * 16, (4 + index) // 4 * 16
        draw.rectangle((x + 2, y + 3, x + 4 + index, y + 12), fill=(255, 255, 255, 255))
    return image


def test_g1t_round_trip_and_block_only_edit():
    data = _g1t(_letters_atlas())
    metadata, sheets = font_formats.extract("g1t", data, G1T_PARAMS)
    chars = font_formats.char_map(metadata)
    assert [chars[c] for c in "ABCD"] == [4, 5, 6, 7]
    packets = metadata["WID1"][0]["packets"]
    assert [packets[g]["width"] for g in (4, 5, 6, 7)] == [5, 6, 7, 8]          # ink + spacing
    assert font_formats.pack("g1t", metadata, sheets, data, G1T_PARAMS) == data

    ImageDraw.Draw(sheets[0]).rectangle((1, 1, 3, 3), fill=(255, 255, 255, 255))    # cell 0, block (0, 0)
    edited = font_formats.pack("g1t", metadata, sheets, data, G1T_PARAMS)
    changed = [i for i in range(len(data)) if data[i] != edited[i]]
    texture_start = len(data) - 64 * 64
    assert changed and all(texture_start <= i < texture_start + 16 for i in changed)
    _again, again = font_formats.extract("g1t", edited, G1T_PARAMS)
    assert again[0].getchannel("A").crop((1, 1, 4, 4)).getextrema() == (255, 255)


# -- Zelda 64 ROM -----------------------------------------------------------------------------

N64_PARAMS = dict(rom_id="TEST", rom_version=0, font_file=2, glyph_count=40, first_code="0x20",
                  widths_file=3, widths_offset="0x10", widths_count=40, extra_chars={"0x46": "ÀÉ"})


def _n64_rom():
    rom = bytearray(0x200000)
    rom[0:4] = b"\x80\x37\x12\x40"
    rom[0x3B:0x40] = b"TEST\x00"
    font = bytes(((i * 7) & 0xFF) for i in range(40 * 128))
    code = bytes(0x10) + struct.pack(">40f", *[float(4 + i % 9) for i in range(40)]) + bytes(64)
    stored = yaz0.compress(code)
    font_at, code_at = 0x2000, 0x10000
    rom[font_at:font_at + len(font)] = font
    rom[code_at:code_at + len(stored)] = stored
    entries = [(0, 0x1060, 0, 0), (0x1060, 0x10B0, 0x1060, 0),
               (font_at, font_at + len(font), font_at, 0),
               (0x20000, 0x20000 + len(code), code_at, code_at + len(stored))]
    for index, entry in enumerate(entries):
        struct.pack_into(">IIII", rom, 0x1060 + index * 16, *entry)
    struct.pack_into(">II", rom, 0x10, *compute_crc(bytes(rom)))
    return bytes(rom)


def test_n64_round_trip_edit_and_crc():
    data = _n64_rom()
    metadata, sheets = font_formats.extract("n64", data, N64_PARAMS)
    chars = font_formats.char_map(metadata)
    assert chars["A"] == 0x21 and chars["À"] == 0x26 and chars["É"] == 0x27
    assert metadata["WID1"][0]["packets"][0]["width"] == 4
    assert font_formats.pack("n64", metadata, sheets, data, N64_PARAMS) == data

    _sheet, box = _paint(sheets, metadata, chars["A"])
    metadata["WID1"][0]["packets"][chars["A"]]["width"] = 13
    edited = font_formats.pack("n64", metadata, sheets, data, N64_PARAMS)
    assert struct.unpack_from(">II", edited, 0x10) == compute_crc(edited)
    again, again_sheets = font_formats.extract("n64", edited, N64_PARAMS)
    assert again["WID1"][0]["packets"][chars["A"]]["width"] == 13
    assert again_sheets[0].crop(box).getchannel("A").getextrema() == (255, 255)
    assert again["WID1"][0]["packets"][1] == metadata["WID1"][0]["packets"][1]


def test_n64_refuses_another_rom():
    with pytest.raises(ValueError, match="described for ROM"):
        font_formats.extract("n64", _n64_rom(), dict(N64_PARAMS, rom_id="CZLE"))


def test_carry_over_puts_the_edited_font_into_a_rebuilt_rom():
    original = _n64_rom()
    metadata, sheets = font_formats.extract("n64", original, N64_PARAMS)
    _paint(sheets, metadata, 5)
    metadata["WID1"][0]["packets"][5]["width"] = 15
    edited = font_formats.pack("n64", metadata, sheets, original, N64_PARAMS)

    assert font_formats.carry_over("n64", original, original, N64_PARAMS) == original
    rebuilt = font_formats.carry_over("n64", edited, original, N64_PARAMS)   # a text save rebuilt from the source
    font = font_formats.extract("n64", rebuilt, N64_PARAMS)
    assert font[0]["WID1"] == metadata["WID1"]
    assert N64Rom(rebuilt).read_file(2) == N64Rom(edited).read_file(2)


# -- BFFNT (Switch) ---------------------------------------------------------------------------


def _bffnt(ink: Image.Image, cell=7):
    """A minimal NX BFFNT: one 32x32 BC4 sheet of 4x4 cells (cell + 1 px apart), 3 glyphs A B C."""
    w, h = ink.size
    linear = Image.merge("RGBA", (ink, ink, ink, ink.transpose(Image.Transpose.FLIP_TOP_BOTTOM)))
    linear_bc4 = linear.tobytes("bcn", 3)
    blocks = [linear_bc4[i * 16:i * 16 + 8] for i in range(len(linear_bc4) // 16)]
    addresses = bffnt._block_addresses(w // 4, h // 4, 8, 1)
    texture = bytearray(max(addresses) + 8)
    for address, block in zip(addresses, blocks):
        texture[address:address + 8] = block

    bntx = bytearray(0x200)
    bntx[0:4] = b"BNTX"
    bntx[0x20:0x24] = b"NX  "
    struct.pack_into("<IQ", bntx, 0x24, 1, 0x40)
    struct.pack_into("<Q", bntx, 0x40, 0x80)              # -> BRTI
    bntx[0x80:0x84] = b"BRTI"
    struct.pack_into("<I", bntx, 0x80 + 0x1C, 0x1D01)
    struct.pack_into("<iiiii", bntx, 0x80 + 0x24, w, h, 1, 1, 0)
    struct.pack_into("<I", bntx, 0x80 + 0x50, len(texture))
    struct.pack_into("<Q", bntx, 0x80 + 0x70, 0x180)       # -> mip table
    struct.pack_into("<Q", bntx, 0x180, 0x200)             # -> mip 0
    bntx += texture

    tglp_at, sheet_at = 0x34, 0x100
    cwdh_at = sheet_at + len(bntx)
    cwdh = b"CWDH" + struct.pack("<IHHI", 16 + 9, 0, 2, 0) + bytes([1, 6, 7, 0xFF, 5, 6, 0, 4, 5])
    cwdh += bytes(-len(cwdh) % 4)
    cmap_at = cwdh_at + len(cwdh)
    cmap = b"CMAP" + struct.pack("<IIIHHIH", 28, 0x41, 0x43, 0, 0, 0, 0) + bytes(2)
    out = bytearray(b"FFNT\xff\xfe" + struct.pack("<HIIHH", 0x14, 0x04010000, 0, 4, 0))
    out += b"FINF" + struct.pack("<IBBBBHHbBBBIII", 0x20, 1, 8, 7, 6, 8, 0, 0, 7, 7, 1, tglp_at + 8,
                                 cwdh_at + 8, cmap_at + 8)
    out += b"TGLP" + struct.pack("<IBBBBIHHHHHHI", sheet_at - tglp_at, cell, cell, 1, 7, len(bntx), 6, 0x0C,
                                 4, 4, w, h, sheet_at)
    out += bytes(sheet_at - len(out))
    out += bntx + cwdh + cmap
    struct.pack_into("<I", out, 0x0C, len(out))
    return bytes(out)


def _ink_with_a():
    ink = Image.new("L", (32, 32), 0)
    ImageDraw.Draw(ink).rectangle((1, 1, 5, 6), fill=255)       # glyph 0 (top-left, upright)
    return ink


def test_bffnt_round_trip_widths_and_orientation():
    data = _bffnt(_ink_with_a())
    metadata, sheets = font_formats.extract("bffnt", data, {})
    assert metadata["GLY1"][0]["cell_width"] == 8                      # cell + 1 px gutter
    assert font_formats.char_map(metadata) == {"A": 0, "B": 1, "C": 2}
    packets = metadata["WID1"][0]["packets"]
    assert packets[0] == {"kerning": -1, "width": 7} and packets[1] == {"kerning": 1, "width": 6}
    assert sheets[0].getchannel("A").crop((1, 1, 6, 7)).getextrema() == (255, 255)   # upright, at the top
    assert font_formats.pack("bffnt", metadata, sheets, data, {}) == data

    packets[1]["width"] = 9
    ImageDraw.Draw(sheets[0]).rectangle((9, 1, 12, 4), fill=(255, 255, 255, 255))   # glyph 1
    edited = font_formats.pack("bffnt", metadata, sheets, data, {})
    again, again_sheets = font_formats.extract("bffnt", edited, {})
    assert again["WID1"][0]["packets"][1]["width"] == 9
    assert again_sheets[0].getchannel("A").crop((9, 1, 13, 5)).getextrema() == (255, 255)
    assert again_sheets[0].crop((0, 0, 8, 8)).tobytes() == sheets[0].crop((0, 0, 8, 8)).tobytes()


def test_bffnt_refuses_big_endian():
    with pytest.raises(ValueError, match="Big-endian"):
        font_formats.extract("bffnt", b"FFNT\xfe\xff" + bytes(64), {})


# -- BFN (the editor's own engine) --------------------------------------------------------------


def test_bfn_engine_keeps_chunk_order_padding_and_linear_map(tmp_path):
    """Wind Waker files: WID1 and MAP1 before GLY1, non-zero padding, a linear (type 0) map."""
    import json
    from tools.bfn_editor.bfn_engine import extract_bfn_logic, repack_bfn_logic

    inf1 = b"INF1" + struct.pack(">I6HI", 32, 0, 6, 2, 8, 8, 0x20, 7) + bytes.fromhex("DEADBEEF01020304")
    wid1 = b"WID1" + struct.pack(">IHH", 32, 0, 2) + bytes([0, 6, 1, 7]) + bytes(range(1, 17))
    map1 = b"MAP1" + struct.pack(">IHHHH", 32, 0, 0x20, 0x21, 0) + bytes(16)
    texture = bytes(((i * 37) & 0xFF) for i in range(64))
    gly1 = b"GLY1" + struct.pack(">IHHHHIHHHHH", 96, 0, 1, 8, 8, 64, 0, 2, 1, 16, 8) + bytes(2) + texture
    body = inf1 + wid1 + map1 + gly1
    data = b"FONTbfn1" + struct.pack(">II", 32 + len(body), 4) + bytes(16) + body

    (tmp_path / "f.bfn").write_bytes(data)
    extract_bfn_logic(str(tmp_path / "f.bfn"), str(tmp_path))
    metadata = json.loads((tmp_path / "data.json").read_text())
    block = metadata["MAP1"][0]                     # what the editor does on load
    block.update(linear_count=block["mapping_entry_count"], mapping_type=2, mapping_entry_count=2, entries=[0, 1])
    (tmp_path / "data.json").write_text(json.dumps(metadata))
    repack_bfn_logic(str(tmp_path), str(tmp_path / "out.bfn"))
    assert (tmp_path / "out.bfn").read_bytes() == data

    block["entries"] = [1, 0]                      # no longer linear: written as a table
    (tmp_path / "data.json").write_text(json.dumps(metadata))
    repack_bfn_logic(str(tmp_path), str(tmp_path / "out.bfn"))
    assert struct.unpack_from(">H", (tmp_path / "out.bfn").read_bytes(), 32 + 64 + 8)[0] == 2


# -- font sources in a project --------------------------------------------------------------


def test_sources_find_files_and_write_only_the_translation(tmp_path):
    source_root, translation_root = tmp_path / "source" / "text", tmp_path / "mod" / "text"
    (tmp_path / "source" / "fonts").mkdir(parents=True)
    source_root.mkdir()
    font = tmp_path / "source" / "fonts" / "main.g1t"
    font.write_bytes(b"ORIGINAL")
    descriptors = [{"label": "Main", "format": "g1t", "path": ["data/missing.g1t", "../fonts/*.g1t"],
                    "font_map": "main.json", "params": {"cell_width": 8}}]
    metadata = {"source_path": str(source_root), "translation_path": str(translation_root), "is_directory_mode": True}
    (found,) = sources.resolve(descriptors, metadata)
    assert found.source_path == str(font) and found.params == {"cell_width": 8}
    assert found.translation_path == str(tmp_path / "mod" / "fonts" / "main.g1t")
    assert found.read_current() == b"ORIGINAL"

    found.write(b"EDITED")
    assert font.read_bytes() == b"ORIGINAL"
    assert found.read_current() == b"EDITED" and found.read_original() == b"ORIGINAL"


def test_sources_single_file_project(tmp_path):
    rom, out = tmp_path / "game.z64", tmp_path / "game_ua.z64"
    rom.write_bytes(b"ROM")
    metadata = {"source_path": str(rom), "translation_path": str(out), "is_directory_mode": False}
    (found,) = sources.resolve([{"label": "Font", "format": "n64", "path": "*.z64"}], metadata)
    assert (found.source_path, found.translation_path) == (str(rom), str(out))
    no_translation = dict(metadata, translation_path="")
    with pytest.raises(ValueError, match="no translation folder"):
        sources.resolve([{"label": "Font", "format": "n64"}], no_translation)[0].write(b"x")


# -- the plugin hook and the text save ---------------------------------------------------------


def test_plugin_hook_reads_font_sources_json_next_to_the_rules(tmp_path, monkeypatch):
    import importlib.util
    import json
    import sys
    folder = tmp_path / "fake_font_plugin"
    folder.mkdir()
    (folder / "rules.py").write_text("from plugins.base_game_rules import BaseGameRules\n"
                                     "class GameRules(BaseGameRules):\n    pass\n", encoding="utf-8")
    described = [{"label": "Font", "format": "g1t", "path": "font.g1t"}]
    (folder / "font_sources.json").write_text(json.dumps(described), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("fake_font_plugin_rules", folder / "rules.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "fake_font_plugin_rules", module)
    spec.loader.exec_module(module)
    assert module.GameRules().get_font_sources() == described

    from plugins.base_game_rules import BaseGameRules
    assert BaseGameRules().get_font_sources() == []


def test_text_save_keeps_the_font_edited_in_the_translation_rom(tmp_path):
    from types import SimpleNamespace
    from core.data_processor.save_mixin import SaveMixin

    original = _n64_rom()
    metadata, sheets = font_formats.extract("n64", original, N64_PARAMS)
    metadata["WID1"][0]["packets"][3]["width"] = 14
    edited = font_formats.pack("n64", metadata, sheets, original, N64_PARAMS)
    source, translation = tmp_path / "game.z64", tmp_path / "game_ua.z64"
    source.write_bytes(original)
    translation.write_bytes(edited)
    rules = SimpleNamespace(get_font_sources=lambda: [{"label": "Font", "format": "n64", "params": N64_PARAMS}])
    project = SimpleNamespace(metadata={"source_path": str(source), "translation_path": str(translation),
                                        "is_directory_mode": False})
    saver = SaveMixin()
    saver.mw = SimpleNamespace(current_game_rules=rules, project_manager=SimpleNamespace(project=project))

    rebuilt = saver._keep_edited_fonts(str(translation), original)      # the plugin rebuilt the ROM from its source
    assert font_formats.extract("n64", rebuilt, N64_PARAMS)[0]["WID1"] == metadata["WID1"]
    assert saver._keep_edited_fonts(str(translation), "text") == "text"
    assert saver._keep_edited_fonts(str(tmp_path / "other.z64"), original) == original