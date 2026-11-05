"""Metal Gear + Metal Gear 2 Master Collection (PC): the plugin's document save and the text units of english.raw.

The unit tests use synthetic bytes; the real-data tests read the install file and skip when it is missing.
"""
from pathlib import Path

import pytest

import romhacking_root

from core import english_raw
from plugins.metal_gear_12_mc.rules import FORMAT, GameRules

INSTALL = romhacking_root.under(r'Metal Gear\Metal Gear 1 and 2\PC\ISO\game\fr\stage\mg1\cache\english.raw')
# three records: flag 00, length, text (the lengths match the text)
RECORDS = b"\x00\x00\x0bHello world" + b"\x00\x00\x07Hi thee" + b"\x00\x00\x06Thanks"


def _document(lines):
    return {"format": FORMAT, "version": 1, "game": "MG1",
            "blocks": [{"name": "english.raw", "lines": lines}]}


def _need(path):
    if not path.is_file():
        pytest.skip(f"no install file at {path}")
    return path.read_bytes()


def test_document_save_keeps_the_lines_and_the_block_name():
    rules = GameRules()
    data, names = rules.load_data_from_json_obj(_document(["Hello world", "Hi thee"]))
    assert data == [["Hello world", "Hi thee"]]
    assert names == {"0": "english.raw"}
    saved = rules.save_data_to_json_obj([["Bye", "Hi"]], names)
    assert saved["format"] == FORMAT
    assert saved["blocks"] == [{"name": "english.raw", "lines": ["Bye", "Hi"]}]


def test_text_units_read_synthetic_records_with_their_budgets():
    units = english_raw.text_units(RECORDS, start=0)
    assert units == [(3, 11, b"Hello world"), (17, 7, b"Hi thee"), (27, 6, b"Thanks")]


def test_apply_units_pads_shorter_text_and_moves_nothing():
    out = english_raw.apply_units(RECORDS, [b"Bye", b"Hi", b"Go"], start=0)
    assert len(out) == len(RECORDS)
    assert out == (b"\x00\x00\x0bBye" + b" " * 8 + b"\x00\x00\x07Hi" + b" " * 5
                   + b"\x00\x00\x06Go" + b" " * 4)


def test_apply_units_refuses_a_text_longer_than_its_budget():
    with pytest.raises(ValueError):
        english_raw.apply_units(RECORDS, [b"Hello there!", b"Hi", b"Go"], start=0)


def test_text_units_round_trip_the_install_file():
    data = _need(INSTALL)
    units = english_raw.text_units(data)
    assert english_raw.apply_units(data, [text for _, _, text in units]) == data


def test_shared_zt_copy_is_the_core_module():
    copy = romhacking_root.under('_shared\\scripts\\zt\\english_raw.py')
    if not copy.is_file():
        pytest.skip("no shared zt copy on this machine")
    assert copy.read_bytes() == Path(english_raw.__file__).read_bytes()
