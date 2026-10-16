"""Silent Hill 1 (PAL disc): the menu and credit strings (NUL-terminated glyph runs) round-trip byte-exact."""
import pytest

import romhacking_root
from plugins.silent_hill_ps1 import pal_runs, pal_text


def test_run_is_found_with_its_room_and_text():
    raw = bytes([pal_text.byte_of("П"), pal_text.byte_of("О"), pal_text.byte_of("Ч"), pal_text.byte_of("А")])
    data = bytes([0x00] * 4) + raw + bytes([0x00] * 4)
    slots = pal_runs.find(data, [(0, len(data))])
    assert [(s.start, s.room, s.text) for s in slots] == [(4, 8, "ПОЧА")]


def test_edit_that_does_not_fit_is_refused():
    raw = bytes([pal_text.byte_of("П"), pal_text.byte_of("О"), pal_text.byte_of("Ч"), pal_text.byte_of("А")])
    data = bytes([0x00] * 4) + raw + bytes([0x00] * 4)
    out, problems = pal_runs.build(data, ["ПОЧАТИГРУ"], [(0, len(data))])
    assert out == data and problems


def test_real_menu_files_round_trip_byte_exact():
    folder = romhacking_root.under(r"Silent Hill\Silent Hill\Switch\source")
    if not folder.is_dir():
        pytest.skip("Silent Hill PAL source not here")
    checked = 0
    for rel in [r"1ST\BODYPROG.BIN", r"VIN\OPTION.BIN", r"VIN\SAVELOAD.BIN", r"VIN\STF_ROLL.BIN"]:
        data = (folder / rel).read_bytes()
        windows = pal_runs.windows_for(data)
        assert windows, rel
        texts = [s.text for s in pal_runs.find(data, windows)]
        assert texts, rel
        out, problems = pal_runs.build(data, texts, windows)
        assert problems == [] and out == data, rel
        checked += 1
    assert checked == 4
