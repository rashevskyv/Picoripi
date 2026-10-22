import struct

import pytest

from plugins.luigis_mansion_1_3ds import build
from plugins.luigis_mansion_1_3ds.gmsg import RECORD, Table
from plugins.luigis_mansion_1_3ds.gmsg import encode
from plugins.luigis_mansion_1_3ds.rules import GameRules

END = b"\x7f\x00\x00\x00"   # every text ends with the end code


def _gmsg(messages, version=3):
    """A GMSG file of ``messages`` (editor texts): the header (20 bytes), 16-byte records, texts aligned to 4 bytes."""
    table, start = 0x14, 0x14 + 16 * len(messages)
    body, records = bytearray(), bytearray()
    for index, text in enumerate(messages):
        raw = encode(text) if text else b""
        if raw:
            body += b"\x00" * (-(start + len(body)) % 4)
            records += RECORD.pack(index + 1, 0, start + len(body), len(raw))
            body += raw
        else:
            records += RECORD.pack(index + 1, 0, 0, 0)
    head = struct.pack("<4sIIII", b"GMSG", version, 2, len(messages), table)
    return head + bytes(records) + bytes(body)


def _write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_unchanged_table_builds_the_original_bytes():
    raw = _gmsg(["Hello", "", "Bye now"])
    table = Table(raw)
    assert table.texts() == ["Hello", "", "Bye now"]
    assert table.ids() == ["1", "2", "3"]
    assert table.build(table.texts()) == raw


def test_an_edited_text_keeps_the_ids_and_the_other_messages():
    raw = _gmsg(["Hello", "", "Bye now"])
    table = Table(Table(raw).build(["Hello there", "", "Bye now"]))
    assert table.texts() == ["Hello there", "", "Bye now"]
    assert table.ids() == ["1", "2", "3"]


def test_a_changed_message_count_is_refused():
    with pytest.raises(ValueError, match="texts"):
        Table(_gmsg(["Hello"])).build(["Hello", "extra"])


def test_a_file_that_is_not_version_3_is_not_a_table():
    assert GameRules().parse_table(_gmsg(["Hello"], version=2)) is None
    assert GameRules().parse_table(b"not a message file") is None


def test_only_the_english_tables_are_selected():
    assert build.select_english("romfs/Region_US/English/main.gmsg")
    assert build.select_english(r"romfs\Region_US\English\UIMansion.gar")
    assert not build.select_english("romfs/Region_US/French/main.gmsg")
    assert not build.select_english("exefs/code.bin")


def test_changed_files_refuses_a_table_with_another_message_count(tmp_path):
    src, trn = tmp_path / "src", tmp_path / "trn"
    _write(src / "romfs/Region_US/English/main.gmsg", _gmsg(["Hello", "Bye"]))
    _write(trn / "romfs/Region_US/English/main.gmsg", _gmsg(["Hello"]))
    with pytest.raises(ValueError, match="number of messages"):
        build.changed_files(src, trn)


def test_build_layeredfs_writes_only_the_changed_table_under_the_title(tmp_path):
    src, trn = tmp_path / "src", tmp_path / "trn"
    raw = _gmsg(["Hello", "Bye"])
    _write(src / "romfs/Region_US/English/main.gmsg", raw)
    _write(src / "romfs/Region_US/English/UIMansion.gar", b"GAR\x05")
    edited = Table(raw).build(["Hi", "Bye"])
    _write(trn / "romfs/Region_US/English/main.gmsg", edited)

    out = build.build_layeredfs(str(src), str(trn), str(tmp_path / "out"), lambda p, t: None, lambda: False)

    romfs = tmp_path / "out/titles/00040000001D1900/romfs"
    assert out.replace("\\", "/").endswith("titles/00040000001D1900/romfs")
    assert (romfs / "Region_US/English/main.gmsg").read_bytes() == edited
    assert sorted(p.name for p in romfs.rglob("*") if p.is_file()) == ["main.gmsg"]


def test_control_codes_with_the_argument_sizes_of_this_game_round_trip():
    from plugins.luigis_mansion_1_3ds.gmsg import decode

    text = "Hi\n{clear}Press {c11:0600} now{style:" + "00" * 16 + "}{c15:03000000}{c08:01000000}."
    raw = encode(text)
    assert decode(raw) == text
