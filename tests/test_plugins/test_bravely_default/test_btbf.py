"""The BTBF codec on a synthetic table: string columns found by the row-major rule, text grows, numbers kept."""
import struct

import pytest

from plugins.bravely_default.btbf import Btbf, label_of
from plugins.bravely_default.rules import GameRules


def _table(rows, ascii_table=b""):
    """rows: [(id, text_a, number, text_b)] -> BTBF bytes with strings stored row by row."""
    strings, offsets = bytearray(), {}
    for row in rows:
        for text in (row[1], row[3]):
            offsets[(id(row), text)] = len(strings)
            strings += text.encode("utf-16-le") + b"\0\0"
    body = bytearray()
    for row in rows:
        body += struct.pack("<IIII", row[0], offsets[(id(row), row[1])], row[2], offsets[(id(row), row[3])])
    ascii_off = 0x30 + len(body)
    strings_off = ascii_off + len(ascii_table)
    strings_off += strings_off % 2
    header = struct.pack("<4s11I", b"BTBF", strings_off + len(strings), 0x30, len(body), ascii_off, len(ascii_table),
                         strings_off, len(strings), 16, len(rows), 0, 0)
    pad = bytes(strings_off - ascii_off - len(ascii_table))
    return bytes(header) + bytes(body) + ascii_table + pad + bytes(strings)


ROWS = [(1000, "Sword", 7, "A plain blade."), (1001, "", 0, "Nothing."), (1002, "Shield", 2, "")]


def test_reads_the_string_columns_and_round_trips():
    raw = _table(ROWS, b"Graphics/UI$_TL$/x\0")
    table = Btbf(raw)
    assert table.columns == [4, 12]
    assert table.texts == ["Sword", "A plain blade.", "", "Nothing.", "Shield", ""]
    assert table.build(list(table.texts)) == raw
    assert label_of(table, 3) == "row 1 field 3"


def test_longer_text_moves_the_offsets_and_keeps_the_numbers():
    raw = _table(ROWS)
    table = Btbf(raw)
    texts = list(table.texts)
    texts[0] = "Довгий меч"
    rebuilt = Btbf(table.build(texts))
    assert rebuilt.texts == texts
    assert rebuilt.columns == [4, 12]
    numbers = [struct.unpack_from("<I", rebuilt.raw, 0x30 + r * 16 + 8)[0] for r in range(3)]
    assert numbers == [7, 0, 2]
    assert rebuilt.size == len(rebuilt.raw)
    assert rebuilt.ascii_off == table.ascii_off and rebuilt.strings_off == table.strings_off


def test_rejects_other_files_and_wrong_counts():
    with pytest.raises(ValueError):
        Btbf(b"MsgStdBn" + bytes(0x30))
    table = Btbf(_table(ROWS))
    with pytest.raises(ValueError):
        table.build(["one"])


def test_rules_load_and_save_through_the_codec():
    raw = _table(ROWS)
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    assert names == {} and blocks == [["Sword", "A plain blade.", "", "Nothing.", "Shield", ""]]
    assert rules.save_data_to_json_obj(blocks, {}) == raw
    blocks[0][4] = "Щит"
    assert Btbf(rules.save_data_to_json_obj(blocks, {})).texts[4] == "Щит"
