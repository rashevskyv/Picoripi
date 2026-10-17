"""Pokémon Scarlet and Violet: the LayeredFS build of a changed text file for both title ids, each with its own index.

The wizard unpacks Scarlet (base and update) and the other version Violet (its base and update, as the other-version
roles). A translation folder holds one edited file; the build writes the romfs and the patched index of each title.
Skips unless the owner's packages, the Switch key path and the Oodle library are on disk.
"""
import re
from pathlib import Path

import pytest
import romhacking_root

from core.containers import console_crypto
from core.containers.game_freak import path_hash
from core.containers.trinity_pack import FlatBuffer
from core.project_library import build
from plugins.pokemon_trinity import build as trinity_build
from plugins.testing import load_rules

ROOT = romhacking_root.under("Pokemon")
SV = ROOT / "Scarlet and Violet" / "ISO"
SCARLET_TITLE, VIOLET_TITLE = "0100A3D008C5C000", "01008F6008C5E000"
SCARLET = {"base": SV / "Pokemon Scarlet" / f"Pokemon Scarlet [{SCARLET_TITLE}][v0].nsp",
           "update": SV / "Pokemon Scarlet" / "Pokemon Scarlet [0100A3D008C5C800][v786432].nsp"}
VIOLET = {"base": SV / "Pokemon Violet" / f"Pokemon Violet [{VIOLET_TITLE}][v0].nsp",
          "update": SV / "Pokemon Violet" / "Pokemon Violet [01008F6008C5E800][v786432].nsp"}
KEY_INI = romhacking_root.root() / "_shared" / "scripts" / "zelda_env.ini" if romhacking_root.root() else None
OODLE_DLL = romhacking_root.root() / "_shared" / "tools" / "oodle" / "oo2ext_7_win64.dll" if romhacking_root.root() else None


def _switch_key_path():
    if KEY_INI is None or not KEY_INI.is_file():
        return None
    for line in KEY_INI.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^\s*switch_keys\s*=\s*(.+?)\s*$", line)
        if match and Path(match.group(1)).is_file():
            return match.group(1)
    return None


def _provider(console):
    if console == "switch":
        return _switch_key_path()
    if console == "oodle" and OODLE_DLL is not None and OODLE_DLL.is_file():
        return str(OODLE_DLL)
    return None


def _hashes(trpfd: bytes):
    fd = FlatBuffer(trpfd)
    return set(fd.u64s(fd.root(), 0))


def test_scarlet_and_violet_builds_move_the_changed_file_out_of_each_index(tmp_path):
    images = [SCARLET["base"], SCARLET["update"], VIOLET["base"], VIOLET["update"]]
    if not all(p.is_file() for p in images) or _switch_key_path() is None or _provider("oodle") is None:
        pytest.skip("the owner's Scarlet and Violet packages, the key path or the Oodle library are not on disk")
    rules = load_rules("pokemon_trinity")
    sources = {"base": str(SCARLET["base"]), "update": str(SCARLET["update"]),
               "other_base": str(VIOLET["base"]), "other_update": str(VIOLET["update"])}
    with console_crypto.key_source(_provider):
        folder = Path(build.run_unpack(rules, sources, str(tmp_path / "project"), lambda p, t: None, lambda: False,
                                       _provider))
    rel = next(p.relative_to(folder).as_posix() for p in (folder / "message" / "dat" / "English" / "common").rglob("*.dat"))
    original = (folder / rel).read_bytes()
    translation = tmp_path / "translation"
    (translation / Path(rel).parent).mkdir(parents=True)
    (translation / rel).write_bytes(original + b"\x00" * 8)
    out = tmp_path / "out"
    out.mkdir()
    trinity_build.build_switch(str(folder), str(translation), str(out), lambda p, t: None, lambda: False)
    for title in (SCARLET_TITLE, VIOLET_TITLE):
        romfs = out / "atmosphere" / "contents" / title / "romfs"
        assert (romfs / rel).read_bytes() == original + b"\x00" * 8
        old = _hashes((folder.parent / "romfs" / title / "arc" / "data.trpfd").read_bytes())
        new = _hashes((romfs / "arc" / "data.trpfd").read_bytes())
        assert path_hash(rel) in old and path_hash(rel) not in new
        assert len(old) == len(new) and len(old - new) == 1
