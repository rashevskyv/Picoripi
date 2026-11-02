"""The FONTbfn1 (ResFONT) backend and the glyph-sheet export/import, on synthetic fonts only."""
import random
import struct
from pathlib import Path

import pytest
from PIL import Image

from core.font_formats import extract, pack
from core.font_formats import resfont
from core.font_formats import sheet_io

CELL = 16
ROWS, COLS = 2, 2          # cells per row and per column: 4 glyphs a sheet
TEX_W = 32                 # texture width: two cells across
SHEETS = 2


def _font(seed: int = 1) -> bytes:
    sheet_bytes = TEX_W * TEX_W // 2                       # I4: 0.5 byte a texel, square texture of TEX_W
    glyphs = SHEETS * ROWS * COLS
    gly_size = 0x20 + sheet_bytes * SHEETS
    body = bytearray(0x20 + gly_size)
    body[:8] = resfont.MAGIC
    struct.pack_into(">II", body, 8, len(body), 1)
    struct.pack_into(">4sI", body, 0x20, b"GLY1", gly_size)
    struct.pack_into(">HHHHIHHHH", body, 0x28, 0, glyphs - 1, CELL, CELL, sheet_bytes, 0, ROWS, COLS, TEX_W)
    rng = random.Random(seed)
    body[0x40:] = bytes(rng.randrange(256) for _ in range(sheet_bytes * SHEETS))
    return bytes(body)


def test_original_bytes_come_back_unchanged():
    data = _font()
    metadata, sheets = extract("resfont", data, {})
    assert len(sheets) == SHEETS
    assert pack("resfont", metadata, sheets, data, {}) == data


def test_texel_nibbles_map_to_grey_ink():
    data = bytearray(_font())
    data[0x40] = 0x5A                                       # texel (0, 0) = 5, texel (1, 0) = 10
    metadata, sheets = extract("resfont", bytes(data), {})
    pixels = sheets[0].convert("RGBA").load()
    assert pixels[0, 0][3] == 5 * 17 and pixels[1, 0][3] == 10 * 17
    assert metadata["GLY1"][0]["glyph_horizontal_count"] == ROWS


def test_an_edit_changes_only_its_texel_byte():
    data = bytearray(_font())
    data[0x40] = 0x00                                       # texels (0, 0) and (1, 0) start at 0
    data = bytes(data)
    metadata, sheets = extract("resfont", data, {})
    sheets[0].putpixel((0, 0), (255, 255, 255, 255))         # full ink at texel (0, 0)
    out = pack("resfont", metadata, sheets, data, {})
    changed = [i for i in range(len(data)) if data[i] != out[i]]
    assert changed == [0x40]


def test_a_sheet_of_another_size_is_refused():
    data = _font()
    metadata, sheets = extract("resfont", data, {})
    sheets[0] = Image.new("RGBA", (TEX_W, TEX_W + 8))
    with pytest.raises(ValueError, match="sheet is"):
        pack("resfont", metadata, sheets, data, {})


def test_a_missing_sheet_is_refused():
    data = _font()
    metadata, sheets = extract("resfont", data, {})
    with pytest.raises(ValueError, match="sheets"):
        pack("resfont", metadata, sheets[:1], data, {})


def test_shift_jis_code_becomes_the_character_it_spells():
    assert resfont._code_of(0x8446) == ord("Ё")
    assert resfont._code_of(0x41) == 0x41


def test_sheet_export_and_import_round_trip(tmp_path: Path):
    data = bytearray(_font())
    data[0x80] = 0x00                                       # texel (16, 0) starts at 0
    data = bytes(data)
    written = sheet_io.export_sheets("resfont", data, tmp_path, "dialogue")
    names = sorted(p.name for p in written)
    assert "dialogue_sheet_0.png" in names and "dialogue_sheet_0_grid.png" in names and "dialogue_cells.json" in names
    clean = Image.open(tmp_path / "dialogue_sheet_0.png").convert("RGBA")
    clean.putpixel((CELL, 0), (255, 255, 255, 255))           # an edit in cell 1 of sheet 0
    clean.save(tmp_path / "dialogue_sheet_0.png")
    out = sheet_io.import_sheets("resfont", data, tmp_path, "dialogue")
    metadata, sheets = extract("resfont", out, {})
    assert sheets[0].convert("RGBA").getpixel((CELL, 0))[3] == 255
    assert len(out) == len(data)
    assert out != data


def test_grid_preview_is_not_read_back(tmp_path: Path):
    data = _font()
    sheet_io.export_sheets("resfont", data, tmp_path, "dialogue")
    Image.new("RGB", (TEX_W, TEX_W), (255, 0, 0)).save(tmp_path / "dialogue_sheet_0_grid.png")
    assert sheet_io.import_sheets("resfont", data, tmp_path, "dialogue") == data
