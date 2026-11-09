"""Luigi's Mansion (GameCube): the dialogue font and the resource archive inside sys/main.dol, the Ukrainian letters
in messages, and the build that carries a changed main.dol. Synthetic bytes only; no game file is read."""
import struct

import pytest
from rarc_fixture import build_rarc

from plugins.luigis_mansion_1_gc import build, messages
from plugins.luigis_mansion_1_gc.dol_font import ARCHIVE_AT, ARCHIVE_MEMBER, DOL_SIZE, FONT_AT, FONT_MAGIC, MEMBER, DolFont

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


def _dol_with_archive(archive: bytes) -> bytes:
    data = bytearray(_dol())
    data[ARCHIVE_AT:ARCHIVE_AT + len(archive)] = archive
    return bytes(data)


def test_resource_archive_is_a_member_with_its_own_room():

    archive = build_rarc({"a.bin": b"\x33" * 40})
    container = DolFont(_dol_with_archive(archive))
    assert container.list_files() == [MEMBER, ARCHIVE_MEMBER]
    assert container.read_file(ARCHIVE_MEMBER) == archive
    container.write_file(ARCHIVE_MEMBER, archive[:-32])
    out = container.pack()
    assert len(out) == DOL_SIZE
    assert out[ARCHIVE_AT:ARCHIVE_AT + len(archive)] == archive[:-32] + bytes(32)
    with pytest.raises(ValueError, match="room for"):
        container.write_file(ARCHIVE_MEMBER, archive + b"\x00")


def test_texture_in_a_yay0_archive_inside_main_dol_is_written_in_place(tmp_path):
    from PIL import Image

    from core.containers import yay0
    from core.texture_formats import sources
    from plugins.luigis_mansion_1_gc.rules import GameRules
    from .test_textures import _bti

    GameRules()   # registers DolFont for .dol
    inner = yay0.compress_matched(build_rarc({"start.bti": _bti((0, 0, 0, 255))}))
    dol = _dol_with_archive(build_rarc({"res_titl.szp": inner}))
    for root in ("src", "trn"):
        (tmp_path / root / "sys").mkdir(parents=True)
        (tmp_path / root / "sys" / "main.dol").write_bytes(dol)
    project = {"source_path": str(tmp_path / "src"), "translation_path": str(tmp_path / "trn"),
               "is_directory_mode": True}
    descriptor = [{"label": "Title", "kind": "title_screen", "format": "bti", "path": "sys/main.dol",
                   "member": "resources.arc/res_titl.szp/start.bti"}]
    [texture] = sources.resolve(descriptor, project)
    assert texture.write(Image.new("RGBA", (8, 4), (255, 255, 255, 255)))

    out = (tmp_path / "trn" / "sys" / "main.dol").read_bytes()
    assert len(out) == DOL_SIZE and out[:ARCHIVE_AT] == dol[:ARCHIVE_AT] and out[FONT_AT:] == dol[FONT_AT:]
    [again] = sources.resolve(descriptor, project)
    assert again.read_current().image.convert("RGBA").getpixel((0, 0)) == (255, 255, 255, 255)
    assert again.read_original().image.convert("RGBA").getpixel((0, 0)) == (0, 0, 0, 255)
