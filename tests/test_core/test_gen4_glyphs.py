"""Gen 4 DS font bins (core/font_formats/gen4_glyphs.py) and the extended LZ10 header (core/containers/lz10.py)."""
import random
import struct

from core.containers import lz10
from core.font_formats import gen4_glyphs as G


def _font_bin(count: int, gw: int = 2, gh: int = 2, seed: int = 1) -> bytes:
    rnd = random.Random(seed)
    glyph = 16 * gw * gh
    body = bytes(rnd.getrandbits(8) for _ in range(count * glyph))
    widths = bytes(rnd.randrange(4, 17) for _ in range(count))
    return struct.pack("<IIIBBBB", 16, 16 + count * glyph, count, 8 * gw, 8 * gh, gw, gh) + body + widths


def test_bin_round_trip_is_byte_exact():
    raw = _font_bin(5)
    assert G.is_font_bin(raw)
    meta, sheets = G.extract(raw, {})
    assert G.pack(meta, sheets, raw, {}) == raw
    assert meta["GLY1"][0]["end_glyph"] == 4


def test_edited_pixel_lands_in_the_right_glyph_and_tile():
    raw = _font_bin(3)
    meta, sheets = G.extract(raw, {})
    sheet = sheets[0]
    glyph, tile_x, tile_y, x, y = 2, 1, 1, 3, 5      # glyph 2 (third cell), its bottom-right tile, pixel (3, 5)
    cell_x, cell_y = (glyph % 16) * 16, (glyph // 16) * 16
    sheet.putpixel((cell_x + tile_x * 8 + x, cell_y + tile_y * 8 + y), (255, 255, 255, 255))
    out = G.pack(meta, sheets, raw, {})
    changed = [i for i in range(len(raw)) if raw[i] != out[i]]
    assert changed, "the edit did not reach the file"
    tile_at = 16 + glyph * 64 + 3 * 16 + y * 2
    assert all(tile_at <= i <= tile_at + 1 for i in changed)
    assert G.extract(out, {})[1][0].getpixel((cell_x + tile_x * 8 + x, cell_y + tile_y * 8 + y))[0] == 255


def test_widths_follow_the_metadata_packets():
    raw = _font_bin(4)
    meta, sheets = G.extract(raw, {})
    for packet in meta["WID1"][0]["packets"]:
        packet["width"] = 9
    out = G.pack(meta, sheets, raw, {})
    assert out[-4:] == bytes([9, 9, 9, 9])


def test_random_bytes_are_not_a_font_bin():
    assert not G.is_font_bin(bytes(range(200)))


def test_extended_lz10_header_decodes():
    # 0x10, zero 24-bit size, then the u32 size 5; one flag byte 0 = five literals
    stream = b"\x10\x00\x00\x00" + struct.pack("<I", 5) + b"\x00" + b"hello"
    assert lz10.decompress(stream)[0] == b"hello"


def test_chars_param_becomes_a_char_map():
    from core.font_formats import char_map

    raw = _font_bin(20)
    meta, _sheets = G.extract(raw, {"chars": {"A": 3, "T": 19, "??": 2, "B": 40}})
    mapping = char_map(meta)
    assert mapping == {"A": 3, "T": 19}          # two-character and out-of-range entries are left out


def test_diamond_charmap_gives_glyph_index_text_code_minus_one():
    from plugins.pokemon_gen4.rules import _glyph_map, _CHARMAPS

    glyphs = _glyph_map(str(_CHARMAPS / "charmap_dp_hgss.txt"))
    assert glyphs["T"] == 0x13E - 1
    assert glyphs["A"] == 0x12B - 1
