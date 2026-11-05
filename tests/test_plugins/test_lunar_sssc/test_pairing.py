"""Lunar SSS Remastered: pairing the JP and EN messages of one TEXT file by bytecode skeleton (synthetic scripts)."""
import struct

from plugins.lunar_sssc import script
from plugins.lunar_sssc.pairing import pair_messages


def _script(*code: bytes) -> bytes:
    labels = struct.pack("<1024H", *([script.HEADER // 2] + [0] * 1023))
    return labels + b"".join(code)


def _message(*text: int) -> bytes:
    body = struct.pack("<H", script.MESSAGE) + bytes(text) + b"\xff"
    return body + (b"\x00" if len(body) % 2 else b"")  # messages are padded to an even length


def _other() -> bytes:
    return struct.pack("<HH", 4, 0)  # an instruction of 4 bytes that is not text and not an end


_END = struct.pack("<H", 5) + b"\x00\x00"


def test_same_skeleton_pairs_every_message_in_order():
    en = _script(_message(0x01), _message(0x02), _END)
    jp = _script(_message(0x01, 0x03), _message(0x04), _END)
    pairs, en_only, jp_only = pair_messages(en, jp)
    assert pairs == [(0, 0), (1, 1)]
    assert en_only == [] and jp_only == []


def test_extra_message_is_unpaired_when_an_instruction_anchors_the_skeleton():
    en = _script(_message(0x01), _other(), _message(0x02), _END)
    jp = _script(_message(0x01), _message(0x09), _other(), _message(0x02), _END)
    pairs, en_only, jp_only = pair_messages(en, jp)
    assert pairs == [(0, 0), (1, 2)]
    assert en_only == [] and jp_only == [1]
