"""Pokémon Sun on the owner's own decrypted image (skipped without it): the unpack writes the same ``romfs`` tree as the
workspace ``source`` folder, file by file, and a longer translated line goes into the LayeredFS mod while every other
member stays as it was."""
import romhacking_root
from pathlib import Path

import pytest

from plugins.common import gfmsg
from plugins.common.garc import Garc
from plugins.pokemon_gen7 import rules, unpack

IMAGE = ("Pokemon", "Sun and Moon", "ISO", "1609 - Pokemon Sun (USA) [Decrypted].3ds")
SOURCE = ("Pokemon", "Sun and Moon", "source", "romfs")
TITLE = "0004000000164800"
MISSING = romhacking_root.missing(*IMAGE) or romhacking_root.missing(*SOURCE)
pytestmark = pytest.mark.skipif(MISSING is not None, reason=MISSING or "")


def _tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_sun_unpack_matches_the_workspace_source_file_by_file(tmp_path):
    out = Path(unpack.extract(str(romhacking_root.path(*IMAGE)), None, str(tmp_path), lambda p, t: None,
                              lambda: False))

    ours = {k: v for k, v in _tree(out / "romfs").items()}
    workspace = _tree(romhacking_root.path(*SOURCE))
    assert len(ours) == len(workspace) == 4667
    assert ours.keys() == workspace.keys()
    assert [k for k in ours if ours[k] != workspace[k]] == []


def test_sun_build_puts_a_longer_line_into_the_mod_and_changes_no_other_member(tmp_path):
    source = tmp_path / "source"
    unpack.extract(str(romhacking_root.path(*IMAGE)), None, str(source), lambda p, t: None, lambda: False)
    member = source / "romfs" / "a" / "0" / "3" / "2" / "001.dat"
    lines = gfmsg.read(member.read_bytes())
    longer = gfmsg.to_editor(lines[0][0]) + " UA TEST with a longer line"
    new = [(gfmsg.from_editor(longer), lines[0][1])] + lines[1:]
    translation = tmp_path / "translation" / "romfs" / "a" / "0" / "3" / "2"
    translation.mkdir(parents=True)
    (translation / "001.dat").write_bytes(gfmsg.write(new))

    rules.GameRules().build_target("layeredfs", str(source), str(tmp_path / "translation"), str(tmp_path / "out"),
                                   lambda p, t: None, lambda: False)

    mod = Garc((tmp_path / "out" / "titles" / TITLE / "romfs" / "a" / "0" / "3" / "2").read_bytes())
    original = Garc((source / "garc_original" / TITLE / "a" / "0" / "3" / "2.garc").read_bytes())
    changed = [(i, b) for i in range(len(original.files)) for b in original.bits(i)
               if mod.member(i, b)[0] != original.member(i, b)[0]]
    assert changed == [(1, 0)]
    assert gfmsg.to_editor(gfmsg.read(mod.member(1, 0)[0])[0][0]) == longer
