"""Xenoblade Chronicles 2 plugin: legacy BDAT text tables (scrambled names and strings, checksum, the ``name``
cells as lines, labels kept), and the LAFT font whose glyph list is longer than its stored row count."""
import struct

from PIL import Image

from core import font_formats
from core.font_formats import laft
from core.formats import SaveContext
from core.texture_formats import mibl
from plugins.common import bdat_legacy as bdat
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.xenoblade_2.rules import TAG_RE

PLUGIN = "xenoblade_2"


def _table(name, rows, scrambled=True):
    """A legacy table ``name`` with columns label (string), style (u16), name (string): ``rows`` = [(label, style, text)]."""
    header = 0x24
    infos = struct.pack("<BBH", 1, 7, 0) + struct.pack("<BBH", 1, 2, 4) + struct.pack("<BBH", 1, 7, 6)
    names_off = header + len(infos)
    names = bytearray()
    name_at = {}
    for text in (name, "label", "style", "name"):
        name_at[text] = names_off + len(names)
        names += text.encode() + b"\0"
    mem_off = names_off + len(names)
    members = b"".join(struct.pack("<HHH", header + 4 * i, 0, name_at[col]) for i, col in enumerate(("label", "style", "name")))
    hash_off = mem_off + len(members)
    hashes = bytes(2 * 3)
    rows_off = hash_off + len(hashes)
    str_off = rows_off + 12 * len(rows)
    strings, items, where = bytearray(), bytearray(), {}
    for label, style, text in rows:
        offsets = []
        for value in (label, text):
            if value not in where:
                where[value] = str_off + len(strings)
                strings += value.encode("utf-8") + b"\0"
                strings += bytes(len(strings) % 2)
            offsets.append(where[value])
        items += struct.pack("<IHIH", offsets[0], style, offsets[1], 0)
    strings += bytes(-(str_off + len(strings)) % 16)
    head = struct.pack("<4sBBHHHHHHHHHIIHH", b"BDAT", 2 if scrambled else 0, 0, names_off, 12, hash_off, 3, rows_off,
                       len(rows), 1, 2, 0, str_off, len(strings), mem_off, 3)
    plain = bytearray(head + infos + names + members + hashes + items + strings)
    checksum = bdat.checksum_of(bytes(plain))
    struct.pack_into("<H", plain, 0x16, checksum)
    if scrambled:
        plain[names_off:hash_off] = bdat._scramble(bytes(plain[names_off:hash_off]), checksum)
        plain[str_off:] = bdat._scramble(bytes(plain[str_off:]), checksum)
    return bytes(plain)


def _file(tables):
    head = 8 + 4 * len(tables)
    offsets, at = [], head
    for table in tables:
        offsets.append(at)
        at += len(table)
    return struct.pack("<II", len(tables), at) + struct.pack(f"<{len(offsets)}I", *offsets) + b"".join(tables)


SAMPLE = _file([_table("bf01_ms", [("bf01_0010", 3, "Talk"), ("bf01_0020", 4, "Open"), ("bf01_0030", 5, "")]),
                _table("menu_ms", [("menu_0010", 1, "a"), ("menu_0020", 1, "[ML:icon icon=A ] b")], scrambled=False)])


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".bdat"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    assert bdat.is_bdat(SAMPLE)
    check_round_trip(PLUGIN, SAMPLE)


def test_text_cells_are_read_in_order_and_written_with_new_strings():
    assert bdat.read(SAMPLE) == ["Talk", "Open", "", "a", "[ML:icon icon=A ] b"]
    assert bdat.write(SAMPLE, bdat.read(SAMPLE)) == SAMPLE
    first, second = struct.unpack_from("<II", SAMPLE, 8)
    table = bdat._Table(SAMPLE[first:second])
    assert table.plain != SAMPLE[first:second] and table.text(table.offset_at(0, 0, 0)) == "bf01_0010"
    assert bdat._rebuild(table, table.texts()) == SAMPLE[first:second]          # scrambling and checksum redone
    out = bdat.write(SAMPLE, ["Розмова про щось довге", "Open", "", "a", "[ML:icon icon=A ] b"])
    assert bdat.is_bdat(out) and bdat.read(out) == ["Розмова про щось довге", "Open", "", "a", "[ML:icon icon=A ] b"]
    new_first, new_second = struct.unpack_from("<II", out, 8)
    assert len(out) > len(SAMPLE) and (new_second - new_first) % 16 == 0
    assert out[new_second:] == SAMPLE[second:]                                   # the untouched table is byte-identical
    again = bdat._Table(out[new_first:new_second])
    assert again.text(again.offset_at(0, 0, 0)) == "bf01_0010" and struct.unpack_from("<H", again.plain, again.rows_off + 4)[0] == 3
    assert again.checksum == bdat.checksum_of(again.plain) and again.flags & 2
    assert out[new_first + 0x24:new_first + 0x30] == SAMPLE[first + 0x24:first + 0x30]   # the member infos stay


def test_a_save_writes_over_the_newest_file_and_checks_the_line_count():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    rules.prepare_save_context(SaveContext(relative_path="bdat/gb/common_ms.bdat", existing_versions=lambda: iter([SAMPLE])))
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
    assert manager.is_tag_legitimate("[ML:undisp ]") and manager.is_tag_legitimate("[System:Color name=tutorial ]")
    assert manager.is_tag_legitimate("[/System:Color]")
    assert not manager.is_tag_legitimate("[blank\\]") and not TAG_RE.fullmatch("{PAGE}")


def _laft(glyphs, columns, rows, cell=(4, 5), height=None):
    """A LAFT font with ``glyphs`` [(code, left, right)] in a ``columns`` x ``rows`` grid; ``height`` overrides the atlas height."""
    cw, ch = cell
    width = -(-(columns * (cw + 1) + 1) // 4) * 4
    height = height or -(-(rows * (ch + 1) + 1) // 4) * 4
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
                     tex_at, len(texture), grid_at, 4, 0)
    return bytes(body) + texture


def test_a_laft_font_with_more_glyphs_than_rows_and_a_duplicate_code_packs_back_unchanged():
    # 5 glyphs in a 2-column grid that says 2 rows (XC2 staff_name), an atlas taller than the grid, code 0x41 twice
    raw = _laft([(0x20, 1, 2), (0x41, 0, 4), (0x152, 1, 3), (0x41, 0, 3), (0x43, 0, 3)], columns=2, rows=2, height=24)
    metadata, sheets = font_formats.extract("laft", raw, {"free_rows": 1})
    assert metadata["GLY1"][0]["glyph_vertical_count"] == 4 and font_formats.char_map(metadata)["A"] == 1
    assert font_formats.coverage(sheets[0]).getpixel((0, 12)) == 44                 # glyph 4 sits in row 2
    assert font_formats.pack("laft", metadata, sheets, raw, {}) == raw
    metadata["MAP1"][0]["entries"] = [0x20, 0x41, 0x43, 0x152, ord("Ї")] + [0, 1, 4, 2, 6]   # cell 6: the free row
    metadata["MAP1"][0]["mapping_entry_count"] = 5
    out = font_formats.pack("laft", metadata, sheets, raw, {})
    again, _sheets = font_formats.extract("laft", out, {"free_rows": 0})
    assert font_formats.char_map(again)["Ї"] == 6 and again["GLY1"][0]["glyph_vertical_count"] == 4
    assert struct.unpack_from("<HBB", out, struct.unpack_from("<I", out, 0x0C)[0] + 4 * 3) == (0x41, 0, 3)   # the duplicate keeps its code
