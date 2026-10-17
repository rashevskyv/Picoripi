"""Wind Waker HD message pack: identify it, unpack its message files, and the plugin's Project Manager hooks.

The pack is built here as a SARC whose members are Yaz0 SARCs, the layout of permanent_2d_UsEnglish.pack.
Synthetic bytes only; no game file is read.
"""
import struct

import pytest

from core.containers import yaz0
from plugins.zelda_ww import message_pack
from plugins.zelda_ww.rules import GameRules


def _sarc(files: dict) -> bytes:
    """A big-endian SARC holding ``files`` ({name: bytes}), laid out the way Sarc reads it."""
    names_blob = bytearray()
    offsets = []
    for name in files:
        offsets.append(len(names_blob) // 4)
        raw = name.encode("utf-8") + b"\0"
        names_blob += raw + b"\0" * (-len(raw) % 4)
    count = len(files)
    names_base = 0x14 + 12 + count * 16 + 8
    data_offset = (names_base + len(names_blob) + 0x1F) // 0x20 * 0x20
    data = bytearray()
    nodes = bytearray()
    for offset, blob in zip(offsets, files.values()):
        start = (len(data) + 0x0F) // 0x10 * 0x10
        data += b"\0" * (start - len(data)) + blob
        nodes += struct.pack(">IIII", 0, 0x01000000 | offset, start, start + len(blob))
    header = b"SARC" + struct.pack(">H", 0x14) + b"\xfe\xff" + struct.pack(">II", data_offset + len(data), data_offset)
    header += b"\x01\x00\x00\x00"
    sfat = b"SFAT" + struct.pack(">HHI", 12, count, 0x65) + bytes(nodes)
    sfnt = b"SFNT" + struct.pack(">HH", 8, 0)
    body = header + sfat + sfnt + bytes(names_blob)
    return body + b"\0" * (data_offset - len(body)) + bytes(data)


def _pack(messages: dict) -> bytes:
    """The English pack shape: member ``<X>_msbt.szs`` is a Yaz0 SARC holding ``<X>.msbt``."""
    members = {f"{stem}_msbt.szs": yaz0.compress(_sarc({f"{stem}.msbt": data}))
               for stem, data in messages.items()}
    return _sarc(members)


def _write(path, data: bytes):
    path.write_bytes(data)
    return str(path)


def _quiet(*_):
    return None


def test_identify_accepts_the_english_pack_by_name_and_header(tmp_path):
    path = _write(tmp_path / message_pack.PACK_NAME, _pack({"Hello": b"MSG1"}))

    assert message_pack.is_english_pack(path)


def test_identify_refuses_another_name_or_a_file_without_the_sarc_header(tmp_path):
    other = _write(tmp_path / "permanent_2d_UsFrench.pack", _pack({"Hello": b"MSG1"}))
    fake = _write(tmp_path / message_pack.PACK_NAME, b"not a pack")

    assert not message_pack.is_english_pack(other)
    assert not message_pack.is_english_pack(fake)


def test_unpack_writes_each_message_file_under_the_message_folder(tmp_path):
    path = _write(tmp_path / message_pack.PACK_NAME, _pack({"Hello": b"MSG-ONE", "Bye": b"MSG-TWO"}))
    target = tmp_path / "unpacked"
    target.mkdir()
    progress = []

    result = message_pack.unpack_messages(path, str(target), lambda pct, name: progress.append((pct, name)),
                                          lambda: False)

    assert result == str(target)
    assert (target / "Message" / "Hello.msbt").read_bytes() == b"MSG-ONE"
    assert (target / "Message" / "Bye.msbt").read_bytes() == b"MSG-TWO"
    assert progress[-1] == (100, "Hello_msbt.szs")


def test_unpack_refuses_a_file_that_is_not_a_sarc(tmp_path):
    path = _write(tmp_path / message_pack.PACK_NAME, b"ZIP-OR-WUA-DATA")
    target = tmp_path / "unpacked"
    target.mkdir()

    with pytest.raises(ValueError, match="not a Wind Waker HD message pack"):
        message_pack.unpack_messages(path, str(target), _quiet, lambda: False)


def test_a_cancel_returns_none_without_a_result(tmp_path):
    path = _write(tmp_path / message_pack.PACK_NAME, _pack({"Hello": b"MSG-ONE"}))
    target = tmp_path / "unpacked"
    target.mkdir()

    assert message_pack.unpack_messages(path, str(target), _quiet, lambda: True) is None


def test_the_plugin_declares_wii_u_and_unpacks_into_the_message_folder(tmp_path):
    rules = GameRules()
    path = _write(tmp_path / message_pack.PACK_NAME, _pack({"Hello": b"MSG-ONE"}))
    target = tmp_path / "unpacked"
    target.mkdir()

    assert [platform["id"] for platform in rules.get_platforms()] == ["wiiu"]
    assert rules.identify_source(path) == {"role": "base", "platform": "wiiu"}
    assert rules.identify_source(str(tmp_path / "other.wua")) is None
    assert rules.get_source_subfolder() == "Message"
    assert rules.unpack_sources({"base": path}, str(target), _quiet, lambda: False) == str(target)
    assert (target / "Message" / "Hello.msbt").is_file()
