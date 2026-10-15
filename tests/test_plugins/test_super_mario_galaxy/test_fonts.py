"""Font port on synthetic NW4R fonts: the Switch's little-endian TNFR read as RFNT, Cyrillic glyphs copied into a
Wii font, and the Ukrainian text normalised and written for each font."""
import struct

from core.font_formats import bcfnt, char_map
from plugins.super_mario_galaxy import font_port, messages

SHEET_AT = 0x60


def build_font(little: bool, cell: int, size: int, glyphs, ascent: int) -> bytes:
    """An I4 NW4R font with one sheet of ``size`` x ``size`` and ``cell`` x ``cell`` cells. ``glyphs``: (character,
    advance, ink rows) in glyph order; a glyph's cell is filled with ink on those rows. ``little``: the Switch form."""
    e = "<" if little else ">"
    columns = rows = size // (cell + 1)
    sheet = bytearray(size * size // 2)
    pixels = bytearray(size * size)
    for index, (_ch, _advance, (top, bottom)) in enumerate(glyphs):
        x0, y0 = index % columns * (cell + 1) + 1, index // columns * (cell + 1) + 1
        for y in range(y0 + top, y0 + bottom):
            for x in range(x0 + 1, x0 + cell - 1):
                pixels[y * size + x] = 15
    order = [(ty + y) * size + tx + x for ty in range(0, size, 8) for tx in range(0, size, 8)
             for y in range(8) for x in range(8)]
    texels = [pixels[p] for p in order]
    sheet[:] = bytes(high << 4 | low for high, low in zip(texels[0::2], texels[1::2]))
    tglp_at = 0x30
    cwdh_at = SHEET_AT + len(sheet)
    cwdh = struct.pack(e + "HHI", 0, len(glyphs) - 1, 0) + b"".join(
        struct.pack("bBB", 0, cell, advance) for _ch, advance, _ink in glyphs)
    cwdh += bytes(-len(cwdh) % 4)
    cmap_at = cwdh_at + 8 + len(cwdh)
    pairs = sorted((ord(ch), index) for index, (ch, _a, _i) in enumerate(glyphs))
    body = struct.pack(e + "HHHHI", 0, 0xFFFF, 2, 0, 0) + struct.pack(e + "H", len(pairs)) + b"".join(
        struct.pack(e + "HH", code, glyph) for code, glyph in pairs)
    body += bytes(-len(body) % 4)
    total = cmap_at + 8 + len(body)
    out = bytearray(total)
    magic = (lambda word: word[::-1]) if little else (lambda word: word)
    out[0:4] = b"TNFR" if little else b"RFNT"
    out[4:6] = b"\xff\xfe" if little else b"\xfe\xff"
    struct.pack_into(e + "HIHH", out, 6, 0x0104, total, 0x10, 4)
    out[0x10:0x14] = magic(b"FINF")
    struct.pack_into(e + "I", out, 0x14, 0x20)
    struct.pack_into(e + "BbHbBBBIIIBBBB", out, 0x18, 1, cell + 2, 0, 0, cell, cell, 1, tglp_at + 8, cwdh_at + 8,
                     cmap_at + 8, cell, cell, ascent, 0)
    out[tglp_at:tglp_at + 4] = magic(b"TGLP")
    struct.pack_into(e + "I", out, tglp_at + 4, cwdh_at - tglp_at)
    struct.pack_into(e + "BBbBIHHHHHHI", out, tglp_at + 8, cell, cell, ascent, cell, len(sheet), 1, 0, columns,
                     rows, size, size, SHEET_AT)
    out[SHEET_AT:SHEET_AT + len(sheet)] = sheet
    out[cwdh_at:cwdh_at + 4] = magic(b"CWDH")
    struct.pack_into(e + "I", out, cwdh_at + 4, 8 + len(cwdh))
    out[cwdh_at + 8:cwdh_at + 8 + len(cwdh)] = cwdh
    out[cmap_at:cmap_at + 4] = magic(b"CMAP")
    struct.pack_into(e + "I", out, cmap_at + 4, 8 + len(body))
    out[cmap_at + 8:] = body
    return bytes(out)


WII = [("A", 6, (1, 6)), ("B", 6, (1, 6)), ("i", 3, (1, 6))]
SWITCH = [("A", 12, (2, 12)), ("B", 12, (2, 12)), ("i", 6, (2, 12)), ("Ж", 14, (2, 12)), ("э", 10, (5, 12)),
          ("Э", 12, (2, 12))]


def test_a_switch_font_reads_as_the_same_wii_font():
    assert font_port.as_rfnt(build_font(True, 15, 64, SWITCH, 12)) == build_font(False, 15, 64, SWITCH, 12)
    assert font_port.font_chars(build_font(True, 15, 64, SWITCH, 12)) == set("ABiЖэЭ")


def test_cyrillic_glyphs_are_copied_scaled_and_ukrainian_letters_aliased():
    wii = build_font(False, 7, 32, WII, 6)
    ported, report = font_port.port_glyphs(wii, build_font(True, 15, 64, SWITCH, 12))
    assert report == {"Ж": "copied", "є": "copied from э", "Є": "copied from Э", "і": "glyph of i"}
    meta, sheets = bcfnt.extract(ported, {})
    chars = char_map(meta)
    packets = meta["WID1"][0]["packets"]
    assert chars["і"] == chars["i"] and "э" not in chars and "ї" not in chars
    assert packets[chars["Ж"]]["width"] == 7          # 14 at the Latin advance ratio 6 / 12
    cell = font_port._cell(sheets, meta, chars["Ж"])
    assert cell.getbbox() is not None                  # the Switch pixels, scaled into the new cell
    again, _ = font_port.port_glyphs(ported, build_font(True, 15, 64, SWITCH, 12))
    assert again == ported                             # nothing left to copy: the font stays as it is


def test_ukrainian_text_is_normalised_and_written_for_each_font():
    text = "Вiдкрийте {escape:3:0000} i Wii, поïхали: э ЭТ"
    normal = font_port.normalize_ukrainian(text, messages.TAG_RE)
    assert normal == "Відкрийте {escape:3:0000} і Wii, поїхали: є ЄТ"
    assert font_port.normalize_ukrainian("Press i", messages.TAG_RE) == "Press i"   # no Cyrillic: as it is
    switch_font = set("ВдкрийтеWiпоxалїэЭТ ,:{}") - {"ї"} | {"i", "ï"}
    assert font_port.encode_for_font("ї є і ґ", switch_font) == "ï э i г"
    assert font_port.encode_for_font("ї є і", {"ї", "є", "і"}) == "ї є і"
