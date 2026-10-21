"""Okami HD plugin: the MSD codec, the atlas character table, the text layer and the rules (synthetic data only).

The last test reads the owner's extracted Switch files when ``PICORIPI_ROMHACKING`` names the workspace; it skips
otherwise.
"""
import struct

import pytest

from plugins.okami_hd import charset, msd, textfile
import romhacking_root
from plugins.okami_hd.rules import GameRules

LIST_HEADER = bytes.fromhex("01000000 0c000000 00000000")


def units(*values):
    return b"".join(struct.pack("<H", v) for v in values)


def strings_bytes(*strings):
    """Raw bytes of 0x0000-terminated strings given as unit lists."""
    return b"".join(units(*s) + b"\x00\x00" for s in strings)


def list_section(*strings, tail=b""):
    return LIST_HEADER + strings_bytes(*strings) + tail


def table_section(records):
    """records: list of (header_units, [unit strings]). Layout: u16 count, u16 X, (u32 offset, u32 0) x count."""
    count = len(records)
    table_end = 4 + 8 * count
    body = bytearray()
    offsets = []
    for header, strings in records:
        offsets.append(table_end + len(body))
        body += units(*header) + strings_bytes(*strings)
    table = bytearray(struct.pack("<HH", count, 0x28))
    for offset in offsets:
        table += struct.pack("<II", offset, 0)
    return bytes(table) + bytes(body)


def container(sections):
    """sections: list of (tag, raw bytes). Header: u32 count, u32 offsets, 4-byte tags, then the sections."""
    count = len(sections)
    header_size = 4 + 8 * count
    out = bytearray(struct.pack("<I", count))
    offset = header_size
    offsets = []
    for _tag, raw in sections:
        offsets.append(offset)
        offset += len(raw)
    for value in offsets:
        out += struct.pack("<I", value)
    for tag, _raw in sections:
        out += tag.encode("ascii").ljust(4, b"\x00")
    for _tag, raw in sections:
        out += raw
    return bytes(out)


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
    assert charset.CODE_TO_CHAR[charset.SPACE] == " "
    assert charset.CODE_TO_CHAR[charset.APOSTROPHE] == "'"


def test_atlas_cell_of_a_code():
    assert charset.atlas_cell(0x44) == (4, 7)      # 't' is cell 71 = 4 * 16 + 7


def test_text_round_trip_is_exact_for_any_units():
    raw = units(0x44, 0x38, 0x35, 0x01, 0x0A, 0xA301, 0x0002, 0x0000, 0xFFFF)
    text = charset.decode(raw)
    assert "the" in text and "{a301}" in text and "{ffff}" in text
    assert charset.encode(text) == raw


def test_encode_refuses_a_character_the_atlas_does_not_show():
    with pytest.raises(ValueError):
        charset.encode("Ж")


# -- MSD layouts -------------------------------------------------------------------

def test_list_section_rebuilds_exactly():
    raw = list_section([0x44, 0x38, 0x35], [0x31], [], tail=b"\x07")
    section = msd.parse_section(raw)
    assert section.layout == "list"
    assert [len(s) for s in msd.strings_of(section)] == [6, 2, 0]
    assert section.serialize() == raw


def test_table_section_rebuilds_exactly():
    raw = table_section([
        ([0x8203, 0x6D65, 0x3531, 0x001F], [[0x44, 0x38, 0x35], [0x31, 0x3E, 0x34]]),
        ([0x0019], [[0x31, 0x46, 0x35], [0x3F, 0x36]]),
    ])
    section = msd.parse_section(raw)
    assert section.layout == "table"
    assert len(section.records) == 2
    assert len(msd.strings_of(section)) == 4
    assert section.serialize() == raw


def test_unknown_section_is_not_parsed():
    assert msd.parse_section(b"\x00\x01\x00\x00\x00\x00\x00\x0c") is None


def test_replace_strings_keeps_record_lengths_or_refuses():
    raw = table_section([([0x8203, 0x6D65, 0x3531, 0x001F], [[0x44, 0x38, 0x35]])])
    section = msd.parse_section(raw)
    same = msd.replace_strings(section, [units(0x31, 0x3E, 0x34)])
    assert same.serialize() != raw and len(same.serialize()) == len(raw)
    with pytest.raises(msd.MsdError):
        msd.replace_strings(section, [units(0x31, 0x3E)])          # length changed
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
    assert texts == ["the", "Te"]
    rebuilt, warnings = textfile.write_text(data, texts)
    assert rebuilt == data and warnings == []


def test_write_text_applies_a_same_length_edit_without_a_warning():
    data = container([("MSD", list_section([0x44, 0x38, 0x35], [0x31, 0x3E, 0x34]))])
    edited, warnings = textfile.write_text(data, ["tee", "and"])
    assert warnings == []
    assert textfile.read_text(edited) == ["tee", "and"]


def container_with_rof(msd_raw):
    """ACT, MSD and a ROF section whose RUNOFS64 table holds the three section starts."""
    act = b"\x11" * 32
    base = 4 + 8 * 3
    rof_start = base + len(act) + len(msd_raw)
    starts = [base, base + len(act), rof_start]
    rof = b"RUNOFS64" + b"".join(struct.pack("<Q", value) for value in starts)
    return container([("ACT", act), ("MSD", msd_raw), ("ROF", rof)])


def test_growth_moves_offsets_and_runofs_starts_and_reads_back():
    data = container_with_rof(list_section([0x44, 0x38, 0x35], [0x31]))
    edited, warnings = textfile.write_text(data, ["theeeee", "a"])
    assert warnings and "not yet proven" in warnings[0]
    assert len(edited) == len(data) + 8                  # four more units in the first string
    assert textfile.read_text(edited) == ["theeeee", "a"]
    parsed = msd.parse_container(edited)
    starts = [start for start, _end in parsed.spans]
    rof = parsed.section_bytes(2)
    assert [struct.unpack_from("<Q", rof, 8 + 8 * j)[0] for j in range(3)] == starts
    assert parsed.section_bytes(0) == b"\x11" * 32       # the untouched section is the same bytes


def test_growth_then_shrink_back_is_the_original_file():
    data = container_with_rof(table_section([([0x8203, 0x6D65, 0x3531, 0x001F], [[0x44, 0x38, 0x35]])]))
    grown, _ = textfile.write_text(data, ["theeeee"])
    back, warnings = textfile.write_text(grown, ["the"])
    assert back == data
    assert warnings


def test_write_text_refuses_a_changed_string_count():
    data = container([("MSD", list_section([0x44], [0x35]))])
    same, warnings = textfile.write_text(data, ["t"])
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


def test_real_switch_files_rebuild_exactly():
    reason = romhacking_root.missing("Okami", "Okami", "Switch", "source", "data", "st1", "r101.bin")
    if reason:
        pytest.skip(reason)
    data = romhacking_root.path("Okami", "Okami", "Switch", "source", "data", "st1", "r101.bin").read_bytes()
    texts = textfile.read_text(data)
    assert len(texts) > 1000
    rebuilt, warnings = textfile.write_text(data, texts)
    assert rebuilt == data and warnings == []
    assert any(text.startswith("Celestial") for text in texts)
