"""Pokémon Sword / Legends: Arceus wizard unpack: the base game with its update's BKTR patch, read by Picoripi's reader.

The real-data tests run through ``build.run_unpack`` (the wizard's own job) and skip unless the owner's packages and the
Switch key path (``switch_keys`` in the shared ``zelda_env.ini``, a path only) are on disk. The key file is opened by
Picoripi's reader, never by these tests.
"""
import hashlib
import re
import struct
from pathlib import Path

import pytest
import romhacking_root

from core.containers import console_crypto
from core.containers.image_files import ImageError
from core.containers.switch_bktr import _shallow_tree
from core.project_library import build
from plugins.testing import load_rules

ROOT = romhacking_root.under('Pokemon')
SWORD = ROOT / "Sword and Shield"
ARCEUS = ROOT / "Legends Arceus"
SWORD_BASE = SWORD / "nsp" / "Pokemon Sword [0100ABF008968000][v0].nsp"
SWORD_UPDATE = SWORD / "nsp" / "Pokemon Sword [0100ABF008968800][v458752].nsp"
ARCEUS_BASE = ARCEUS / "nsp" / "Pokemon Legends Arceus [01001F5010DFA000][v0].nsp"
ARCEUS_UPDATE = ARCEUS / "nsp" / "Pokemon Legends Arceus [01001F5010DFA800][v262144].nsp"
KEY_INI = romhacking_root.root() / "_shared" / "scripts" / "zelda_env.ini" if romhacking_root.root() else None


def _switch_key_path():
    """The ``switch_keys`` path of the shared env file, or None (paths only; the key file is not opened here)."""
    if KEY_INI is None or not KEY_INI.is_file():
        return None
    for line in KEY_INI.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^\s*switch_keys\s*=\s*(.+?)\s*$", line)
        if match and Path(match.group(1)).is_file():
            return match.group(1)
    return None


OODLE_DLL = (romhacking_root.root() / "_shared" / "tools" / "oodle" / "oo2ext_7_win64.dll"
             if romhacking_root.root() else None)


def _oodle_path():
    """The Oodle library path of the owner's shared tools (a path only; the library is loaded by Picoripi)."""
    return str(OODLE_DLL) if OODLE_DLL is not None and OODLE_DLL.is_file() else None


def _provider(console):
    if console == "switch":
        return _switch_key_path()
    return _oodle_path() if console == "oodle" else None


def _need(*paths, oodle=False):
    if not all(p.is_file() for p in paths):
        pytest.skip("the owner's Pokémon Switch packages are not on disk")
    if _switch_key_path() is None:
        pytest.skip("the Switch key path is not in the shared env file")
    if oodle and _oodle_path() is None:
        pytest.skip("the owner's Oodle library is not on disk")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_wizard(sources, project_dir):
    """The wizard's own unpack job: build.run_unpack with the rules of the plugin and the key path provider."""
    rules = load_rules("pokemon_nx")
    with console_crypto.key_source(_provider):
        return build.run_unpack(rules, sources, str(project_dir), lambda percent, text: None, lambda: False, _provider)


def test_a_deeper_patch_table_is_refused():
    def read(offset, size):
        if offset == 0x100:
            return struct.pack("<iiq", 0, 1, 0)   # one entry set ...
        return (struct.pack("<iiq", 0, 1, 0) + bytes(16))[:size]   # ... holding one entry

    with pytest.raises(ImageError):
        _shallow_tree(read, 0x100, 0x10, 2)   # the table claims two entries


def test_sword_wizard_unpack_matches_the_workspace_source(tmp_path):
    _need(SWORD_BASE, SWORD_UPDATE)
    if not (SWORD / "source").is_dir():
        pytest.skip("the workspace source is not on disk")
    folder = _run_wizard({"base": str(SWORD_BASE), "update": str(SWORD_UPDATE)}, tmp_path / "project")
    unpacked = Path(folder)
    assert (unpacked / "bin" / "message" / "English").is_dir()
    ours = {p.relative_to(unpacked).as_posix(): p for p in unpacked.rglob("*") if p.is_file()}
    theirs = {p.relative_to(SWORD / "source").as_posix(): p
              for p in (SWORD / "source").rglob("*") if p.is_file()}
    # the workspace source predates the dialogue layout (bin/appli/msg/bin/msg_00.arc): it is the only extra file
    assert theirs.keys() <= ours.keys() and len(theirs) > 2000
    assert set(ours) - set(theirs) == {"bin/appli/msg/bin/msg_00.arc"}
    assert all(_sha(ours[name]) == _sha(theirs[name]) for name in theirs)


def test_arceus_wizard_unpack_matches_the_workspace_packs(tmp_path):
    _need(ARCEUS_BASE, ARCEUS_UPDATE, oodle=True)
    if not (ARCEUS / "source").is_dir():
        pytest.skip("the workspace source is not on disk")
    folder = Path(_run_wizard({"base": str(ARCEUS_BASE), "update": str(ARCEUS_UPDATE)}, tmp_path / "project"))
    assert (folder / "bin" / "message" / "English").is_dir()
    packs = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*_eng.gfpak"))
    theirs = sorted(p.relative_to(ARCEUS / "source").as_posix() for p in (ARCEUS / "source").rglob("*_eng.gfpak"))
    assert packs == theirs and packs
    assert _sha(folder / packs[0]) == _sha(ARCEUS / "source" / packs[0])
    # the decoded files of every pack equal the workspace's <pack>.gfpak.d folder, name and byte
    for pack in packs:
        ours = {p.name: _sha(p) for p in (folder / (pack + ".d")).iterdir()}
        target = {p.name: _sha(p) for p in (ARCEUS / "source" / (pack + ".d")).iterdir()}
        assert ours == target and ours
    # every other file of the workspace source is written identically
    theirs = {p.relative_to(ARCEUS / "source").as_posix(): p
              for p in (ARCEUS / "source").rglob("*") if p.is_file()}
    ours_all = {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()}
    assert theirs.keys() <= ours_all.keys() and len(theirs) > 300
    assert all(_sha(ours_all[name]) == _sha(theirs[name]) for name in theirs)


def test_arceus_packs_without_the_oodle_path_are_an_error(tmp_path, monkeypatch):
    _need(ARCEUS_BASE, ARCEUS_UPDATE)
    monkeypatch.setattr(console_crypto, "key_path", lambda console: _switch_key_path() if console == "switch" else None)
    with pytest.raises(ImageError):
        _run_wizard({"base": str(ARCEUS_BASE), "update": str(ARCEUS_UPDATE)}, tmp_path / "project")


def test_a_missing_update_is_an_error_not_a_silent_unpack(tmp_path):
    _need(SWORD_BASE)
    with pytest.raises(ImageError):
        _run_wizard({"base": str(SWORD_BASE)}, tmp_path / "project")


def test_a_file_that_is_not_a_pokemon_image_is_an_error(tmp_path):
    fake = tmp_path / "not_a_game.nsp"
    fake.write_bytes(b"not a switch package")
    with pytest.raises(ImageError):
        _run_wizard({"base": str(fake), "update": str(fake)}, tmp_path / "project")
