"""DS NFTR font backend on a synthetic font: byte-exact round trips, edits in place, new characters added."""
import struct

import pytest
from PIL import Image

import romhacking_root
from core import font_formats
from core.containers.narc_members import narc_members
from core.font_formats import nftr

WHITE = (255, 255, 255, 255)
PARAMS = {"columns": 4, "spare": 4}


def _block(magic: bytes, body: bytes) -> bytes:
    body += bytes(-(len(body) + 8) % 4)
    return magic + struct.pack("<I", len(body) + 8) + body


def _font() -> bytes:
    """4x4 cells, 1 bpp (2 bytes a glyph): glyph 0 'A' (top row), glyph 1 'B' (left column), glyph 2 'Ё' in a
    table 0x401-0x405; one HDWC; PAMC direct 'A'-'B', the table, an empty scan list covering everything."""
    glyphs = [bytes([0xF0, 0x00]), bytes([0x88, 0x88]), bytes([0x66, 0x00])]
    plgc = _block(b"PLGC", struct.pack("<BBHbBBB", 4, 4, 2, 3, 4, 1, 0) + b"".join(glyphs))
    hdwc = _block(b"HDWC", struct.pack("<HHI", 0, 2, 0) + bytes([0, 4, 5, 1, 1, 3, 0, 4, 5]))
    maps = [_block(b"PAMC", struct.pack("<HHII", 0x41, 0x42, 0, 0) + struct.pack("<HH", 0, 0)),
            _block(b"PAMC", struct.pack("<HHII", 0x401, 0x405, 1, 0) + struct.pack("<5H", 2, *[0xFFFF] * 4)),
            _block(b"PAMC", struct.pack("<HHII", 0, 0xFFFF, 2, 0) + struct.pack("<H", 0))]
    finf_size = 0x20
    at = 16 + finf_size
    plgc_at, hdwc_at = at, at + len(plgc)
    map_at = [hdwc_at + len(hdwc)]
    for block in maps[:-1]:
        map_at.append(map_at[-1] + len(block))
    finf = b"FNIF" + struct.pack("<IBBHbBBBIIIBBBB", finf_size, 0, 5, 0, 0, 4, 5, 1, plgc_at + 8, hdwc_at + 8,
                                 map_at[0] + 8, 4, 4, 3, 0)
    linked = bytearray(b"".join(maps))
    offset = 0
    for index, block in enumerate(maps[:-1]):
        struct.pack_into("<I", linked, offset + 16, map_at[index + 1] + 8)
        offset += len(block)
    body = finf + plgc + hdwc + bytes(linked)
    return b"RTFN\xff\xfe\x02\x01" + struct.pack("<IHH", 16 + len(body), 16, 6) + body


def _cell(metadata, glyph):
    gly = metadata["GLY1"][0]
    x, y = (glyph % gly["glyph_horizontal_count"]) * 4, (glyph // gly["glyph_horizontal_count"]) * 4
    return x, y, x + 4, y + 4


def _add(metadata, char, glyph, kerning=0, width=4):
    entries = metadata["MAP1"][0]["entries"]
    half = len(entries) // 2
    entries.insert(half, font_formats.char_code(char))
    entries.append(glyph)
    metadata["WID1"][0]["packets"][glyph] = {"kerning": kerning, "width": width}


def test_detect_parse_and_build_round_trip():
    data = _font()
    assert font_formats.detect(data) == "nftr" and font_formats.adds_glyphs("nftr")
    font = nftr.Font(data)
    assert len(font.glyphs) == 3 and font.codes() == {0x41: 0, 0x42: 1, 0x401: 2}
    assert font.build() == data
    with pytest.raises(ValueError):
        nftr.Font(b"RFNT" + data[4:])


def test_extract_shows_every_glyph_and_packs_back_byte_exact():
    data = _font()
    metadata, sheets = font_formats.extract("nftr", data, PARAMS)
    assert sheets[0].size == (16, 8)                                  # 3 glyphs + 4 spare cells, 4 a row
    ink = sheets[0].getchannel("A")
    assert [ink.getpixel((x, 0)) for x in range(4)] == [255] * 4      # A: top row, bits most significant first
    assert [ink.getpixel((4, y)) for y in range(4)] == [255] * 4      # B: left column (rows run on)
    assert font_formats.font_map(metadata) == {"A": {"width": 5}, "B": {"width": 3}, "Ё": {"width": 5}}
    assert font_formats.pack("nftr", metadata, sheets, data, PARAMS) == data


def test_redrawn_glyph_and_widths_are_written_in_place():
    data = _font()
    metadata, sheets = font_formats.extract("nftr", data, PARAMS)
    sheets[0].putpixel((1, 3), WHITE)                                 # A gets a pixel in its last row
    metadata["WID1"][0]["packets"][1] = {"kerning": -1, "width": 2}
    packed = font_formats.pack("nftr", metadata, sheets, data, PARAMS)
    font = nftr.Font(packed)
    assert len(packed) == len(data)
    assert font.glyphs[0] == bytes([0xF0, 0x04])
    assert font.width_entries()[1] == (1, 1, 2)
    assert font.width_entries()[0] == (0, 4, 5)                       # redrawn: glyph width from its ink


def test_new_characters_get_glyphs_widths_and_codes():
    data = _font()
    metadata, sheets = font_formats.extract("nftr", data, PARAMS)
    sheets[0].paste(Image.new("RGBA", (2, 4), WHITE), (12, 0))        # cell 3
    sheets[0].paste(Image.new("RGBA", (3, 4), WHITE), (0, 4))         # cell 4
    _add(metadata, "Є", 3, kerning=-1, width=3)                       # in the Cyrillic table
    _add(metadata, "ґ", 4, width=4)                                   # in the scan list
    packed = font_formats.pack("nftr", metadata, sheets, data, PARAMS)
    font = nftr.Font(packed)
    assert len(font.glyphs) == 5 and font.glyphs[3] == bytes([0xCC, 0xCC])
    assert font.codes() == {0x41: 0, 0x42: 1, 0x401: 2, 0x404: 3, 0x491: 4}
    assert font.width_entries()[3] == (1, 2, 3) and font.width_entries()[4] == (0, 3, 4)
    assert len(font.widths) == 1 and len(font.maps) == 3              # grown in place, no new blocks
    assert font.build() == packed
    again, again_sheets = font_formats.extract("nftr", packed, PARAMS)
    assert font_formats.pack("nftr", again, again_sheets, packed, PARAMS) == packed
    assert font_formats.font_map(again)["Є"] == {"width": 3}


def test_a_code_no_block_covers_gets_a_new_scan_list():
    data = _font()
    font = nftr.Font(data)
    font.maps.pop()                                                    # no scan list covering everything
    font.order.pop()
    font.map_chain.pop()
    data = font.build()
    metadata, sheets = font_formats.extract("nftr", data, PARAMS)
    _add(metadata, "’", 3)
    packed = font_formats.pack("nftr", metadata, sheets, data, PARAMS)
    font = nftr.Font(packed)
    assert font.codes()[0x2019] == 3 and font.maps[-1][:3] == [0x2019, 0x2019, 2]


def test_existing_codes_cannot_change():
    data = _font()
    metadata, sheets = font_formats.extract("nftr", data, PARAMS)
    entries = metadata["MAP1"][0]["entries"]
    entries[len(entries) // 2] = 1                                     # 'A' -> glyph 1
    with pytest.raises(ValueError, match="U\\+0041"):
        font_formats.pack("nftr", metadata, sheets, data, PARAMS)


def test_a_block_whose_declared_size_leaves_out_its_padding_is_read_and_packs_back_unchanged():
    """Pokémon Black / White: the next block starts on a word although the block's size field stops before it."""
    data = bytearray(_font())
    plgc = data.index(b"PLGC")
    declared = struct.unpack_from("<I", data, plgc + 4)[0]
    assert declared % 4 == 0 and data[plgc + declared - 2:plgc + declared] == b"\0\0"
    struct.pack_into("<I", data, plgc + 4, declared - 2)
    data = bytes(data)
    font = nftr.Font(data)
    assert len(font.glyphs) == 3 and font.codes() == {0x41: 0, 0x42: 1, 0x401: 2}
    metadata, sheets = font_formats.extract("nftr", data, PARAMS)
    assert font_formats.pack("nftr", metadata, sheets, data, PARAMS) == data


# -- Gen 5 layout (Pokémon Black / White): widths in row 0 of each glyph, an HDWC block that is not a table ----

GEN5_PARAMS = {"columns": 4, "spare": 2}


def _gen5_font() -> bytes:
    """12 x 16 two-bit cells (48 bytes). Row 0 of each glyph holds (left, glyph width, advance); the HDWC block
    does not parse as a width table (first > last) and is kept as it is; one scan list of three codes."""
    glyphs = [bytes([0, 6, 6]) + bytes(45),                    # 0: 'A' with no ink (widths only)
              bytes([0, 2, 3, 0xC0]) + bytes(44),              # 1: 'i', ink at row 1 column 0
              bytes([1, 3, 5, 0x40]) + bytes(44)]              # 2: ',', ink at row 1 column 0, one to the right
    plgc = _block(b"PLGC", struct.pack("<BBHbBBB", 12, 16, 48, 14, 12, 2, 0) + b"".join(glyphs))
    hdwc = _block(b"HDWC", struct.pack("<HHI", 3339, 12, 16) + bytes(range(64)))
    pairs = [(0x2C, 2), (0x41, 0), (0x69, 1)]
    pamc = _block(b"PAMC", struct.pack("<HHII", 0x2C, 0x69, 2, 0) + struct.pack("<H", len(pairs))
                  + b"".join(struct.pack("<HH", *pair) for pair in pairs))
    plgc_at = 16 + 0x20
    hdwc_at = plgc_at + len(plgc)
    pamc_at = hdwc_at + len(hdwc)
    finf = b"FNIF" + struct.pack("<IBBHbBBBIIIBBBB", 0x20, 0, 15, 0, 0, 12, 12, 1, plgc_at + 8, hdwc_at + 8,
                                 pamc_at + 8, 4, 4, 3, 0)
    body = finf + plgc + hdwc + pamc
    return b"RTFN\xff\xfe\x01\x01" + struct.pack("<IHH", 16 + len(body), 16, 4) + body


def test_gen5_widths_are_row_zero_and_the_opaque_hdwc_is_kept_byte_exact():
    data = _gen5_font()
    font = nftr.Font(data)
    assert font.row0_widths and font.opaque_hdwc and font.width_chain == []
    assert font.width_entries() == {0: (0, 6, 6), 1: (0, 2, 3), 2: (1, 3, 5)}
    assert font.codes() == {0x41: 0, 0x69: 1, 0x2C: 2}
    assert font.raw[0][:4] == b"HDWC"
    assert font.build() == data
    assert not nftr.Font(_font()).row0_widths                         # a table font keeps its HDWC table


def test_gen5_extract_shows_the_widths_and_row_zero_is_not_ink():
    data = _gen5_font()
    metadata, sheets = font_formats.extract("nftr", data, GEN5_PARAMS)
    packets = metadata["WID1"][0]["packets"]
    assert packets[1] == {"kerning": 0, "width": 3} and packets[2] == {"kerning": -1, "width": 5}
    assert metadata["WID1"][0]["glyph_widths"][1] == 2
    ink = font_formats.coverage(sheets[0])
    assert all(ink.getpixel((x, 0)) == 0 for x in range(12))          # glyph 0: row 0 holds widths only
    assert ink.getpixel((12, 1)) != 0                                 # glyph 1: its ink at row 1
    assert font_formats.pack("nftr", metadata, sheets, data, GEN5_PARAMS) == data


def test_gen5_edited_width_and_glyph_round_trip_through_build_and_read():
    data = _gen5_font()
    metadata, sheets = font_formats.extract("nftr", data, GEN5_PARAMS)
    metadata["WID1"][0]["packets"][1] = {"kerning": 0, "width": 4}  # 'i' advances 4 px, not 3
    sheets[0].putpixel((12 + 5, 3), WHITE)                            # and gets ink at row 3, column 5
    packed = font_formats.pack("nftr", metadata, sheets, data, GEN5_PARAMS)
    assert len(packed) == len(data)
    font = nftr.Font(packed)
    assert font.width_entries()[1] == (0, 6, 4)                       # the width follows the new ink (0..5)
    assert font.raw == nftr.Font(data).raw                            # the HDWC block is untouched
    assert font.build() == packed
    again, again_sheets = font_formats.extract("nftr", packed, GEN5_PARAMS)
    assert again["WID1"][0]["packets"][1] == {"kerning": 0, "width": 4}
    assert font_formats.coverage(again_sheets[0]).getpixel((17, 3)) != 0
    assert font_formats.pack("nftr", again, again_sheets, packed, GEN5_PARAMS) == packed


def test_gen5_new_character_gets_its_widths_in_row_zero_and_no_table():
    data = _gen5_font()
    metadata, sheets = font_formats.extract("nftr", data, GEN5_PARAMS)
    sheets[0].paste(Image.new("RGBA", (3, 4), WHITE), (36, 1))        # cell 3: ink from row 1
    _add(metadata, "’", 3, width=4)
    packed = font_formats.pack("nftr", metadata, sheets, data, GEN5_PARAMS)
    font = nftr.Font(packed)
    assert len(font.glyphs) == 4 and font.width_entries()[3] == (0, 3, 4)
    assert font.codes()[0x2019] == 3 and font.widths == []
    assert font.build() == packed
    again, again_sheets = font_formats.extract("nftr", packed, GEN5_PARAMS)
    assert font_formats.pack("nftr", again, again_sheets, packed, GEN5_PARAMS) == packed


# -- real game fonts (skip without the workspace, PICORIPI_ROMHACKING) ----------------------------------------

_GEN5_FONTS = [("Pokemon", "Black and White"), ("Pokemon", "Black 2 and White 2")]
_REAL = {"columns": 16, "spare": 32}


def _real_font(game: tuple):
    parts = (*game, "source", "a", "0", "2", "3")
    reason = romhacking_root.missing(*parts)
    if reason:
        pytest.skip(reason)
    return narc_members(romhacking_root.path(*parts).read_bytes())[0]


@pytest.mark.parametrize("game", _GEN5_FONTS, ids=["black", "black_2"])
def test_real_gen5_message_font_reads_row_zero_widths_and_builds_byte_exact(game):
    data = _real_font(game)
    font = nftr.Font(data)
    assert font.row0_widths and font.opaque_hdwc
    assert font.build() == data
    entries = font.width_entries()
    assert entries[0] == (4, 0, 4) and entries[73] == (0, 2, 3) and entries[76] == (0, 3, 4)
    assert entries[12] == (1, 3, 5)                                   # the comma: one pixel right, advance 5
    metadata, sheets = font_formats.extract("nftr", data, _REAL)
    assert font_formats.font_map(metadata)["i"] == {"width": 3}
    assert font_formats.pack("nftr", metadata, sheets, data, _REAL) == data


@pytest.mark.parametrize("game", _GEN5_FONTS, ids=["black", "black_2"])
def test_real_gen5_edited_glyph_and_width_round_trip(game):
    data = _real_font(game)
    metadata, sheets = font_formats.extract("nftr", data, _REAL)
    glyph = 79                                                        # 'o' in Black: advance 6
    x, y = (glyph % 16) * 12, (glyph // 16) * 16
    sheets[0].putpixel((x + 2, y + 8), WHITE)
    metadata["WID1"][0]["packets"][glyph] = {"kerning": 0, "width": 5}
    packed = font_formats.pack("nftr", metadata, sheets, data, _REAL)
    assert len(packed) == len(data)
    font = nftr.Font(packed)
    assert font.width_entries()[glyph][2] == 5
    assert font.raw == nftr.Font(data).raw and font.build() == packed
    again, again_sheets = font_formats.extract("nftr", packed, _REAL)
    assert font_formats.coverage(again_sheets[0]).getpixel((x + 2, y + 8)) != 0
    assert again["WID1"][0]["packets"][glyph] == {"kerning": 0, "width": 5}
