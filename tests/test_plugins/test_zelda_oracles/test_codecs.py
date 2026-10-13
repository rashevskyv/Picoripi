"""Oracle of Ages / Seasons codecs on synthetic bytes (no game data): markup, text spans, font, port cache."""
import pytest

from plugins.zelda_oracles import font, port_cache, rom, text
from plugins.zelda_oracles.rom import GameLayout


def _layout(count=2, font_offset=0x4000):
    return GameLayout(
        key="test",
        sha1="0" * 40,
        text_base1_table=0x100,
        text_base2_table=0x103,
        language_table=0x106,
        text_base2_index_start=0x2C,
        last_group_size=count,
        font_offset=font_offset,
    )


def _build_text_rom(strings, layout):
    """A 1 MB ROM with one high index holding ``strings`` (bytes), laid out for ``layout``.

    The text index table sits at bank 1; the group table and the strings sit in base bank 2.
    """
    data = bytearray(rom.ROM_SIZE)
    # Language table: reversed pointer (16-bit, then bank) to the text index table at bank 1.
    table = 0x4000 + 0x0100
    data[layout.language_table] = table & 0xFF
    data[layout.language_table + 1] = table >> 8
    data[layout.language_table + 2] = 1
    # Base 1 and base 2: bank byte, then 16-bit pointer (base address = bank * 0x4000 + pointer).
    base = 2 * 0x4000 + 0x0400
    for pointer_at in (layout.text_base1_table, layout.text_base2_table):
        data[pointer_at] = 2
        data[pointer_at + 1] = (0x0400) & 0xFF
        data[pointer_at + 2] = 0x04
    # Index table: 0x64 entries of 16-bit offsets from the text index table. Entry 0 points at the
    # group table; the rest point at the same place so they add no extra group.
    group_table = 0x0200  # offset from the index table
    for high in range(0x64):
        data[table + 2 * high] = group_table & 0xFF
        data[table + 2 * high + 1] = group_table >> 8
    # Group table: offsets from the text base to each string.
    position = base
    group_at = table + group_table
    offsets = []
    for s in strings:
        offsets.append(position - base)
        data[position:position + len(s)] = s
        position += len(s)
    for entry, offset in enumerate(offsets):
        data[group_at + 2 * entry] = offset & 0xFF
        data[group_at + 2 * entry + 1] = offset >> 8
    return data, base, offsets


def test_identify_rejects_other_bytes():
    with pytest.raises(rom.UnknownRom):
        rom.identify(bytes(100))
    with pytest.raises(rom.UnknownRom):
        rom.identify(bytes(rom.ROM_SIZE))


def test_known_usa_hashes_are_the_port_hashes():
    assert rom.LAYOUTS["880374fb978b18af4aa529e2e32f7ffb4d7dd2f4"].key == "ages"
    assert rom.LAYOUTS["ba1268290fb2b1b70505d2d7b5825fc8a4816a4b"].key == "seasons"


@pytest.mark.parametrize("markup", [
    "You got \\col(1)1 Rupee\\col(0)!\n...",
    "\\pos(2)\\slow()Hi\\stop",
    "Press \\abtn or \\bbtn to jump\\opt()",
    "Symbols \\heart\\up\\down\\rectangle",
    "Item \\item(0x00) and \\sym(0x10)",
    "Wait\\wait(30)\\speed(1)",
    "Hi \\Link, \\Child",
    "Plain \\x80\\x7f text",
])
def test_markup_round_trips_through_bytes(markup):
    data = text.from_markup(markup)
    assert data[-1] == 0
    assert text.from_markup(text.to_markup(data[:-1]) ) == data


def test_markup_uses_index_for_jump_and_call():
    data = text.from_markup("\\jump(TX_0010)", index=0x0410)
    assert data == bytes([0x07, 0x10, 0x00])
    assert text.to_markup(data[:-1], 0x0410) == "\\jump(TX_0010)"
    with pytest.raises(text.TextError):
        text.from_markup("\\call(TX_0110)", index=0x0410)


def test_unknown_tag_and_non_ascii_are_refused():
    with pytest.raises(text.TextError):
        text.from_markup("\\nope")
    with pytest.raises(text.TextError):
        text.from_markup("é")


def test_text_tables_read_synthetic_strings():
    strings = [b"Hi\x00", b"You\x01Go\x00", b"End\x00"]
    layout = _layout(count=len(strings))
    data, base, offsets = _build_text_rom(strings, layout)
    tables = text.TextTables(bytes(data), layout)
    spans = tables.spans
    assert [s.length for s in spans] == [3, 7, 4]
    assert all(s.terminated for s in spans)
    assert tables.raw(spans[0]) == b"Hi\x00"
    assert tables.expand(spans[1]) == b"You\x01Go\x00"
    assert tables.span(spans[0].index) is spans[0]


def test_replace_text_fits_in_place_and_refuses_longer():
    layout = _layout(count=2)
    data, base, _ = _build_text_rom([b"Hi\x00", b"Later\x00"], layout)
    tables = text.TextTables(bytes(data), layout)
    first = tables.spans[0]
    rom_bytes = bytearray(data)
    text.replace_text(rom_bytes, first, b"Yo\x00")
    assert rom_bytes[first.start:first.start + 3] == b"Yo\x00"
    assert rom_bytes[first.start + 3:first.end + 1] == data[first.start + 3:first.end + 1]
    with pytest.raises(text.TextError):
        text.replace_text(rom_bytes, first, b"Too long\x00")
    with pytest.raises(text.TextError):
        text.replace_text(rom_bytes, first, b"no terminator")


def test_span_is_isolated_when_no_other_string_starts_inside():
    layout = _layout(count=2)
    data, base, _ = _build_text_rom([b"Hi\x00", b"Later\x00"], layout)
    tables = text.TextTables(bytes(data), layout)
    assert all(tables.is_isolated(span) for span in tables.spans)


def test_font_round_trip_through_png(tmp_path):
    font_bytes = bytes((i * 37) & 0xFF for i in range(font.FONT_BYTES))
    path = tmp_path / "font.png"
    font.export_png(font_bytes, str(path))
    assert font.import_png(str(path)) == font_bytes


def test_glyph_rows_match_bits():
    glyph = bytes([0b10000001] + [0] * 7 + [0b01000000] + [0] * 7)
    rows = font.glyph_rows(glyph)
    assert rows[0] == [1, 0, 0, 0, 0, 0, 0, 1]
    assert rows[8] == [0, 1, 0, 0, 0, 0, 0, 0]
    assert font.rows_to_glyph(rows) == glyph


def test_write_font_replaces_only_the_font_block():
    layout = _layout(font_offset=0x100)
    rom_bytes = bytearray(b"\x11" * 0x2000)
    font.write_font(rom_bytes, layout, bytes(font.FONT_BYTES))
    assert rom_bytes[0x100:0x100 + font.FONT_BYTES] == bytes(font.FONT_BYTES)
    assert rom_bytes[0x0FF] == 0x11 and rom_bytes[0x100 + font.FONT_BYTES] == 0x11


def test_port_cache_takes_data_bytes_and_refuses_code():
    clean = bytearray(b"ABCDEFGH")
    cache = bytearray(clean)
    cache[2] = 0  # code byte, zeroed by the port
    translated = bytearray(clean)
    translated[5] = ord("x")  # data byte
    patched = port_cache.apply_translation(bytes(clean), bytes(translated), bytes(cache))
    assert patched[5] == ord("x") and patched[2] == 0
    translated[2] = ord("y")  # code byte: refused
    with pytest.raises(port_cache.CacheConflict):
        port_cache.apply_translation(bytes(clean), bytes(translated), bytes(cache))


def test_port_cache_check_counts_zeroed_code():
    clean = bytes(b"ABCD")
    cache = bytes(b"A\x00C\x00")
    assert port_cache.check_cache(clean, cache) == 2
    with pytest.raises(port_cache.CacheConflict):
        port_cache.check_cache(clean, b"Z\x00CD")


def test_reference_specials_map_european_and_russian_bytes():
    from plugins.zelda_oracles import reference

    assert reference._eu_special(0x80) == "À"  # A grave
    assert reference._eu_special(0x8C) == "Ö"  # O umlaut
    assert reference._eu_special(0x93) is None  # "?" in the table: shown as \xNN
    assert reference._ru_special(0xD2) == "Т"  # cyrillic capital TE
    assert reference._ru_special(0x98) is None  # not a cp1251 letter
    assert text.to_markup(bytes([0x41, 0x80]), 0, reference._eu_special) == "AÀ"
    assert text.to_markup(bytes([0x41, 0x80])) == "A\\x80"


def test_third_base_and_language_pointers_are_used():
    layout = GameLayout(
        key="test-eu", sha1="0" * 40, text_base1_table=0x100, text_base2_table=0x103, language_table=0x106,
        text_base2_index_start=0x1A, last_group_size=2, font_offset=None,
        text_base3_table=0x109, text_base3_index_start=0x34,
    )
    data = bytearray(rom.ROM_SIZE)
    # Language 0 and 1 share the same pointer layout; language 1 points the index table at bank 2.
    for language, bank in ((0, 1), (1, 2)):
        at = layout.language_table + 3 * language
        data[at:at + 3] = bytes([0x00, bank * 0x40, bank])  # reversed pointer: 16-bit, then bank
        for base_at in (layout.text_base1_table, layout.text_base2_table, layout.text_base3_table):
            data[base_at + 4 * language:base_at + 4 * language + 3] = bytes([bank, 0x10, 0x00])
    tables = text.TextTables(bytes(data), layout, language=1)
    assert tables.language == 1
    assert rom.read_bank_pointer(bytes(data), layout.text_base3_table + 4) == 2 * 0x4000 + 0x10
