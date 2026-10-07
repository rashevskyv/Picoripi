"""Smoke tests for the Paper Mario: Color Splash plugin on a small big-endian MSBT built here."""
import struct

from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "paper_mario_cs"


def _msbt(*texts: bytes) -> bytes:
    """A big-endian UTF-16 MSBT with one TXT2 section."""
    offsets, body = [], b""
    for text in texts:
        offsets.append(4 + 4 * len(texts) + len(body))
        body += text + b"\0\0"
    section = struct.pack(">I", len(texts)) + b"".join(struct.pack(">I", o) for o in offsets) + body
    section = b"TXT2" + struct.pack(">I", len(section)) + bytes(8) + section
    section += b"\xab" * (-len(section) % 16)
    header = b"MsgStdBn\xfe\xff\0\0\x01\x03" + struct.pack(">HHI", 1, 0, 0x20 + len(section)) + bytes(10)
    return header + section


def _tag(group: int, kind: int, params: bytes) -> bytes:
    return struct.pack(">HHHH", 0x0E, group, kind, len(params)) + params


# {select:0:1:0:300:yesno} is option group 3, tag 0; {wait:30} is scroll group 4, tag 4
SELECT = _tag(3, 0, struct.pack(">hhhhH", 0, 1, 0, 300, 10) + "yesno".encode("utf-16-be"))
SAMPLE = _msbt("Go to the world map?".encode("utf-16-be") + SELECT,
               "Wait".encode("utf-16-be") + _tag(4, 4, struct.pack(">H", 30)) + "\nend".encode("utf-16-be"))


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_tags_are_named_and_an_unchanged_file_is_written_back_byte_for_byte():
    from plugins.paper_mario_cs.rules import GameRules
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert blocks == [["Go to the world map?{select:0:1:0:300:yesno}", "Wait{wait:30}\nend"]]
    assert rules.save_data_to_json_obj(blocks, names) == SAMPLE
    assert rules.tag_manager.is_tag_legitimate("{wait:30}")
    assert not rules.tag_manager.is_tag_legitimate("{wait}")


def test_the_validator_passes():
    check_validator(PLUGIN)
