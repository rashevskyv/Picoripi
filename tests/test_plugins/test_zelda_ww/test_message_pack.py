"""Wind Waker HD message pack: identify it, unpack it into the project's folders, build the Cemu graphic pack.

The pack is built here as a SARC whose members are Yaz0 SARCs, the layout of permanent_2d_UsEnglish.pack.
Synthetic bytes only; no game file is read.
"""
import struct

import pytest

from core.containers import yaz0
from plugins.zelda_ww import graphic_pack, message_pack
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


def _pack(members: dict) -> bytes:
    """The English pack shape: ``{"Hello.msbt": b"..."}`` becomes member ``Hello_msbt.szs``, a Yaz0 SARC of it."""
    outer = {}
    for name, data in members.items():
        stem, ext = name.rsplit(".", 1)
        outer[f"{stem}_{ext}.szs"] = yaz0.compress(_sarc({name: data}))
    return _sarc(outer)


def _write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def _quiet(*_):
    return None


def _game_folder(root):
    """A game folder as the owner's copy has it: content/Common/Pack/<pack> and content/Common/Layout/*.szs."""
    _write(root / "content" / "Common" / "Pack" / message_pack.PACK_FILE,
           _pack({"Hello.msbt": b"MSG-ONE", "CKingMsg.bffnt": b"FONT-ONE"}))
    _write(root / "content" / "Common" / "Layout" / "Title_00.szs", b"LAYOUT")
    return root


def test_identify_accepts_the_english_pack_by_name_and_header(tmp_path):
    path = _write(tmp_path / message_pack.PACK_FILE, _pack({"Hello.msbt": b"MSG1"}))

    assert message_pack.is_english_pack(path)


def test_identify_refuses_another_name_or_a_file_without_the_sarc_header(tmp_path):
    other = _write(tmp_path / "permanent_2d_UsFrench.pack", _pack({"Hello.msbt": b"MSG1"}))
    fake = _write(tmp_path / message_pack.PACK_FILE, b"not a pack")

    assert not message_pack.is_english_pack(other)
    assert not message_pack.is_english_pack(fake)


def test_unpack_writes_messages_fonts_the_pack_and_the_layouts(tmp_path):
    game = _game_folder(tmp_path / "game")
    target = tmp_path / "unpacked"
    target.mkdir()
    progress = []

    result = message_pack.unpack_messages(str(game), str(target), lambda pct, name: progress.append((pct, name)),
                                          lambda: False)

    assert result == str(target)
    assert (target / "Message" / "Hello.msbt").read_bytes() == b"MSG-ONE"
    assert (target / "Font" / "CKingMsg.bffnt").read_bytes() == b"FONT-ONE"
    assert (target / "Pack" / message_pack.PACK_FILE).read_bytes().startswith(b"SARC")
    assert (target / "Layout" / "Title_00.szs").read_bytes() == b"LAYOUT"
    assert progress[-1][0] == 100


def test_unpack_from_the_pack_file_alone_writes_no_layouts(tmp_path):
    path = _write(tmp_path / message_pack.PACK_FILE, _pack({"Hello.msbt": b"MSG-ONE"}))
    target = tmp_path / "unpacked"
    target.mkdir()

    message_pack.unpack_messages(path, str(target), _quiet, lambda: False)

    assert (target / "Message" / "Hello.msbt").is_file()
    assert not (target / "Layout").exists()


def test_unpack_refuses_a_file_that_is_not_a_sarc(tmp_path):
    path = _write(tmp_path / message_pack.PACK_FILE, b"ZIP-OR-WUA-DATA")
    target = tmp_path / "unpacked"
    target.mkdir()

    with pytest.raises(ValueError, match="not a Wind Waker HD message pack"):
        message_pack.unpack_messages(path, str(target), _quiet, lambda: False)


def test_a_cancel_returns_none_without_a_result(tmp_path):
    path = _write(tmp_path / message_pack.PACK_FILE, _pack({"Hello.msbt": b"MSG-ONE"}))
    target = tmp_path / "unpacked"
    target.mkdir()

    assert message_pack.unpack_messages(path, str(target), _quiet, lambda: True) is None


def test_the_plugin_identifies_a_pack_or_a_game_folder_and_declares_no_subfolder(tmp_path):
    rules = GameRules()
    game = _game_folder(tmp_path / "game")
    target = tmp_path / "unpacked"
    target.mkdir()

    assert [platform["id"] for platform in rules.get_platforms()] == ["wiiu"]
    assert rules.identify_source(str(game)) == {"role": "base", "platform": "wiiu"}
    assert rules.identify_source(str(tmp_path / "other.wua")) is None
    assert rules.get_source_subfolder() is None
    assert rules.unpack_sources({"base": str(game)}, str(target), _quiet, lambda: False) == str(target)
    assert (target / "Message" / "Hello.msbt").is_file()


def test_the_cemu_target_repacks_a_changed_message_and_font_into_the_game_pack(tmp_path):
    source = tmp_path / "source"
    message_pack.unpack_messages(str(_game_folder(tmp_path / "game")), str(source), _quiet, lambda: False)
    translation = tmp_path / "translation"
    _write(translation / "Message" / "Hello.msbt", b"MSG-UA")
    _write(translation / "Font" / "CKingMsg.bffnt", b"FONT-UA")
    output = tmp_path / "out"
    output.mkdir()
    rules = GameRules()

    built = rules.build_target("cemu", str(source), str(translation), str(output), _quiet, lambda: False)

    assert built == str(output / "graphicPacks" / graphic_pack.GRAPHIC_PACK_NAME)
    pack = message_pack_read(output / "graphicPacks" / graphic_pack.GRAPHIC_PACK_NAME / "content" / "Common" /
                             "Pack" / message_pack.PACK_FILE)
    assert pack["Hello_msbt.szs"] == b"MSG-UA"
    assert pack["CKingMsg_bffnt.szs"] == b"FONT-UA"
    rules_txt = (output / "graphicPacks" / graphic_pack.GRAPHIC_PACK_NAME / "rules.txt").read_text(encoding="utf-8")
    assert f"titleIds = {graphic_pack.TITLE_ID}" in rules_txt


def test_the_cemu_target_is_a_layered_folder_for_wii_u():
    targets = {target["id"]: target for target in GameRules().get_build_targets()}

    assert targets["cemu"]["platforms"] == ["wiiu"]
    assert targets["cemu"]["kind"] == "layeredfs"


def message_pack_read(path):
    """``{member name: inner bytes}`` of an unpacked pack: each member decompressed to its one file's data."""
    from core.containers.sarc import Sarc
    pack = Sarc(path.read_bytes())
    return {name: next(iter(Sarc(yaz0.decompress(data)).files.values())) for name, data in pack.files.items()}
