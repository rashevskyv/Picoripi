"""Luigi's Mansion (GameCube): the dialogue font inside sys/main.dol, the Ukrainian letters in messages, and the build
that carries a changed main.dol. Synthetic bytes only; no game file is read."""
import struct

import pytest

from plugins.luigis_mansion_1_gc import build, messages
from plugins.luigis_mansion_1_gc.dol_font import DOL_SIZE, FONT_AT, FONT_MAGIC, MEMBER, DolFont

FONT_SIZE = 64


def _font(payload: bytes = b"\x11") -> bytes:
    return FONT_MAGIC + struct.pack(">I", FONT_SIZE) + payload * (FONT_SIZE - 12)


def _dol(font: bytes = None) -> bytes:
    data = bytearray(DOL_SIZE)
    data[:4] = b"\x00\x00\x01\x00"
    data[FONT_AT:FONT_AT + FONT_SIZE] = font or _font()
    return bytes(data)


def test_recognises_only_this_executable():
    assert DolFont.can_handle(_dol())
    assert not DolFont.can_handle(_dol()[:-1])
    assert not DolFont.can_handle(b"\x00\x00\x01\x00" + bytes(DOL_SIZE - 4))


def test_member_reads_the_font_and_writes_in_place():
    dol = _dol()
    container = DolFont(dol)
    assert container.list_files() == [MEMBER]
    assert container.read_file(MEMBER) == _font()
    container.write_file(MEMBER, _font(b"\x22"))
    out = container.pack()
    assert len(out) == DOL_SIZE
    assert out[FONT_AT:FONT_AT + FONT_SIZE] == _font(b"\x22")
    assert out[:FONT_AT] == dol[:FONT_AT] and out[FONT_AT + FONT_SIZE:] == dol[FONT_AT + FONT_SIZE:]


def test_member_never_grows():
    with pytest.raises(ValueError, match="room for"):
        DolFont(_dol()).write_file(MEMBER, bytes(FONT_SIZE + 1))


def test_ukrainian_letters_round_trip_through_the_message_table():
    table = messages.Table(b"Hello\r\nWorld\r\n")
    raw = table.build(["Їжак Ґанок", "єнот і ґудзик"])
    assert "Ё".encode("cp932") in raw          # the Ґ slot is the unused cp932 Cyrillic code
    assert messages.Table(raw).texts() == ["Їжак Ґанок", "єнот і ґудзик"]


def test_unchanged_message_table_returns_the_original_bytes():
    table = messages.Table(b"Hello\r\n")
    assert table.build(["Hello"]) == b"Hello\r\n"


def test_changed_executable_is_in_the_build_changes(tmp_path):
    source, translation = tmp_path / "source", tmp_path / "translation"
    for root in (source, translation):
        (root / "sys").mkdir(parents=True)
    (source / "sys" / "main.dol").write_bytes(_dol())
    (translation / "sys" / "main.dol").write_bytes(_dol(_font(b"\x33")))
    changes = build.changed_files(source, translation)
    assert list(changes) == ["sys/main.dol"]
    assert changes["sys/main.dol"] == _dol(_font(b"\x33"))


def test_dash_and_guillemets_take_the_nearest_shift_jis_mark():
    table = messages.Table(b"one\r\n")
    raw = table.build(["a \u2014 b \u00abc\u00bb"])
    assert messages.Table(raw).texts() == ["a \u2015 b \u201cc\u201d"]
