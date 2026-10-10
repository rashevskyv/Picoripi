"""Xenoblade Chronicles 3 plugin: modern BDAT text tables (strings re-laid out, other columns kept), the LAFT
font (glyph table, hash buckets, atlas growth) and the wilay layouts (MIBL blocks in place, the JPEG picture)."""
import io
import struct

from PIL import Image, ImageDraw

from core import font_formats
from core.font_formats import laft
from core.formats import SaveContext
from core.texture_formats import mibl, wilay
from plugins.common import bdat
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.xenoblade_3.rules import TAG_RE

PLUGIN = "xenoblade_3"


def _table(cols, rows):
    """A modern BDAT table: ``cols`` types, ``rows`` lists of values (a str for a string column)."""
    ncol, nrow = len(cols), len(rows)
    prefix = b"\0" + b"\x11\x22\x33\x44" + bytes(4) + b"".join(struct.pack("<I", 0xA0 + i) for i in range(ncol))
    strings, where = bytearray(prefix), {"": 0}
    packed_rows, hashes = bytearray(), bytearray()
    for n, row in enumerate(rows):
        hashes += struct.pack("<II", 0x1000 + n, n)
        for kind, value in zip(cols, row):
            if kind == 7:
                if value not in where:
                    where[value] = len(strings)
                    strings += value.encode("utf-8") + b"\0"
                packed_rows += struct.pack("<I", where[value])
            else:
                packed_rows += struct.pack({1: "<B", 2: "<H", 3: "<I", 9: "<I"}[kind], value)
    row_len = sum(bdat.SIZES[k] for k in cols)
    o_col, o_hash = 0x30, 0x30 + 3 * ncol
    o_row = o_hash + 8 * nrow
    o_str = o_row + row_len * nrow
    head = struct.pack("<4sHH10I", b"BDAT", 0x3004, 0, ncol, nrow, 1, 0, o_col, o_hash, o_row, row_len, o_str, len(strings))
    body = head + b"".join(struct.pack("<BH", k, 9 + 4 * i) for i, k in enumerate(cols)) + hashes + packed_rows + strings
    return body + bytes(-len(body) % 4)


def _file(tables):
    header = 16 + 4 * len(tables)
    offsets, at = [], header
    for table in tables:
        offsets.append(at)
        at += len(table)
    return struct.pack("<4sHHII", b"BDAT", 0x1004, 0x100, len(tables), at) + struct.pack(f"<{len(tables)}I", *offsets) + b"".join(tables)


SAMPLE = _file([_table([9, 2, 7], [[0xAAAA, 3, "Talk"], [0xBBBB, 4, "Open"], [0xCCCC, 5, ""]]),
                _table([7, 7], [["a", "[ML:icon icon=btn_a ] b"]])])


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".bdat"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    assert bdat.is_bdat(SAMPLE)
    check_round_trip(PLUGIN, SAMPLE)


def test_text_cells_are_read_in_order_and_written_with_new_strings():
    assert bdat.read(SAMPLE) == ["Talk", "Open", "", "a", "[ML:icon icon=btn_a ] b"]
    assert bdat.write(SAMPLE, bdat.read(SAMPLE)) == SAMPLE
    out = bdat.write(SAMPLE, ["Розмова", "Open", "", "a", "[ML:icon icon=btn_a ] b"])
    assert bdat.is_bdat(out) and bdat.read(out) == ["Розмова", "Open", "", "a", "[ML:icon icon=btn_a ] b"]
    first = struct.unpack_from("<I", out, 16)[0]
    second = struct.unpack_from("<I", out, 20)[0]
    second_len = len(SAMPLE) - struct.unpack_from("<I", SAMPLE, 20)[0]
    assert out[second:second + second_len] == SAMPLE[-second_len:]           # the untouched table is byte-identical
    _o_col, _o_hash, o_row, row_len, o_str, _str_len = struct.unpack_from("<6I", out, first + 24)
    assert struct.unpack_from("<IH", out, first + o_row)[:2] == (0xAAAA, 3)   # the hash and u16 columns stay
    assert struct.unpack_from("<I", out, first + o_row + row_len * 2 + 6)[0] == 0   # the empty text points at byte 0
    assert out[first + o_str] == 0 and out[first + o_str + 1:first + o_str + 5] == b"\x11\x22\x33\x44"
    assert struct.unpack_from("<I", out, 12)[0] == len(out) and len(out) % 4 == 0


def test_a_save_writes_over_the_newest_file_and_checks_the_line_count():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    rules.prepare_save_context(SaveContext(relative_path="bdat/gb/game/menu.bdat", existing_versions=lambda: iter([SAMPLE])))
    blocks[0][1] = "Відкрити"
    assert bdat.read(rules.save_data_to_json_obj(blocks, names))[1] == "Відкрити"
    try:
        rules.save_data_to_json_obj([blocks[0][:2]], names)
    except ValueError as error:
        assert "text cells" in str(error)
    else:
        raise AssertionError("a wrong line count must not be written")


def test_the_tag_manager_accepts_the_games_codes_only():
    rules = load_rules(PLUGIN)
    manager = rules.tag_manager_class()
    assert manager.is_tag_legitimate("[ML:icon icon=btn_a ]") and manager.is_tag_legitimate("[System:Color 1]")
    assert not manager.is_tag_legitimate("[Class: Sharpshooter]") and not TAG_RE.fullmatch("{PAGE}")


# -- LAFT fonts -----------------------------------------------------------------------

def _laft(glyphs, columns, rows, cell=(4, 5)):
    """A LAFT font with ``glyphs`` [(code, left, right)] in a ``columns`` x ``rows`` grid of ``cell`` cells."""
    cw, ch = cell
    width, height = -(-(columns * (cw + 1) + 1) // 4) * 4, -(-(rows * (ch + 1) + 1) // 4) * 4
    atlas = Image.new("L", (width, height), 0)
    for index in range(len(glyphs)):
        x, y = (index % columns) * (cw + 1), (index // columns) * (ch + 1)
        atlas.paste(40 + index, (x, y, x + cw, y + ch))
    by_bucket = {}
    for index, (code, _l, _r) in enumerate(glyphs):
        by_bucket.setdefault(code & 511, []).append(index)
    buckets, entries = bytearray(), []
    for bucket in range(512):
        ids = sorted(by_bucket.get(bucket, []), key=lambda i: glyphs[i][0])
        buckets += struct.pack("<HH", len(entries), len(ids))
        entries += ids
    entries_blob = struct.pack(f"<{len(entries)}H", *entries)
    entries_blob += bytes(-len(entries_blob) % 4)
    glyphs_at = laft.ENTRIES_AT + len(entries_blob)
    grid_at = glyphs_at + 4 * len(glyphs)
    body = bytearray(laft.HEADER_SIZE) + buckets + entries_blob
    body += b"".join(struct.pack("<HBB", *g) for g in glyphs) + struct.pack("<6I", width, height, cw, ch, columns, rows)
    tex_at = -(-len(body) // 4096) * 4096
    body += bytes(tex_at - len(body))
    texture = mibl.build(Image.merge("RGBA", (atlas, atlas.point(lambda _v: 0), atlas.point(lambda _v: 0),
                                              atlas.point(lambda _v: 255))), 1, 1)
    struct.pack_into("<4s13I", body, 0, b"LAFT", 10001, 0, glyphs_at, laft.ENTRIES_AT, len(glyphs), laft.HEADER_SIZE, 512, 511,
                     tex_at, len(texture), grid_at, 4, 20)
    return bytes(body) + texture


def test_a_laft_font_opens_packs_back_and_grows_for_a_new_letter():
    raw = _laft([(0x20, 1, 2), (0x41, 0, 4), (0x152, 1, 3), (0x241, 0, 3)], columns=3, rows=2)   # A and U+0241 share a bucket
    assert font_formats.detect(raw) == "laft"
    metadata, sheets = font_formats.extract("laft", raw, {"free_rows": 2})
    chars = font_formats.char_map(metadata)
    assert chars == {" ": 0, "A": 1, "Œ": 2, "Ɂ": 3}
    assert metadata["WID1"][0]["packets"][1] == {"kerning": 0, "width": 4}
    assert metadata["GLY1"][0]["cell_width"] == 5 and metadata["GLY1"][0]["glyph_vertical_count"] == 4
    assert font_formats.coverage(sheets[0]).getpixel((5, 0)) == 41       # cell 1 at x = 5 (pitch 5)
    assert font_formats.pack("laft", metadata, sheets, raw, {}) == raw
    metadata["MAP1"][0]["entries"] = [0x20, 0x41, 0x152, 0x241, ord("Ї")] + [0, 1, 2, 3, 7]   # cell 7: a free row
    metadata["MAP1"][0]["mapping_entry_count"] = 5
    metadata["WID1"][0]["packets"][7] = {"kerning": 1, "width": 3}
    ImageDraw.Draw(sheets[0]).rectangle((5, 12, 8, 16), fill=(255, 255, 255, 255))
    out = font_formats.pack("laft", metadata, sheets, raw, {})
    again, sheets2 = font_formats.extract("laft", out, {"free_rows": 0})
    assert font_formats.char_map(again)["Ї"] == 7 and again["WID1"][0]["packets"][7] == {"kerning": 1, "width": 3}
    assert again["GLY1"][0]["glyph_vertical_count"] == 3 and font_formats.coverage(sheets2[0]).getpixel((6, 13)) == 255
    assert struct.unpack_from("<I", out, 0x14)[0] == 8                     # glyphs up to the new cell, codes filled in
    assert font_formats.pack("laft", again, sheets2, out, {}) == out


# -- wilay layouts -----------------------------------------------------------------------

def test_mibl_blocks_in_a_layout_write_back_in_place_and_the_jpeg_is_replaced():
    picture = Image.new("RGBA", (16, 8), (200, 30, 30, 255))
    block = mibl.build(picture, 1, 2)                       # R8 with 2 mip levels
    assert mibl.detect(block) and len(block) == 4096
    assert mibl.read(block, {})[0].image.getpixel((0, 0))[0] == 200
    layout = b"LAGP" + struct.pack("<I", 10003) + bytes(0x1000 - 8) + block + block
    textures = wilay.read(layout, {})
    assert [t.name for t in textures] == ["#0", "#1"] and textures[1].pixel_format == "R8" and textures[1].mipmaps == 2
    assert wilay.write(layout, {0: textures[0].image, 1: textures[1].image}, {}) == layout
    changed = textures[1].image.copy()
    changed.putpixel((3, 3), (0, 0, 0, 255))
    out = wilay.write(layout, {1: changed}, {})
    assert len(out) == len(layout) and out[:0x1000 + 4096] == layout[:0x1000 + 4096]
    assert wilay.read(out, {})[1].image.getpixel((3, 3))[0] == 0
    jpeg = io.BytesIO()
    Image.new("RGB", (32, 16), (0, 0, 255)).save(jpeg, format="JPEG")
    head = bytearray(b"LAHD" + struct.pack("<I", 10003) + bytes(0xD0 - 8))
    struct.pack_into("<II", head, 0xC0, 0xD0, len(jpeg.getvalue()))
    layout = bytes(head) + jpeg.getvalue()
    (texture,) = wilay.read(layout, {})
    assert texture.name == "jpeg" and texture.image.size == (32, 16)
    red = Image.new("RGBA", (32, 16), (255, 0, 0, 255))
    out = wilay.write(layout, {0: red}, {})
    assert struct.unpack_from("<II", out, 0xC0) == (0xD0, len(out) - 0xD0) and out[0xD0:0xD3] == b"\xff\xd8\xff"
    assert wilay.read(out, {})[0].image.getpixel((5, 5))[0] > 200
