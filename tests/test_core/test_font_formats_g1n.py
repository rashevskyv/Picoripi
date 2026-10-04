"""G1N fonts (Age of Calamity): synthetic files round-trip byte-exact, glyphs are redrawn and added."""
import struct

import pytest
from PIL import ImageDraw

from core import font_formats

CELL = 8


def _g1n(fonts):
    """A G1N with ``fonts`` = [[(code, width, pixel rows as "0..f" strings)]]; glyph 0 of each is the first."""
    count = len(fonts)
    header = 0x20 + 4 * count + 64 * count
    sections, bitmaps = [], bytearray()
    for glyphs in fonts:
        table = [0] * 65536
        records = bytearray()
        for index, (code, width, rows) in enumerate(glyphs):
            table[code] = index
            stride = (width + 1) // 2
            bitmap = bytearray(stride * CELL)
            for y, row in enumerate(rows):
                for x, digit in enumerate(row):
                    bitmap[y * stride + x // 2] |= int(digit, 16) << (4 * (x % 2))
            records += struct.pack("<8BI", width, CELL, 0, CELL - 1, width, 256 - CELL // 2, 0, CELL, len(bitmaps))
            bitmaps += bitmap + bytes(CELL * CELL // 2 - len(bitmap))
        sections.append(struct.pack("<65536H", *table) + bytes(records))
    offsets, at = [], header
    for section in sections:
        offsets.append(at)
        at += len(section)
    head = struct.pack("<8sIIIIII", b"_N1G0000", at + len(bitmaps), header, 10, at, count, count)
    head += struct.pack(f"<{count}I", *offsets) + b"".join(
        b"".join(struct.pack("<I", 0x00FFFFFF | (i * 17) << 24) for i in range(16)) for _ in range(count))
    return head + b"".join(sections) + bytes(bitmaps)


ROWS_A = ["0ff0", "f00f", "ffff", "f00f"]
SAMPLE = _g1n([
    [(0x20, 3, []), (0x41, 4, ROWS_A), (0x80, 2, ["ff"])],   # U+0080: a control code a game font maps
    [(0x20, 2, []), (0x42, 5, ["fffff"])],
])


def _cell_box(metadata, glyph):
    gly = metadata["GLY1"][0]
    columns, cell = gly["glyph_horizontal_count"], gly["cell_width"]
    return (glyph % columns) * cell, (glyph // columns) * cell


def test_detect_and_round_trip_every_font():
    assert font_formats.detect(SAMPLE) == "g1n"
    for font in (0, 1):
        metadata, sheets = font_formats.extract("g1n", SAMPLE, {"font": font, "spare": 4})
        assert font_formats.pack("g1n", metadata, sheets, SAMPLE, {"font": font, "spare": 4}) == SAMPLE
    metadata, sheets = font_formats.extract("g1n", SAMPLE, {"font": 0})
    assert font_formats.char_map(metadata)["A"] == 1 and font_formats.char_map(metadata)[" "] == 0
    assert font_formats.font_map(metadata)["A"] == {"width": 4}
    x, y = _cell_box(metadata, 1)
    assert sheets[0].getpixel((x + 1, y)) == (255, 255, 255, 255) and sheets[0].getpixel((x, y))[3] == 0


def test_redrawn_glyph_and_width_stay_in_their_slot():
    params = {"font": 0, "spare": 4}
    metadata, sheets = font_formats.extract("g1n", SAMPLE, params)
    x, y = _cell_box(metadata, 1)
    ImageDraw.Draw(sheets[0]).rectangle((x, y + 5, x + 5, y + 6), fill=(255, 255, 255, 255))
    metadata["WID1"][0]["packets"][1]["width"] = 6
    edited = font_formats.pack("g1n", metadata, sheets, SAMPLE, params)
    assert len(edited) == len(SAMPLE)
    again, again_sheets = font_formats.extract("g1n", edited, params)
    assert again["WID1"][0]["packets"][1]["width"] == 6
    assert again_sheets[0].crop((x, y, x + 6, y + CELL)).tobytes() == sheets[0].crop((x, y, x + 6, y + CELL)).tobytes()
    assert font_formats.extract("g1n", edited, {"font": 1})[0] == font_formats.extract("g1n", SAMPLE, {"font": 1})[0]


def test_new_character_adds_a_glyph_and_moves_the_next_font():
    params = {"font": 0, "spare": 4}
    metadata, sheets = font_formats.extract("g1n", SAMPLE, params)
    x, y = _cell_box(metadata, 3)
    ImageDraw.Draw(sheets[0]).rectangle((x, y + 2, x + 2, y + 4), fill=(255, 255, 255, 255))
    metadata["WID1"][0]["packets"][3] = {"kerning": 0, "width": 4}
    block = metadata["MAP1"][0]
    half = len(block["entries"]) // 2
    pairs = list(zip(block["entries"][:half], block["entries"][half:])) + [(font_formats.char_code("Ж"), 3)]
    metadata["MAP1"] = [font_formats.map_entries(pairs)]
    edited = font_formats.pack("g1n", metadata, sheets, SAMPLE, params)
    assert len(edited) == len(SAMPLE) + 12 + CELL * CELL // 2
    assert struct.unpack_from("<I", edited, 8)[0] == len(edited)
    again, again_sheets = font_formats.extract("g1n", edited, params)
    assert font_formats.char_map(again)["Ж"] == 3 and font_formats.char_map(again)["A"] == 1
    assert again_sheets[0].crop((x, y, x + 4, y + CELL)).tobytes() == sheets[0].crop((x, y, x + 4, y + CELL)).tobytes()
    assert font_formats.extract("g1n", edited, {"font": 1})[0] == font_formats.extract("g1n", SAMPLE, {"font": 1})[0]
    table = struct.unpack_from("<65536H", edited, struct.unpack_from("<I", edited, 0x20)[0])
    assert table[0x80] == 2 and table[0x416] == 3          # the control-code entry survives the rewrite
    assert font_formats.pack("g1n", again, again_sheets, edited, params) == edited


def test_wrong_font_index_and_magic_are_refused():
    with pytest.raises(ValueError):
        font_formats.extract("g1n", SAMPLE, {"font": 2})
    with pytest.raises(ValueError):
        font_formats.extract("g1n", b"GT1G0600" + bytes(64), {})


def test_editor_gives_a_new_g1n_glyph_its_own_character():
    from types import SimpleNamespace

    from tools.bfn_editor.translation_map_mixin import TranslationMapMixin
    metadata, _sheets = font_formats.extract("g1n", SAMPLE, {"font": 0})
    editor = SimpleNamespace(font_format="g1n", metadata=metadata, translation_map={},
                             get_next_free_char_code=lambda _map=None: 0xA1)
    assert font_formats.adds_glyphs("g1n") and not font_formats.adds_glyphs("g1t")
    assert TranslationMapMixin.physical_code_for(editor, "Ж") == 0x416
    assert TranslationMapMixin.physical_code_for(editor, "A") == 0xA1     # the font has A: a free slot
    editor.font_format = "g1t"
    assert TranslationMapMixin.physical_code_for(editor, "Ж") == 0xA1
