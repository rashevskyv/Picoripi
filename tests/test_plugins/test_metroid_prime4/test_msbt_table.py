"""The translation import's view of an MSBT file (Metroid Prime 4 and Remastered share it): editor texts, label
ids, a refusal of other bytes, and a build that keeps every untouched message exactly."""
import struct

import pytest

from plugins.common.msbt import Msbt
from plugins.metroid_prime4.rules import GameRules


class _Fake:
    endian, little = "<", True


def _msbt(texts, labels=("First", "Second")):
    """A minimal little-endian UTF-16 MSBT: a label section (LBL1) and a text section (TXT2)."""
    bodies = [Msbt.encode_text(_Fake(), [text]) for text in texts]
    offsets, at = [], 4 + 4 * len(bodies)
    for body in bodies:
        offsets.append(at)
        at += len(body)
    txt2 = struct.pack(f"<I{len(bodies)}I", len(bodies), *offsets) + b"".join(bodies)
    entries = b"".join(bytes([len(name)]) + name.encode() + struct.pack("<I", index)
                       for index, name in enumerate(labels))
    lbl1 = struct.pack("<I", 1) + struct.pack("<II", len(labels), 12) + entries
    out = bytearray(b"MsgStdBn\xff\xfe\x00\x00\x01\x03\x02\x00" + bytes(16))
    for magic, body in ((b"LBL1", lbl1), (b"TXT2", txt2)):
        out += magic + struct.pack("<I", len(body)) + bytes(8) + body
        out += b"\xab" * (-len(out) % 16)
    struct.pack_into("<I", out, 0x12, len(out))
    return bytes(out)


def test_editor_texts_and_label_ids_and_untouched_build_is_byte_exact():
    raw = _msbt(["Hello", "World"])
    table = GameRules().parse_table(raw)
    assert table.texts() == ["Hello", "World"]
    assert table.ids() == ["First", "Second"]
    assert table.build(table.texts()) == raw


def test_a_translation_is_written_with_cyrillic_and_read_back():
    table = GameRules().parse_table(_msbt(["Hello", "World"]))
    translated = GameRules().parse_table(table.build(["Привіт", "World"]))
    assert translated.texts() == ["Привіт", "World"]


def test_a_text_count_that_differs_is_refused():
    table = GameRules().parse_table(_msbt(["Hello", "World"]))
    with pytest.raises(ValueError):
        table.build(["only one"])


@pytest.mark.parametrize("raw", [b"", b"plain text"])
def test_bytes_that_are_not_an_msbt_are_not_a_table(raw):
    assert GameRules().parse_table(raw) is None
