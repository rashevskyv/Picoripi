"""The Wind Waker GameCube disc builder: a playable ISO from an unpacked tree, with synthetic data only.

The tree is made here: sys/ (header, bi2, apploader, FST, DOL) and files/. The checks read the built image back
through its own FST, so a wrong offset or size fails them.
"""
import struct
from pathlib import Path

import pytest

from plugins.zelda_tww import disc
from plugins.zelda_tww.rules import BLUEWAKE_TARGET, DISC_TARGET, GameRules


def _fst(entries):
    """An FST for ``entries``: ``[("file", name, data_size)]`` or ``[("dir", name, next_index)]`` after the root.

    Returns ``(fst bytes, file entry index per name)``. Offsets and sizes are written as zero; the builder sets them.
    """
    count = len(entries) + 1
    names = bytearray()
    table = [struct.pack(">III", 0x01000000, 0, count)]
    indexes = {}
    for index, entry in enumerate(entries, start=1):
        kind, name = entry[0], entry[1]
        at = len(names)
        names += name.encode("ascii") + b"\0"
        if kind == "dir":
            table.append(struct.pack(">III", 0x01000000 | at, 0, entry[2]))
        else:
            indexes[name] = index
            table.append(struct.pack(">III", at, 0, entry[2]))
    return b"".join(table) + bytes(names), indexes


def _tree(root: Path):
    """A tree with files/a.bin, files/dir/b.bin, sys/ parts. Returns the source folder."""
    sys_dir = root / "sys"
    files = root / "files"
    (files / "dir").mkdir(parents=True)
    sys_dir.mkdir(parents=True)
    fst, _ = _fst([("file", "a.bin", 0), ("dir", "dir", 4), ("file", "b.bin", 0)])
    contents = {"a.bin": b"A" * 1000, "dir/b.bin": b"B" * 33}
    for name, data in contents.items():
        (files / name).write_bytes(data)
    boot = bytearray(0x440)
    boot[0:6] = b"GZLE01"
    (sys_dir / "boot.bin").write_bytes(bytes(boot))
    (sys_dir / "bi2.bin").write_bytes(b"\x11" * 0x2000)
    (sys_dir / "apploader.img").write_bytes(b"\x22" * 0x300)
    (sys_dir / "fst.bin").write_bytes(fst)
    (sys_dir / "main.dol").write_bytes(b"D" * 0x1234)
    return root


def _read_back(image: Path):
    iso = image.read_bytes()
    dol_off, fst_off, fst_size = struct.unpack_from(">III", iso, 0x420)
    return iso, dol_off, fst_off, fst_size, disc.read_files(iso)


def test_build_writes_every_fst_file_with_its_source_bytes(tmp_path):
    source = _tree(tmp_path / "src")
    out = tmp_path / "out.iso"

    disc.build_disc(source, None, out, False, lambda *_: None, lambda: False)

    iso, dol_off, fst_off, fst_size, files = _read_back(out)
    assert files == {"files/a.bin": b"A" * 1000, "files/dir/b.bin": b"B" * 33}
    assert iso[dol_off:dol_off + 0x1234] == b"D" * 0x1234
    assert dol_off % disc.DOL_ALIGN == 0 and fst_off % disc.DOL_ALIGN == 0
    assert iso[0x2440:0x2440 + 0x300] == b"\x22" * 0x300
    assert fst_size == len((source / "sys" / "fst.bin").read_bytes())


def test_a_translated_file_replaces_the_source_and_a_grown_file_moves(tmp_path):
    source = _tree(tmp_path / "src")
    translation = tmp_path / "trn"
    (translation / "files").mkdir(parents=True)
    (translation / "files" / "a.bin").write_bytes(b"Z" * 5000)     # bigger than the source file

    out = tmp_path / "out.iso"
    disc.build_disc(source, translation, out, False, lambda *_: None, lambda: False)

    _, _, _, _, files = _read_back(out)
    assert files["files/a.bin"] == b"Z" * 5000
    assert files["files/dir/b.bin"] == b"B" * 33


def test_the_dolphin_disc_takes_the_translated_dol_and_the_bluewake_disc_keeps_the_original(tmp_path):
    source = _tree(tmp_path / "src")
    translation = tmp_path / "trn"
    (translation / "sys").mkdir(parents=True)
    (translation / "sys" / "main.dol").write_bytes(b"T" * 0x1234)

    dolphin, bluewake = tmp_path / "dolphin.iso", tmp_path / "bluewake.iso"
    disc.build_disc(source, translation, dolphin, True, lambda *_: None, lambda: False)
    disc.build_disc(source, translation, bluewake, False, lambda *_: None, lambda: False)

    for image, expected in ((dolphin, b"T"), (bluewake, b"D")):
        iso, dol_off, _, _, _ = _read_back(image)
        assert iso[dol_off:dol_off + 0x1234] == expected * 0x1234


def test_a_dol_that_changes_size_is_refused(tmp_path):
    source = _tree(tmp_path / "src")
    translation = tmp_path / "trn"
    (translation / "sys").mkdir(parents=True)
    (translation / "sys" / "main.dol").write_bytes(b"T" * 0x2000)

    with pytest.raises(ValueError, match="main.dol changed its size"):
        disc.build_disc(source, translation, tmp_path / "x.iso", True, lambda *_: None, lambda: False)


def test_a_cancel_stops_the_build_without_a_complete_image(tmp_path):
    source = _tree(tmp_path / "src")
    out = tmp_path / "out.iso"
    progress = []

    disc.build_disc(source, None, out, False, lambda pct, name: progress.append(name), lambda: len(progress) >= 1)

    assert progress == ["files/a.bin"]


def test_the_plugin_declares_both_discs_on_their_own_platforms():
    rules = GameRules()
    targets = {target["id"]: target for target in rules.get_build_targets()}

    assert set(targets) == {DISC_TARGET, BLUEWAKE_TARGET}
    assert targets[DISC_TARGET]["platforms"] == ["gc"]
    assert targets[BLUEWAKE_TARGET]["platforms"] == ["bluewake"]
    assert {platform["id"] for platform in rules.get_platforms()} == {"gc", "bluewake"}


def test_the_plugin_build_writes_the_named_disc(tmp_path):
    source = _tree(tmp_path / "src")
    output = tmp_path / "out"
    output.mkdir()

    built = GameRules().build_target(DISC_TARGET, str(source), str(tmp_path / "missing"), str(output),
                                     lambda *_: None, lambda: False)

    assert Path(built) == output / "The Wind Waker (UA).iso"
    assert Path(built).is_file()
