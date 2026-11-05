from core.bfn_core import BfnCore

def test_bfn_core_pack_unpack_lifecycle():
    bfn = BfnCore()
    bfn.signature = "FFNT1bnd"
    
    # 1. Fill mock INF1
    bfn.inf1 = [{
        "encoding": 0,  # CP1252
        "ascent": 22,
        "descent": 2,
        "width": 24,
        "leading": 2,
        "fallback_code": 63,
        "unk1": 0
    }]
    
    # 2. Fill mock GLY1
    bfn.gly1 = [{
        "start_glyph": 0,
        "end_glyph": 10,
        "cell_width": 24,
        "cell_height": 24,
        "page_data_size": 256,
        "texture_format": 0,
        "glyph_horizontal_count": 5,
        "glyph_vertical_count": 2,
        "texture_width": 128,
        "texture_height": 128,
        "sheets_binary": [b'\x00' * 256]
    }]
    
    # 3. Fill mock MAP1 (mapping type 2, range 32 to 42)
    bfn.map1 = [{
        "mapping_type": 2,
        "first_char": 32,
        "last_char": 42,
        "mapping_entry_count": 11,
        "entries": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    }]
    
    # 4. Fill mock WID1
    bfn.wid1 = [{
        "first_code_included": 32,
        "last_code_included": 42,
        "packets": [
            {"kerning": 0, "width": 8},   # index 0 (space)
            {"kerning": 1, "width": 10},  # index 1
            {"kerning": -1, "width": 12}, # index 2
            {"kerning": 0, "width": 14},  # index 3
            {"kerning": 2, "width": 16},  # index 4
            {"kerning": 0, "width": 10},  # index 5
            {"kerning": 0, "width": 10},  # index 6
            {"kerning": 0, "width": 10},  # index 7
            {"kerning": 0, "width": 10},  # index 8
            {"kerning": 0, "width": 10},  # index 9
            {"kerning": 0, "width": 10}   # index 10
        ]
    }]
    
    # Pack to bytes
    bfn_bytes = bfn.save()
    assert isinstance(bfn_bytes, bytes)
    assert len(bfn_bytes) > 0
    
    # Unpack from bytes
    bfn_verify = BfnCore()
    bfn_verify.load(bfn_bytes)
    
    # Assert signature and count
    assert bfn_verify.signature == "FFNT1bnd"
    assert bfn_verify.num_chunks == 4
    
    # Assert INF1
    assert len(bfn_verify.inf1) == 1
    assert bfn_verify.inf1[0]["ascent"] == 22
    assert bfn_verify.inf1[0]["width"] == 24
    
    # Assert GLY1
    assert len(bfn_verify.gly1) == 1
    assert bfn_verify.gly1[0]["cell_width"] == 24
    assert bfn_verify.gly1[0]["texture_width"] == 128
    
    # Assert MAP1
    assert len(bfn_verify.map1) == 1
    assert bfn_verify.map1[0]["mapping_type"] == 2
    assert bfn_verify.map1[0]["first_char"] == 32
    assert bfn_verify.map1[0]["entries"] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    
    # Assert WID1
    assert len(bfn_verify.wid1) == 1
    assert bfn_verify.wid1[0]["first_code_included"] == 32
    assert bfn_verify.wid1[0]["packets"][2]["kerning"] == -1
    assert bfn_verify.wid1[0]["packets"][2]["width"] == 12

def test_bfn_core_to_font_map_conversion():
    bfn = BfnCore()
    bfn.inf1 = [{"width": 12}]
    bfn.map1 = [{
        "mapping_type": 2,
        "first_char": 32,
        "last_char": 35,
        "mapping_entry_count": 3,
        "entries": [32, 33, 34]
    }]
    bfn.wid1 = [{
        "first_code_included": 32,
        "last_code_included": 35,
        "packets": [
            {"kerning": 0, "width": 8},   # code 32 (space ' ')
            {"kerning": 1, "width": 10},  # code 33 (exclamation '!')
            {"kerning": -1, "width": 15}  # code 34 (quotes '"')
        ]
    }]
    
    # Without translation map overrides
    font_map = bfn.to_font_map()
    
    assert " " in font_map  # deslop: ignore[poor-substring-tests] dict key check: the font map is keyed by character
    assert font_map[" "]["width"] == 8
    assert "!" in font_map  # deslop: ignore[poor-substring-tests] dict key check: the font map is keyed by character
    assert font_map["!"]["width"] == 10
    
    # With translation map (map Ukranian 'і' [U+0456] to CP1252 '!' [code 33])
    translation_map = {
        "і": "!"
    }
    font_map_with_ukr = bfn.to_font_map(translation_map)
    
    # The Ukranian letter 'і' must dynamically inherit the width of CP1252 '!' (10 pixels)
    assert "і" in font_map_with_ukr  # deslop: ignore[poor-substring-tests] single non-ASCII glyph marker: the Ukrainian letter must be in the font map
    assert font_map_with_ukr["і"]["width"] == 10

def test_bfn_core_get_sheets_qimages():
    bfn = BfnCore()
    
    # 1. Test empty gly1 returns empty list
    assert bfn.get_sheets_qimages() == []
    
    # Reset cached value to test GLY1 loading properly
    bfn._qimages_cache = None
    
    # 2. Setup mock GLY1 with single 8x8 I4 texture sheet (each tile 8x8 pixels)
    bfn.gly1 = [{
        "start_glyph": 0,
        "end_glyph": 0,
        "cell_width": 8,
        "cell_height": 8,
        "page_data_size": 32, # 8x8 pixels at 4bpp (I4) = 64 pixels = 32 bytes
        "texture_format": 0,  # I4
        "glyph_horizontal_count": 1,
        "glyph_vertical_count": 1,
        "texture_width": 8,
        "texture_height": 8,
        "sheets_binary": [b'\x5A' * 32] # mock filled sheet
    }]
    
    sheets = bfn.get_sheets_qimages()
    assert len(sheets) == 1
    assert sheets[0].width() == 8
    assert sheets[0].height() == 8
    # I4: the high nibble is the left texel, drawn white with alpha = intensity (0x5 * 17, 0xA * 17)
    from PyQt6.QtGui import QColor
    assert QColor.fromRgba(sheets[0].pixel(0, 0)).getRgb() == (85, 85, 85, 85)
    assert QColor.fromRgba(sheets[0].pixel(1, 0)).getRgb() == (170, 170, 170, 170)
    
    # Check cached retrieval
    sheets_cached = bfn.get_sheets_qimages()
    assert sheets is sheets_cached


def test_a_shift_jis_font_maps_two_byte_codes_and_draws_ascii_full_width():
    """Luigi's Mansion's dialogue font: MAP1 holds only Shift-JIS codes; JUTResFont draws ASCII with them."""
    from core.bfn_core import char_glyphs
    map1 = [{"mapping_type": 2, "first_char": 0x8260, "last_char": 0x8261, "entries": [5, 6]},   # Ａ Ｂ
            {"mapping_type": 3, "first_char": 0x8140, "last_char": 0x8446, "entries": [0x8140, 0x8446, 0, 9]}]

    assert char_glyphs(map1, 2) == {"Ａ": 5, "Ｂ": 6, "A": 5, "B": 6, "　": 0, " ": 0, "Ё": 9}
    assert char_glyphs(map1[:1], 0) == {chr(0x8260): 5, chr(0x8261): 6}
    quotes = [{"mapping_type": 3, "first_char": 0x8166, "last_char": 0x8168, "entries": [0x8166, 0x8168, 7, 8]}]
    assert char_glyphs(quotes, 2) == {"’": 7, "”": 8, "'": 7, '"': 8}   # halftofull: ' -> ’, " -> ”


def test_a_table_map_whose_count_field_is_not_its_size_reads_one_glyph_per_code():
    import struct
    body = struct.pack(">HHHH", 2, 0x8260, 0x8262, 118) + struct.pack(">3H", 4, 5, 6) + bytes(10)
    chunk = b"MAP1" + struct.pack(">I", 8 + len(body)) + body
    data = b"FONTbfn1" + struct.pack(">II", 32 + len(chunk), 1) + bytes(16) + chunk
    bfn = BfnCore()

    bfn.load(data)

    assert bfn.map1[0]["entries"] == [4, 5, 6] and bfn.map1[0]["mapping_entry_count"] == 118
