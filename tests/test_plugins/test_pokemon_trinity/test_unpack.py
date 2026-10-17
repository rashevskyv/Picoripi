"""Pokémon Scarlet / Violet: the wizard unpack of the English text, fonts and layouts, on the owner's images.

The tests run the wizard's own job (``build.run_unpack``) and skip unless the owner's packages, the workspace, the Switch
key path (a path in the shared ``zelda_env.ini``) and the Oodle library path are on disk. Picoripi's readers open the
key file and the library; the tests never read them.
"""
import hashlib
import re
from pathlib import Path

import pytest
import romhacking_root

from core.containers import console_crypto
from core.project_library import build
from plugins.pokemon_trinity import unpack
from plugins.testing import load_rules

ROOT = romhacking_root.under("Pokemon")
SV = ROOT / "Scarlet and Violet"
BASE = SV / "ISO" / "Pokemon Scarlet" / "Pokemon Scarlet [0100A3D008C5C000][v0].nsp"
UPDATE = SV / "ISO" / "Pokemon Scarlet" / "Pokemon Scarlet [0100A3D008C5C800][v786432].nsp"
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


def _oodle_path():
    return str(OODLE_DLL) if OODLE_DLL is not None and OODLE_DLL.is_file() else None


def _provider(console):
    if console == "switch":
        return _switch_key_path()
    return _oodle_path() if console == "oodle" else None


def _need():
    if not (BASE.is_file() and UPDATE.is_file()):
        pytest.skip("the owner's Scarlet packages are not on disk")
    if _switch_key_path() is None or _oodle_path() is None:
        pytest.skip("the Switch key path or the Oodle library is not configured")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_identify_tells_base_from_update(tmp_path):
    _need()
    assert unpack.identify(str(BASE))["role"] == "base"
    assert unpack.identify(str(UPDATE))["role"] == "update"
    assert unpack.identify(str(BASE))["libraries"] == ["oodle"]


def test_the_wizard_unpack_writes_the_text_like_the_workspace(tmp_path):
    _need()
    if not (SV / "source").is_dir():
        pytest.skip("the workspace source is not on disk")
    rules = load_rules("pokemon_trinity")
    with console_crypto.key_source(_provider):
        folder = Path(build.run_unpack(rules, {"base": str(BASE), "update": str(UPDATE)}, str(tmp_path / "project"),
                                       lambda percent, text: None, lambda: False, _provider))
    theirs = {p.relative_to(SV / "source").as_posix(): p
              for p in (SV / "source").rglob("*") if p.is_file()}
    ours = {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()}
    missing = sorted(set(theirs) - set(ours))
    different = sorted(name for name in theirs if name in ours and _sha(ours[name]) != _sha(theirs[name]))
    assert len(theirs) > 1800 and not missing[:10] and not different[:10]
    assert len([n for n in theirs if n.endswith(".dat")]) > 900


ZA = ROOT / "Legends Z-A"
ZA_BASE = ZA / "nsp" / "Pokemon Legends Z-A [0100F43008C44000][v0].nsp"
ZA_UPDATE = ZA / "nsp" / "Pokemon Legends Z-A [0100F43008C44800][v393216].nsp"


def test_the_wizard_unpack_of_z_a_matches_the_workspace_text_and_layouts(tmp_path):
    if not (ZA_BASE.is_file() and ZA_UPDATE.is_file()):
        pytest.skip("the owner's Legends: Z-A packages are not on disk")
    if _switch_key_path() is None or _oodle_path() is None or not (ZA / "source").is_dir():
        pytest.skip("the key path, the Oodle library or the workspace source is not configured")
    rules = load_rules("pokemon_trinity")
    with console_crypto.key_source(_provider):
        folder = Path(build.run_unpack(rules, {"base": str(ZA_BASE), "update": str(ZA_UPDATE)},
                                       str(tmp_path / "project"), lambda percent, text: None, lambda: False,
                                       _provider))
    theirs = {p.relative_to(ZA / "source").as_posix(): p for p in (ZA / "source").rglob("*") if p.is_file()}
    ours = {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()}
    assert len(theirs) > 400
    assert not sorted(set(theirs) - set(ours))[:10]
    assert not sorted(n for n in theirs if _sha(ours[n]) != _sha(theirs[n]))[:10]
