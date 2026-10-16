"""Pokémon Sword / Shield and Legends: Arceus: the LayeredFS build of a changed file, on the owner's images.

The wizard unpacks the image (``build.run_unpack``); a translation folder holds one edited file; the build writes the
romfs of the title ids. Skips unless the owner's packages, the Switch key path and (Arceus) the Oodle library are on disk.
"""
import re
from pathlib import Path

import pytest
import romhacking_root

from core.containers import console_crypto, gfpak
from core.project_library import build
from plugins.pokemon_nx import build as nx_build
from plugins.testing import load_rules

ROOT = romhacking_root.under("Pokemon")
SWORD_BASE = ROOT / "Sword and Shield" / "nsp" / "Pokemon Sword [0100ABF008968000][v0].nsp"
SWORD_UPDATE = ROOT / "Sword and Shield" / "nsp" / "Pokemon Sword [0100ABF008968800][v458752].nsp"
ARCEUS_BASE = ROOT / "Legends Arceus" / "nsp" / "Pokemon Legends Arceus [01001F5010DFA000][v0].nsp"
ARCEUS_UPDATE = ROOT / "Legends Arceus" / "nsp" / "Pokemon Legends Arceus [01001F5010DFA800][v262144].nsp"
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


def _unpack(base, update, tmp_path):
    rules = load_rules("pokemon_nx")
    with console_crypto.key_source(_provider):
        return Path(build.run_unpack(rules, {"base": str(base), "update": str(update)}, str(tmp_path / "project"),
                                     lambda p, t: None, lambda: False, _provider))


def _edit_one(source: Path, rel: str, tmp_path: Path, data: bytes) -> Path:
    translation = tmp_path / "translation"
    (translation / Path(rel).parent).mkdir(parents=True, exist_ok=True)
    (translation / rel).write_bytes(data)
    return translation


def test_sword_build_writes_the_changed_file_for_both_title_ids(tmp_path):
    if not (SWORD_BASE.is_file() and SWORD_UPDATE.is_file()) or _switch_key_path() is None:
        pytest.skip("the owner's Sword packages or the Switch key path are not on disk")
    folder = _unpack(SWORD_BASE, SWORD_UPDATE, tmp_path)
    rel = next(p.relative_to(folder).as_posix() for p in (folder / "bin" / "message" / "English").rglob("*.dat"))
    original = (folder / rel).read_bytes()
    translation = _edit_one(folder, rel, tmp_path, original + b"\x00" * 8)
    out = tmp_path / "out"
    out.mkdir()
    nx_build.build_switch(str(folder), str(translation), str(out), lambda p, t: None, lambda: False)
    for title in nx_build.SWORD_SHIELD_TITLES:
        written = out / "atmosphere" / "contents" / title / "romfs" / rel
        assert written.read_bytes() == original + b"\x00" * 8


def test_arceus_build_stores_the_changed_entry_and_keeps_the_others(tmp_path):
    if not (ARCEUS_BASE.is_file() and ARCEUS_UPDATE.is_file()) or _switch_key_path() is None or _provider("oodle") is None:
        pytest.skip("the owner's Arceus packages, the key path or the Oodle library are not on disk")
    from core.unreal.oodle import Oodle
    folder = _unpack(ARCEUS_BASE, ARCEUS_UPDATE, tmp_path)
    pack_rel = "bin/archive/appli/battle_menu_eng.gfpak"
    pack_data = (folder / pack_rel).read_bytes()
    oodle = Oodle(_provider("oodle"))
    before = gfpak.decode(pack_data, oodle.decompress)
    name = gfpak.file_names(before, [e.path_hash for e in gfpak.read_entries(pack_data)])[0]
    rel = f"{pack_rel}.d/{name}"
    edited = before[0] + b"\x00" * 16
    translation = _edit_one(folder, rel, tmp_path, edited)
    out = tmp_path / "out"
    out.mkdir()
    nx_build.build_switch(str(folder), str(translation), str(out), lambda p, t: None, lambda: False)
    written = out / "atmosphere" / "contents" / nx_build.ARCEUS_TITLES[0] / "romfs" / pack_rel
    after = gfpak.decode(written.read_bytes(), oodle.decompress)
    assert after[0] == edited and after[1:] == before[1:]
    assert gfpak.read_entries(written.read_bytes())[0].kind == gfpak.KIND_STORED
