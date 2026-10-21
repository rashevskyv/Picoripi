"""Okami HD plugin: the MSD codec, the atlas character table, the text layer and the rules (synthetic data only).

The sections here have the disc layout: every record starts on a 4-byte boundary and every section is a multiple of 16
bytes (the pad is zero bytes, which read back as empty strings). The last test reads the owner's extracted Switch files
when ``PICORIPI_ROMHACKING`` names the workspace; it skips otherwise.
"""
import struct

import pytest

from plugins.okami_hd import charset, msd, textfile
import romhacking_root
from plugins.okami_hd.rules import GameRules

LIST_HEADER = bytes.fromhex("01000000 0c000000 00000000")
ME51 = (0x8203, 0x6D65, 0x3531)     # the bytes 03 82 65 6d 31 35: the "me51" record header


def units(*values):
    return b"".join(struct.pack("<H", v) for v in values)


def strings_bytes(*strings):
    """Raw bytes of 0x0000-terminated strings given as unit lists."""
    return b"".join(units(*s) + b"\x00\x00" for s in strings)


def pad(raw, multiple):
    return raw + b"\x00" * (-len(raw) % multiple)


def list_section(*strings):
    return pad(LIST_HEADER + strings_bytes(*strings), 16)


def table_section(records):
    """records: list of (header_units, [unit strings]). Layout: u16 count, u16 X, (u32 offset, u32 0) x count."""
    count = len(records)
    chunks = [pad(units(*header) + strings_bytes(*strings), 4) for header, strings in records]
    offsets = []
    position = 4 + 8 * count
    for chunk in chunks:
        offsets.append(position)
        position += len(chunk)
    chunks[-1] += b"\x00" * (-position % 16)
    table = struct.pack("<HH", count, 0x28) + b"".join(struct.pack("<II", offset, 0) for offset in offsets)
    return table + b"".join(chunks)


def container(sections):
    """sections: list of (tag, raw bytes). Header: u32 count, u32 offsets, 4-byte tags; the header and every section are
    padded to 16 bytes, as on the disc."""
    count = len(sections)
    starts = []
    position = len(pad(b"\x00" * (4 + 8 * count), 16))
    for _tag, raw in sections:
        starts.append(position)
        position += len(pad(raw, 16))
    out = bytearray(struct.pack("<I", count))
    for value in starts:
        out += struct.pack("<I", value)
    for tag, _raw in sections:
        out += tag.encode("ascii").ljust(4, b"\x00")
    out = pad(bytes(out), 16)
    for _tag, raw in sections:
        out += pad(raw, 16)
    return bytes(out)


def record_starts_ok(raw):
    """Every section starts and ends on 16 bytes; every record of every MSD section starts on 4 bytes."""
    parsed = msd.parse_container(raw)
    if any(start % 16 or (end - start) % 16 for start, end in parsed.spans):
        return False
    for index, tag in enumerate(parsed.tags):
        if tag != "MSD":
            continue
        section = msd.parse_section(parsed.section_bytes(index))
        position = len(section.prefix)
        for record in section.records:
            if position % 4 or record.byte_length() % 4:
                return False
            position += record.byte_length()
    return True


# -- character table ---------------------------------------------------------------

def test_letter_codes_match_the_atlas_grid():
    assert charset.CODE_TO_CHAR[0x44] == "t"       # cell 71
    assert charset.CODE_TO_CHAR[0x35] == "e"       # cell 56
    assert charset.CODE_TO_CHAR[0x2a] == "T"
    assert charset.CODE_TO_CHAR[0x29] == "S"
    assert charset.CODE_TO_CHAR[0x2d] == "W"
    assert charset.CODE_TO_CHAR[0x17] == "A"
    assert charset.CODE_TO_CHAR[0x18] == "B"
    assert charset.CODE_TO_CHAR[0x19] == "C"
    assert charset.CODE_TO_CHAR[charset.APOSTROPHE] == "'"


def test_punctuation_codes_are_the_atlas_cells_not_a_space():
    assert charset.decode(units(0x01, 0x02, 0x03, 0x04, 0x0A, 0xC6)) == ".,?!'-"
    assert charset.encode(".,?!'-") == units(0x01, 0x02, 0x03, 0x04, 0x0A, 0xC6)
    assert 0x0001 not in [code for code, char in charset.CODE_TO_CHAR.items() if char == " "]
    with pytest.raises(ValueError):
        charset.encode("a b")                       # a space is a string break, never a code


def test_line_break_code_is_a_newline_in_the_text():
    assert charset.decode(units(0xA001)) == "\n"
    assert charset.encode("\n") == units(0xA001)
    assert charset.encode("{a001}") == units(0xA001)


def test_ukrainian_slots_are_66_unique_cells_with_letters():
    assert len(charset.UK_SLOT_CODES) == len(charset.UKRAINIAN_LETTERS) == 66
    assert len(set(charset.UK_SLOT_CODES)) == 66
    assert charset.CODE_TO_CHAR[charset.UK_SLOT_CODES[0]] == "А"          # А
    assert charset.CODE_TO_CHAR[charset.UK_SLOT_CODES[-1]] == "я"       # я
    assert charset.encode("Ґґ") == struct.pack("<HH", charset.UK_SLOT_CODES[4], charset.UK_SLOT_CODES[37])


def test_atlas_cell_of_a_code():
    assert charset.atlas_cell(0x44) == (4, 7)      # 't' is cell 71 = 4 * 16 + 7


def test_text_round_trip_is_exact_for_any_units():
    raw = units(0x44, 0x38, 0x35, 0x01, 0x0A, 0xA301, 0x0002, 0x0000, 0xFFFF)
    text = charset.decode(raw)
    assert "the" in text and "{a301}" in text and "{ffff}" in text
    assert charset.encode(text) == raw


def test_encode_refuses_a_character_the_atlas_does_not_show():
    with pytest.raises(ValueError):
        charset.encode("中")


# -- MSD layouts -------------------------------------------------------------------

def test_list_section_rebuilds_exactly():
    raw = list_section([0x44, 0x38, 0x35], [0x31])
    section = msd.parse_section(raw)
    assert section.layout == "list"
    assert msd.strings_of(section)[:2] == [units(0x44, 0x38, 0x35), units(0x31)]
    assert section.serialize() == raw


def test_table_section_rebuilds_exactly():
    raw = table_section([
        ([*ME51, 0xD201], [[0x44, 0x38, 0x35], [0x31, 0x3E, 0x34]]),
        ([0x8103], [[0x31, 0x46, 0x35], [0x3F, 0x36]]),
    ])
    section = msd.parse_section(raw)
    assert section.layout == "table"
    assert len(section.records) == 2
    assert section.serialize() == raw


def test_header_rule_keeps_a_letter_that_starts_a_record():
    # 'K' 'a' 'm' 'i' 'k' 'i' with no header: the first letter is text, not a header (it was lost before)
    raw = table_section([([], [[0x21, 0x31, 0x3D, 0x39, 0x3B, 0x39]])])
    assert textfile.read_text(container([("MSD", raw)])) == ["Kamiki"]


def test_one_unit_control_header_is_not_shown():
    raw = table_section([([0x8103], [[0x44, 0x38, 0x35]])])
    assert textfile.read_text(container([("MSD", raw)])) == ["the"]


def test_unknown_section_is_not_parsed():
    assert msd.parse_section(b"\x00\x01\x00\x00\x00\x00\x00\x0c") is None


def test_replace_strings_keeps_record_lengths_or_refuses():
    raw = table_section([([*ME51, 0xD201], [[0x44, 0x38, 0x35]])])
    section = msd.parse_section(raw)
    old = msd.strings_of(section)                                  # the pad strings are in the list too
    same = msd.replace_strings(section, [units(0x31, 0x3E, 0x34)] + old[1:])
    assert same.serialize() != raw and len(same.serialize()) == len(raw)
    with pytest.raises(msd.MsdError):
        msd.replace_strings(section, [units(0x31, 0x3E)] + old[1:])   # length changed
    with pytest.raises(msd.MsdError):
        msd.replace_strings(section, [])                           # count changed


# -- text layer --------------------------------------------------------------------

def test_container_read_and_write_text_round_trip():
    data = container([
        ("ACT", b"\x11" * 32),
        ("MSD", list_section([0x44, 0x38, 0x35], [0x2A, 0x35])),
        ("ROF", b"\x22" * 16),
    ])
    texts = textfile.read_text(data)
    assert texts == ["the Te"]                 # one row per record; the two strings are joined by a space
    rebuilt, warnings = textfile.write_text(data, texts)
    assert rebuilt == data and warnings == []


def test_a_space_in_a_row_is_a_string_break():
    data = container([("MSD", list_section([0x44, 0x38, 0x35]))])
    edited, warnings = textfile.write_text(data, ["tee and"])
    assert warnings == []
    assert textfile.read_text(edited) == ["tee and"]
    assert msd.strings_of(msd.parse_section(msd.parse_container(edited).section_bytes(0)))[:2] == [
        units(0x44, 0x35, 0x35), units(0x31, 0x3E, 0x34)]


def test_line_break_round_trips_and_keeps_the_disc_layout():
    data = container([("MSD", list_section([0x44, 0x38, 0x35], [0x31]))])
    edited, warnings = textfile.write_text(data, ["one\ntwo of the land."])
    assert warnings == []
    assert textfile.read_text(edited) == ["one\ntwo of the land."]
    assert record_starts_ok(edited)


def test_growth_keeps_record_and_section_alignment():
    raw = table_section([
        ([*ME51, 0xD201], [[0x44, 0x38, 0x35]]),
        ([0x8103], [[0x31, 0x3E, 0x34], [0x44, 0x38, 0x35]]),
        ([0x8103], [[0x31]]),
    ])
    data = container([("MSD", raw), ("MST", b"\x33" * 48)])
    assert record_starts_ok(data)
    for grown_text in ("theeeee", "t", "theeeeeeeeeeeeeeeee"):
        texts = textfile.read_text(data)
        texts[1] = f"{grown_text} and the"                    # the middle record grows, shrinks, grows
        edited, warnings = textfile.write_text(data, texts)
        assert warnings == []
        assert record_starts_ok(edited)
        assert textfile.read_text(edited) == texts
        assert msd.parse_container(edited).section_bytes(1) == b"\x33" * 48  # the other section keeps its bytes


def container_with_rof(msd_raw):
    """ACT, MSD and a ROF section whose RUNOFS64 table holds the three section starts."""
    act = b"\x11" * 32
    placeholder = container([("ACT", act), ("MSD", msd_raw), ("ROF", b"RUNOFS64" + b"\x00" * 24)])
    starts = [start for start, _end in msd.parse_container(placeholder).spans]
    rof = b"RUNOFS64" + b"".join(struct.pack("<Q", value) for value in starts)
    return container([("ACT", act), ("MSD", msd_raw), ("ROF", rof)])


def test_growth_moves_offsets_and_runofs_starts_and_reads_back():
    data = container_with_rof(list_section([0x44, 0x38, 0x35], [0x31]))
    edited, warnings = textfile.write_text(data, ["theeeeeeeeeeeeeeeee a"])
    assert warnings == []
    assert len(edited) % 16 == 0 and len(edited) > len(data)
    assert textfile.read_text(edited) == ["theeeeeeeeeeeeeeeee a"]
    parsed = msd.parse_container(edited)
    starts = [start for start, _end in parsed.spans]
    rof = parsed.section_bytes(2)
    assert [struct.unpack_from("<Q", rof, 8 + 8 * j)[0] for j in range(3)] == starts
    assert parsed.section_bytes(0) == b"\x11" * 32       # the untouched section is the same bytes


def test_a_section_never_shrinks_below_the_length_it_was_loaded_with():
    data = container_with_rof(table_section([([*ME51, 0xD201], [[0x44, 0x38, 0x35]])]))
    grown, _ = textfile.write_text(data, ["theeeee"])
    back, warnings = textfile.write_text(grown, ["the"])
    assert warnings == []
    assert textfile.read_text(back) == ["the"]
    assert len(back) == len(grown)


def test_write_text_refuses_a_changed_row_count():
    data = container([("MSD", list_section([0x44], [0x35]))])
    same, warnings = textfile.write_text(data, ["t", "e"])
    assert same == data and warnings


def test_file_without_messages_has_no_text():
    data = container([("ACT", b"\x00" * 24)])
    assert textfile.read_text(data) == []
    assert textfile.write_text(data, [])[0] == data


# -- rules -------------------------------------------------------------------------

def test_rules_load_and_save_keep_the_bytes_when_nothing_changes():
    data = container([("MSD", list_section([0x44, 0x38, 0x35]))])
    rules = GameRules()
    lines, block_names = rules.load_data_from_json_obj(data)
    assert lines == [["the"]] and block_names == {"0": "messages"}
    assert rules.save_data_to_json_obj(lines, block_names) == data


def test_rules_identify_refuses_a_non_switch_file(tmp_path):
    other = tmp_path / "game.bin"
    other.write_bytes(b"not a switch image")
    from plugins.okami_hd import unpack
    assert unpack.identify(str(other)) is None


def test_build_writes_only_the_changed_files_into_the_layeredfs_romfs(tmp_path):
    from plugins.okami_hd import build
    source = tmp_path / "source" / "data" / "st1"
    translation = tmp_path / "translation" / "data" / "st1"
    source.mkdir(parents=True)
    translation.mkdir(parents=True)
    original = container([("MSD", list_section([0x44, 0x38, 0x35]))])
    edited, warnings = textfile.write_text(original, ["tee"])
    assert warnings == []
    (source / "r101.bin").write_bytes(original)
    (translation / "r101.bin").write_bytes(edited)
    (translation / "r102.bin").write_bytes(original)          # same as the source: not a change
    (source / "r102.bin").write_bytes(original)
    out = tmp_path / "out"
    build.build_switch(str(tmp_path / "source"), str(tmp_path / "translation"), str(out),
                       lambda done, text: None, lambda: False)
    romfs = out / "atmosphere" / "contents" / "0100276009872000" / "romfs" / "data" / "st1"
    assert (romfs / "r101.bin").read_bytes() == edited
    assert not (romfs / "r102.bin").exists()


def dds_bc7_file(image, mips, pad=0):
    """A DX10 BC7 DDS (size as given, ``mips`` levels) placed after ``pad`` filler bytes."""
    from PIL import Image
    from core.texture_formats import pixels
    codec = pixels.codec("BC7")
    header = bytearray(148)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<II", header, 12, image.size[1], image.size[0])
    struct.pack_into("<I", header, 28, mips)
    header[84:88] = b"DX10"
    struct.pack_into("<I", header, 128, 98)
    body = bytearray()
    level = image
    for _ in range(mips):
        body += codec.encode(level)
        level = level.resize((max(1, level.size[0] // 2), max(1, level.size[1] // 2)), Image.Resampling.LANCZOS)
    return b"\x7f" * pad + bytes(header) + bytes(body)


def test_dds_bc7_reads_at_an_offset_and_writes_back_exactly():
    from PIL import Image
    from core.texture_formats import dds
    source = Image.new("RGBA", (16, 16), (200, 40, 40, 255))
    data = dds_bc7_file(source, 2, pad=32)
    texture = dds.read(data, {"offset": 32})[0]
    assert texture.image.size == (16, 16) and texture.mipmaps == 2 and texture.pixel_format == "BC7"
    assert dds.write(data, {0: texture.image}, {"offset": 32}) == data


def test_dds_bc7_changes_only_the_changed_blocks_of_level_zero():
    from PIL import Image
    from core.texture_formats import dds
    data = dds_bc7_file(Image.new("RGBA", (16, 16), (200, 40, 40, 255)), 1)
    image = dds.read(data, {})[0].image.copy()
    image.paste(Image.new("RGBA", (4, 4), (0, 255, 0, 255)), (8, 8))      # the block at column 2, row 2
    out = dds.write(data, {0: image}, {})
    assert len(out) == len(data)
    base = 148
    blocks = [i for i in range(0, 16 * 16 // 16) if data[base + 16 * i:base + 16 * i + 16] != out[base + 16 * i:base + 16 * i + 16]]
    assert blocks == [2 * 4 + 2]
    assert dds.read(out, {})[0].image.getpixel((9, 9))[1] > 200


def test_real_switch_files_rebuild_exactly():
    reason = romhacking_root.missing("Okami", "Okami", "Switch", "source", "data", "st1", "r101.bin")
    if reason:
        pytest.skip(reason)
    data = romhacking_root.path("Okami", "Okami", "Switch", "source", "data", "st1", "r101.bin").read_bytes()
    texts = textfile.read_text(data)
    assert len(texts) == 47                        # one row per record of st1/r101.bin
    rebuilt, warnings = textfile.write_text(data, texts)
    assert rebuilt == data and warnings == []
    assert any("Celestial" in text for text in texts)
