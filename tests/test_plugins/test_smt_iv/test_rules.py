"""Shin Megami Tensei IV plugin: MSG2 tables and executable strings (synthetic and the real games)."""
import struct
from pathlib import Path

import pytest

from core.font_formats import sjis
from plugins.smt_iv import codebin, mbm
from plugins.testing import check_loads, check_validator, load_rules

PLUGIN = "smt_iv"
GAMES = [Path(r"E:\Emulators\RomHacking\Shin Megami Tensei\IV\source"),
         Path(r"E:\Emulators\RomHacking\Shin Megami Tensei\IV Apocalypse\source")]


def make_table(entries, gap=b"\xAA" * 12, tail=b"\0" * 8):
    """An MSG2 table of raw strings (``b""`` = empty entry), with bytes between the table and the strings."""
    table = b""
    strings = b""
    at = 0x20 + len(entries) * 16 + len(gap)
    for i, raw in enumerate(entries):
        table += struct.pack("<4I", i, len(raw), at + len(strings) if raw else 0, 0)
        strings += raw
    body = table + gap + strings
    return bytes(4) + b"MSG2" + struct.pack("<4I", 0x10000, 0x20 + len(table) + len(strings), len(entries), 0x20) + bytes(8) + body + tail


HELLO = bytes.fromhex("82 67 82 85 82 8c 82 8c 82 8f f8 01 82 60 f8 7a 01 00 ff ff")   # Hello␤A{F87A 0001}
SAMPLE = make_table([HELLO, b"", bytes.fromhex("82 78 82 85 82 93 ff ff")])


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_decode_shows_ascii_newlines_and_tags():
    assert mbm.decode(HELLO) == "Hello\nA{F87A 0001}"
    assert mbm.encode("Hello\nA{F87A 0001}") == HELLO
    assert mbm.encode("") == b"\xff\xff"


def test_ukrainian_letters_take_the_free_shift_jis_codes():
    text = "Ґалка і їжак"
    raw = mbm.encode(text)
    assert raw[:2] == bytes.fromhex("8492") and mbm.decode(raw) == text
    assert sjis.decode(sjis.encode("ї")) == "ї"
    assert sjis.encode("A") == 0x41 and sjis.decode(0x8260) == "Ａ"


def test_table_rebuilds_byte_for_byte_and_grows():
    table = mbm.Table(SAMPLE)
    texts = table.texts()
    assert texts == ["Hello\nA{F87A 0001}", "", "Yes"]
    assert table.build(texts) == SAMPLE
    texts[2] = "Yes, a longer answer"
    again = mbm.Table(table.build(texts))
    assert again.texts() == texts
    assert struct.unpack_from("<I", again.raw, 0x0C)[0] == struct.unpack_from("<I", SAMPLE, 0x0C)[0] + 34


def test_executable_strings_are_edited_in_place():
    code = b"\0" * 16 + bytes.fromhex("82 60 82 87 82 89") + b"\0\0" + bytes.fromhex("82 62 82 85 82 8c") + b"\0" * 10
    assert codebin.texts(code) == ["Agi", "Cel"]
    out = codebin.build(code, ["Ag", "Cel"])
    assert len(out) == len(code) and codebin.texts(out) == ["Ag", "Cel"]
    with pytest.raises(codebin.FormatError):
        codebin.build(code, ["Agilao", "Cel"])


def test_plugin_load_and_save_round_trip():
    rules = load_rules(PLUGIN)
    blocks, _names = rules.load_data_from_json_obj(SAMPLE)
    assert blocks == [["Hello\nA{F87A 0001}", "", "Yes"]]
    assert rules.save_data_to_json_obj(blocks, {}) == SAMPLE


@pytest.mark.parametrize("root", GAMES, ids=["smt4", "apocalypse"])
def test_every_real_table_rebuilds_byte_for_byte(root):
    if not root.is_dir():
        pytest.skip("the unpacked game is not on this machine")
    files = sorted(root.glob("**/*.mbm"))
    assert len(files) > 1000
    for path in files:
        raw = path.read_bytes()
        table = mbm.Table(raw)
        texts = table.texts()
        assert table.build(texts) == raw, path.name
        for entry, text in zip(table.entries, texts):
            assert mbm.encode(text) == entry or (text == "" and entry == b""), (path.name, text)
    code = (root / "exefs" / "code.bin").read_bytes()
    texts = codebin.texts(code)
    assert len(texts) > 500 and codebin.build(code, texts) == code
