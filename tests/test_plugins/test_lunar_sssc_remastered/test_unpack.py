"""Lunar SSS Remastered unpack: the PC game folder is recognised by its files (synthetic folders, no game data)."""
import struct

import pytest

from core.containers.image_files import ImageError
from plugins.lunar_sssc_remastered import unpack


def test_pc_folder_with_data_cpk_and_exe_is_pc_base(tmp_path):
    (tmp_path / "data.cpk").write_bytes(b"CPK ")
    (tmp_path / "lunar1.exe").write_bytes(b"MZ")
    assert unpack.identify(str(tmp_path)) == {"role": "base", "platform": "pc", "libraries": []}


def test_folder_without_the_game_files_is_not_recognised(tmp_path):
    (tmp_path / "data.cpk").write_bytes(b"CPK ")
    assert unpack.identify(str(tmp_path)) is None


def _fil(files):
    """A synthetic LUNADATA.FIL: the header entry (count at +20), one 32-byte entry per file, the files from sector 1."""
    table, body, sector = bytearray(32), bytearray(), 1
    struct.pack_into("<I", table, 20, len(files))
    for name, data in files:
        table += name.encode("ascii").ljust(20, b"\0") + struct.pack("<III", sector, len(data), 0)
        padded = data + b"\0" * (-len(data) % 2048)
        body += padded
        sector += len(padded) // 2048
    return bytes(table).ljust(2048, b"\0") + bytes(body)


def test_fil_gives_the_dialogue_files_only():
    fil = _fil([("TEXT001.DAT", b"one"), ("SYSTEM.DAT", b"menus"), ("TEXT200.DAT", b"none"), ("TEXT100.DAT", b"x" * 3000)])
    members = unpack.fil_text_members(lambda offset, size: fil[offset:offset + size])
    assert members == {"TEXT001.DAT": b"one", "TEXT100.DAT": b"x" * 3000}


def test_the_ps1_disc_is_the_ps1_role(monkeypatch, tmp_path):
    disc = tmp_path / "disc.cue"
    disc.write_text("FILE")
    monkeypatch.setattr(unpack.images, "identify", lambda path: {"kind": "psx", "game_id": "SLUS-00628"})
    assert unpack.identify(str(disc)) == {"role": "ps1", "platform": "psx", "libraries": []}
    monkeypatch.setattr(unpack.images, "identify", lambda path: {"kind": "psx", "game_id": "SCUS-94457"})
    assert unpack.identify(str(disc)) is None


def test_the_ps1_disc_alone_asks_for_the_remastered_game(tmp_path):
    with pytest.raises(ImageError):
        unpack.unpack({"ps1": str(tmp_path / "disc.cue")}, str(tmp_path), lambda *_: None, lambda: False)
