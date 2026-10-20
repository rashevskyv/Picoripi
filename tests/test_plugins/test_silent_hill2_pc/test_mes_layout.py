"""Silent Hill 2 message table (read from word 1), the PC font charset, and the migration of rows saved before the fix.

All inputs are built here; no game data is read.
"""
import struct

import pytest

from plugins.silent_hill2_pc import mes, mes_legacy


def _rows_of(data):
    return [mes_legacy.legacy_decode(m) for m in mes_legacy.legacy_split(data)]


def test_table_is_count_then_offsets_and_message_zero_follows_it():
    data = mes.build([b"\x39\x45\x53\x0e", b"\x44\x45"])   # "Yes." and "De"
    assert struct.unpack_from("<3H", data, 0) == (2, 3, 5)  # count, message 0 at byte 6, message 1 at byte 10
    assert mes.table_starts(data) == [6, 10]
    assert mes.split(data) == [b"\x39\x45\x53\x0e", b"\x44\x45"]


def test_empty_file_and_bad_tables():
    assert mes.split(b"\x00\x00") == []
    with pytest.raises(ValueError):
        mes.split(b"\x05\x00\x04\x00")      # count 5 but no room for the table
    with pytest.raises(ValueError):
        mes.split(b"\x01\x00\x04\x00\xaa")  # message 0 must start right after the table (byte 4)


def test_pc_font_charset_shows_byte_plus_0x20():
    raw = bytes([0x39, 0x45, 0x53, 0x0E, 0x00, 0x07])   # "Yes." then a space and an apostrophe
    assert mes.decode(raw) == "Yes. '"
    assert mes.encode("Yes. '") == raw


def test_every_byte_round_trips_as_text_or_tag():
    for b in range(256):
        raw = bytes([b])
        assert mes.encode(mes.decode(raw)) == raw, b


def test_codes_and_undefined_cells_are_tags():
    assert mes.decode(bytes([0xFF, 0xFD, 0x5B, 0x5D, 0xE0])) == "{FF}{FD}{5B}{5D}{E0}"
    assert mes.decode(bytes([0x61])) == "{61}"          # 0x81 is undefined in Windows-1252


def test_text_outside_the_charset_is_refused():
    with pytest.raises(ValueError):
        mes.encode("ї")


def test_legacy_rows_migrate_to_the_messages_they_hold():
    messages = [b"\x00\x80\x39\x45\x53\x0e\xff\xff\x00\x80", b"\x00\x80\x2e\x4f\x0e\xff\xff\x00\x00\x00",
                b"\x00\x80\x29\x54\x07\x53\xff\xff\x00\x90"]
    data = mes.build(messages)
    rows = _rows_of(data)
    assert len(rows) == 3                   # the old reading: one row too many, the last row holds two messages
    new, notes = mes_legacy.migrate_rows(rows, mes_legacy.legacy_encode)
    assert new == messages
    assert new == mes.split(data)
    assert len(notes) == 2


def test_legacy_migration_of_one_and_two_messages():
    one = mes.build([b"\x00\x80\x39\x45\x53\x0e\xff\xff"])
    assert mes_legacy.migrate_rows(_rows_of(one), mes_legacy.legacy_encode)[0] == mes.split(one)
    two = mes.build([b"\x39\x45\x53\x0e", b"\x44\x45"])
    assert mes_legacy.migrate_rows(_rows_of(two), mes_legacy.legacy_encode)[0] == [b"\x39\x45\x53\x0e", b"\x44\x45"]


def test_migration_takes_the_translation_codec_for_translation_rows():
    translation = mes.build([bytes([0x6D, 0xCC]), bytes([0x8E, 0x8E]), bytes([0x96, 0xCC, 0x9D, 0xCF])])
    rows = [mes.decode_uk(m) for m in mes_legacy.legacy_split(translation)]
    new, _ = mes_legacy.migrate_rows(rows, mes.encode_uk)
    assert [mes.decode_uk(m) for m in new] == ["Ні", "оо", "цієї"]
