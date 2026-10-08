"""Fragile Dreams plugin: message blocks (load, save, a longer text, cp1251), the HOME Menu table, the FONT
format (unedited = same bytes, a redrawn and a bigger glyph, widths); the real files when the workspace is
unpacked here."""
import struct
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core import font_formats
from core.formats import SaveContext
from core.texture_formats import sources as texture_sources
from core.texture_formats import tpl
from plugins.fragile_dreams import fdtext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "fragile_dreams"
SOURCE = Path(r"E:\Emulators\RomHacking\Fragile Dreams\source")
real = pytest.mark.skipif(not (SOURCE / "text" / "60001061.msg").exists(), reason="Fragile Dreams not unpacked here")


def block(tag: bytes, *texts: bytes, garbage: bytes = b"") -> bytes:
    head = bytearray(tag + struct.pack(">III", 0, 0x4E4, len(texts)) + bytes(8 * len(texts)))
    body = bytearray()
    for i, text in enumerate(texts):
        struct.pack_into(">II", head, 16 + 8 * i, i + 1, len(head) + len(body) - (16 + 8 * i))
        body += text + bytes(-(len(text) + 1) % 4 + 1)
    struct.pack_into(">I", head, 4, len(head) + len(body))
    out = bytes(head + body)
    pad = -len(out) % 0x20
    return out + (garbage * pad)[:pad] if garbage else out + bytes(pad)


SAMPLE = (block(b"USA ", b"<v1>Who's there?!<w>", b"<v>It's...his flashlight!<w>", garbage=b"2003\\Tools\\")
          + block(b"USA ", b"[Red]ATK+[Value]\nA stick you can swing.") + bytes(0x20))


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".msg", ".csv"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_a_longer_text_moves_the_next_block_and_keeps_the_rest():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert blocks == [["<v1>Who's there?!<w>", "<v>It's...his flashlight!<w>"],
                      ["[Red]ATK+[Value]\nA stick you can swing."]]
    assert names == {"0": "Block 1 (2)", "1": "Block 2 (1)"}
    rules.prepare_save_context(SaveContext(relative_path="text/x.msg", existing_versions=lambda: iter([SAMPLE])))
    assert rules.save_data_to_json_obj(blocks, names) == SAMPLE
    blocks[0][1] = "<v>Це... його ліхтарик! Ґанок, їжак, є.<w>" * 3
    saved = rules.save_data_to_json_obj(blocks, names)
    again, _names = rules.load_data_from_json_obj(saved)
    assert again == blocks
    second = fdtext.parse(saved).blocks[1]
    assert second.raw == fdtext.parse(SAMPLE).blocks[1].raw            # the unchanged block keeps its bytes
    assert saved.endswith(bytes(0x20)) and len(saved) % 0x20 == 0


def test_tags_and_cp1251():
    assert fdtext.TAG_RE.fullmatch("<c#404040ff>") and fdtext.TAG_RE.fullmatch("[Value]")
    missing = set()
    assert fdtext.from_editor("Їжак … ★", missing) == "Їжак … ?".encode("cp1251") and missing == {"★"}
    assert fdtext.to_editor(b"\x93Hi\x94\x85") == "“Hi”…"


def test_the_home_menu_table_shows_the_english_cells():
    cell = '"{}"'
    text = "\r\n".join("\t".join(cell.format(f"{lang}{n}") for lang in ("jp", "en", "de")) for n in range(2))
    raw = b"\xfe\xff" + text.encode("utf-16-be")
    rules = load_rules(PLUGIN)
    blocks, _names = rules.load_data_from_json_obj(raw)
    assert blocks == [["en0", "en1"]]


def test_the_english_blocks_of_main_dol_are_written_in_place_within_their_room():
    usa = block(b"USA ", b"Creating save data.", b"Yes")
    dol = bytearray(b"\x00\x00\x01\x00" + bytes(0x11C))
    dol += block(b"JPN ", b"x") + usa + b"CODE" * 8
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(bytes(dol))
    assert blocks == [["Creating save data.", "Yes"]] and "main.dol" in names["0"]
    rules.prepare_save_context(SaveContext(relative_path="sys/main.dol", existing_versions=lambda: iter([bytes(dol)])))
    assert rules.save_data_to_json_obj(blocks, names) == bytes(dol)
    blocks[0][0] = "UA TEST"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert len(saved) == len(dol) and saved.endswith(b"CODE" * 8)
    assert rules.load_data_from_json_obj(saved)[0] == [["UA TEST", "Yes"]]
    blocks[0][0] = "Too long " * 20
    with pytest.raises(fdtext.FormatError, match="room"):
        rules.save_data_to_json_obj(blocks, names)


# -- the FONT format -----------------------------------------------------------------------------


def make_font() -> bytes:
    """A FONT with glyphs for A and B in one 64 x 16 I4 page."""
    codes = {0x41: (1, 1), 0x42: (8, 1)}
    records = bytearray()
    table = bytearray(0x400)
    for n, (code, (x, y)) in enumerate(sorted(codes.items())):
        struct.pack_into(">I", table, 4 * code, 8 + 0x400 + 10 * n)
        records += struct.pack(">BBbbBBB", 6, 10, 0, 1, 5, 7, 0) + (x << 12 | y).to_bytes(3, "big")
    bc = b"BC  " + struct.pack(">I", 0) + table + records
    bc += bytes(-(0x14 + len(bc) + 8) % 0x20)
    bc = bc[:4] + struct.pack(">I", len(bc)) + bc[8:]
    head = bytearray(b"\x00\x20\xaf\x30" + struct.pack(">III", 1, 0xC, 0x14) + bytes(4))
    head += struct.pack(">HHII", 16, 64, 0, 0x40) + bytes(0x40 - len(head) - 12)
    page = bytes(head) + bytes(64 * 16 // 2)
    image = Image.new("RGBA", (64, 16))
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, 5, 7), fill=(255, 255, 255, 255))
    draw.rectangle((8, 1, 12, 7), fill=(136, 136, 136, 136))
    page = tpl.write(page, {0: image}, {})
    texd = b"TEXD" + struct.pack(">I", 8 + len(page)) + page
    body = bc + texd
    return b"FONT" + struct.pack(">IBBBBHHI", 0x14 + len(body), 1, 1, 8, 1, 8, 10, 0) + body


def test_a_font_packs_back_unchanged_and_takes_a_redrawn_or_bigger_glyph():
    data = make_font()
    meta, sheets = font_formats.extract("fragile_dreams", data, {})
    gly = meta["GLY1"][0]
    assert (gly["glyph_horizontal_count"], gly["cell_width"]) == (16, 8)
    assert meta["WID1"][0]["packets"][0x41]["width"] == 6
    assert font_formats.char_map(meta)["А"] == 0xC0            # cp1251 cells for Ukrainian letters
    assert font_formats.pack("fragile_dreams", meta, sheets, data, {}) == data
    sheet = sheets[0].copy()
    draw = ImageDraw.Draw(sheet)
    cw, ch = gly["cell_width"], gly["cell_height"]
    bx, by = (0x42 % 16) * cw, (0x42 // 16) * ch
    draw.rectangle((bx, by, bx + cw - 1, by + ch - 1), fill=(0, 0, 0, 0))
    draw.rectangle((bx, by, bx + 6, by + 8), fill=(255, 255, 255, 255))      # bigger than B's 5x7 box
    meta["WID1"][0]["packets"][0x41]["width"] = 9
    packed = font_formats.pack("fragile_dreams", meta, [sheet], data, {})
    assert len(packed) == len(data) and packed != data
    meta2, sheets2 = font_formats.extract("fragile_dreams", packed, {})
    assert meta2["WID1"][0]["packets"][0x41]["width"] == 9
    cell = sheets2[0].crop((bx, by, bx + cw, by + ch))
    assert font_formats.coverage(cell).getbbox() == (0, 0, 7, 9)
    a = (0x41 % 16) * cw, (0x41 // 16) * ch
    assert sheets2[0].crop((*a, a[0] + cw, a[1] + ch)).tobytes() == sheets[0].crop((*a, a[0] + cw, a[1] + ch)).tobytes()


def test_a_glyph_in_a_code_without_record_is_refused():
    data = make_font()
    meta, sheets = font_formats.extract("fragile_dreams", data, {})
    gly = meta["GLY1"][0]
    sheet = sheets[0].copy()
    x, y = (0xC0 % 16) * gly["cell_width"], (0xC0 // 16) * gly["cell_height"]
    ImageDraw.Draw(sheet).rectangle((x, y, x + 3, y + 3), fill=(255, 255, 255, 255))
    with pytest.raises(ValueError, match="no glyph record"):
        font_formats.pack("fragile_dreams", meta, [sheet], data, {})


# -- the real game -----------------------------------------------------------------------------


@real
def test_every_text_file_opens_and_saves_unchanged():
    rules = load_rules(PLUGIN)
    count = 0
    for path in sorted((SOURCE / "text").rglob("*.msg")):
        data = path.read_bytes()
        blocks, names = rules.load_data_from_json_obj(data)
        count += sum(len(b) for b in blocks)
        rules.prepare_save_context(SaveContext(relative_path=path.name, existing_versions=lambda d=data: iter([d])))
        assert rules.save_data_to_json_obj(blocks, names) == data, path
    assert count >= 3000
    dol = (SOURCE / "sys" / "main.dol").read_bytes()
    blocks, names = rules.load_data_from_json_obj(dol)
    assert [len(b) for b in blocks] == [41, 1, 11]
    rules.prepare_save_context(SaveContext(relative_path="sys/main.dol", existing_versions=lambda: iter([dol])))
    assert rules.save_data_to_json_obj(blocks, names) == dol


@real
def test_every_font_opens_and_packs_back_the_same():
    fonts = sorted((SOURCE / "font").rglob("*.font"))
    assert len(fonts) == 14
    for path in fonts:
        data = path.read_bytes()
        meta, sheets = font_formats.extract("fragile_dreams", data, {})
        assert font_formats.pack("fragile_dreams", meta, sheets, data, {}) == data, path


@real
def test_the_texture_sources_find_the_ui_pictures():
    rules = load_rules(PLUGIN)
    found = texture_sources.resolve(rules.get_texture_sources(),
                                    {"source_path": str(SOURCE), "translation_path": "", "is_directory_mode": True})
    assert len(found) >= 2700
    logo = [s for s in found if s.key.startswith("ui/600010A5.tpl")]
    assert logo and logo[0].kind == "title_screen"
