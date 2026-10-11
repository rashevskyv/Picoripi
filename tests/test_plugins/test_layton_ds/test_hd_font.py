"""Professor Layton HD ports: ``font.dat`` in the Font Editor model, and IMGA pictures (IMGN under another magic)."""
import copy
import struct
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core import font_formats, texture_formats
from core.containers import level5
from core.texture_formats import imgc, pixels

def make_imgn(image: Image.Image, fmt: int) -> bytes:
    """A Switch IMGN texture of 8x8 tiles, pixels row by row."""
    codec = pixels.codec(imgc.NX_FORMATS[fmt])
    width, height = image.size
    tiles = [codec.encode(image.crop((x, y, x + 8, y + 8))) for y in range(0, height, 8) for x in range(0, width, 8)]
    table = level5.compress(struct.pack(f"<{len(tiles)}h", *range(len(tiles))), level5.STORED)
    store = level5.compress(b"".join(tiles), level5.STORED)
    bpp = len(tiles[0]) * 8 // 64
    head = bytearray(0x48)
    head[:4] = b"IMGN"
    head[0x0A], head[0x0C], head[0x0D] = fmt, 1, bpp
    struct.pack_into("<HHHI", head, 0x0E, 64 * bpp // 8, width, height, 0)
    struct.pack_into("<I", head, 0x1C, 0x48)
    struct.pack_into("<III", head, 0x34, len(table), (len(table) + 3) & ~3, len(store))
    return bytes(head) + table + b"\0" * (-len(table) % 4) + store


HEIGHT, PAD = 6, 1
CELL = HEIGHT + 2 * PAD            # 8
WIDTH, ROWS_PX = 32, 16            # 4 x 2 cells


def make_font(entries):
    atlas = bytearray(WIDTH * ROWS_PX)
    for glyph in range(len(entries)):
        x0, y0 = (glyph % 4) * CELL, (glyph // 4) * CELL
        for y in range(2, 6):
            for x in range(2, 5):
                atlas[(y0 + y) * WIDTH + x0 + x] = 40 + 30 * glyph
    head = struct.pack("<IHHHH", len(entries), HEIGHT, PAD, WIDTH, ROWS_PX)
    return head + b"".join(struct.pack("<HH", code, adv) for code, adv in entries) + bytes(atlas)


ENTRIES = [(65, 5), (66, 6), (0xFEFF, 0)]
RAW = make_font(ENTRIES)


def test_unedited_font_packs_back_unchanged():
    meta, sheets = font_formats.extract("layton_hd", RAW, {})
    assert sheets[0].size == (WIDTH, ROWS_PX)
    assert meta["GLY1"][0]["glyph_horizontal_count"] == 4
    assert [p["width"] for p in meta["WID1"][0]["packets"]] == [5, 6, 0]
    assert font_formats.pack("layton_hd", meta, sheets, RAW, {}) == RAW


def test_a_redrawn_cell_and_a_new_width_are_written_in_place():
    meta, sheets = font_formats.extract("layton_hd", RAW, {})
    sheet = sheets[0].copy()
    ImageDraw.Draw(sheet).rectangle((8, 0, 15, 7), fill=(255, 255, 255, 255))      # cell 1 ('B') is a box
    meta["WID1"][0]["packets"][1]["width"] = 9
    new = font_formats.pack("layton_hd", meta, [sheet], RAW, {})
    assert len(new) == len(RAW)
    assert struct.unpack_from("<HH", new, 12 + 4) == (66, 9)
    again, sheets2 = font_formats.extract("layton_hd", new, {})
    assert sheets2[0].crop((8, 0, 16, 8)).getpixel((0, 0))[3] == 255
    assert sheets2[0].crop((0, 0, 8, 8)).tobytes() == sheets[0].crop((0, 0, 8, 8)).tobytes()


def test_a_new_letter_in_a_spare_cell_gets_a_sorted_entry():
    meta, sheets = font_formats.extract("layton_hd", RAW, {})
    sheet = sheets[0].copy()
    ImageDraw.Draw(sheet).rectangle((24, 0, 31, 7), fill=(255, 255, 255, 255))     # cell 3 (spare): the new glyph
    meta = copy.deepcopy(meta)
    pairs = font_formats.char_map(meta)
    pairs["ї"] = 3
    meta["MAP1"] = [font_formats.map_entries(sorted((font_formats.char_code(c), g) for c, g in pairs.items()))]
    meta["WID1"][0]["packets"].append({"kerning": 0, "width": 7})
    new = font_formats.pack("layton_hd", meta, [sheet], RAW, {})
    count = struct.unpack_from("<I", new, 0)[0]
    assert count == 4
    codes = [struct.unpack_from("<HH", new, 12 + 4 * i) for i in range(count)]
    assert codes == [(65, 5), (66, 6), (0x0457, 7), (0xFEFF, 0)]
    _meta, sheets2 = font_formats.extract("layton_hd", new, {})
    cells = [sheets2[0].crop(((i % 4) * 8, (i // 4) * 8, (i % 4) * 8 + 8, (i // 4) * 8 + 8)) for i in range(4)]
    assert cells[2].getpixel((0, 0))[3] == 255                 # the new letter's box
    assert cells[0].tobytes() == sheets[0].crop((0, 0, 8, 8)).tobytes()


def test_changing_a_code_the_font_has_is_refused():
    meta, sheets = font_formats.extract("layton_hd", RAW, {})
    meta = copy.deepcopy(meta)
    pairs = {c: g for c, g in font_formats.char_map(meta).items() if c != "B"}
    meta["MAP1"] = [font_formats.map_entries(sorted((font_formats.char_code(c), g) for c, g in pairs.items()))]
    with pytest.raises(ValueError):
        font_formats.pack("layton_hd", meta, sheets, RAW, {})


def test_imga_picture_reads_and_writes_like_imgn():
    image = Image.new("RGBA", (16, 8))
    for x in range(16):
        for y in range(8):
            image.putpixel((x, y), (x * 16, y * 32, 90, 255))
    imgn = make_imgn(image, 0)
    imga = b"IMGA" + imgn[4:]
    assert texture_formats.detect(imga, "x.xi") == "imgc"
    textures = texture_formats.read("imgc", imga)
    assert textures[0].image.tobytes() == texture_formats.read("imgc", imgn)[0].image.tobytes()
    assert texture_formats.write("imgc", imga, {0: textures[0].image}) == imga


REAL = Path(r"E:\Emulators\RomHacking\Professor Layton")


@pytest.mark.parametrize("game", ["Curious Village", "Pandora's Box", "Lost Future"])
def test_real_hd_font_round_trips(game):
    files = list((REAL / game / "Switch (port)" / "source").rglob("font.dat"))
    if not files:
        pytest.skip("the HD port is not unpacked")
    raw = files[0].read_bytes()
    meta, sheets = font_formats.extract("layton_hd", raw, {})
    assert font_formats.pack("layton_hd", meta, sheets, raw, {}) == raw


def test_event_header_stays_apart_and_hd_ports_take_utf8():
    from plugins.layton_ds.formats import Document, EncodeError

    raw = b"50|NONE|NONE|3|Hello there!\r\nSecond line."
    hd = Document(raw, "data-en/event/t10_000_100.txt")
    assert hd.rows[0].label == "50|NONE|NONE|3|" and hd.rows[0].text.startswith("Hello there!")
    assert hd.build(hd.texts()) == raw
    new = hd.build(["Привіт, їжак!"])
    assert new == b"50|NONE|NONE|3|" + "Привіт, їжак!".encode("utf-8")
    ds = Document(raw, "data_lt2/event/en/t10_000_100.txt")      # a DS game: Latin-1 text, no Cyrillic
    with pytest.raises(EncodeError):
        ds.build(["Привіт"])
    assert Document(b"50|NONE|NONE|3|", "data-en/event/t.txt").rows == []        # a header alone has no text


def test_utf8_can_be_given_by_the_caller_and_a_puzzle_record_is_found_by_content():
    from plugins.layton_ds.formats import Document, NazoCodec

    bank = b"\x00".join([b"Prompt", b"Right", b"Wrong", b"Hint 1", b"Hint 2", b"Hint 3"]) + b"\x00"
    offsets, at = [], 0
    for part in bank.split(b"\x00")[:6]:
        offsets.append(at)
        at += len(part) + 1
    head = bytearray(112)
    struct.pack_into("<H", head, 2, 112)
    head[4:4 + 5] = b"Title"
    struct.pack_into("<6I", head, 0x40, *offsets)
    raw = bytes(head) + bank
    assert NazoCodec(raw).rows[0].text == "Title"
    document = Document(raw, "", utf8=True)
    assert [r.text for r in document.rows][:2] == ["Title", "Prompt"]
    changed = document.build(["Титул", "Prompt", "Right", "Wrong", "Hint 1", "Hint 2", "Hint 3"])
    assert "Титул".encode("utf-8") in changed
