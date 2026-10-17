"""Pokémon X on the owner's own CIA (skipped without it and without a 3DS key path): the unpack writes the same
``romfs`` tree as the workspace ``source`` folder, file by file, and a longer translated line in a text table and a
changed picture inside a DARC pack reach the LayeredFS mod while every other member stays as it was."""
import os
from pathlib import Path

import pytest

import romhacking_root
from core.containers import console_crypto
from plugins.common import gfmsg
from plugins.common.darc_pack import darc_files
from plugins.common.garc import Garc
from plugins.pokemon_gen6 import pack, rules, unpack

CIA = ("Pokemon", "X and Y", "ISO", "0004000000055D00 Pokemon X (CTR-P-EKJA) (v0.2.0) (W).legit.cia")
SOURCE = ("Pokemon", "X and Y", "source", "romfs")
TITLE = "0004000000055d00"
KEY_FILE = os.environ.get("PICORIPI_3DS_KEY_FILE", "").strip()   # the 3DS key file, by path only; never read here
MISSING = romhacking_root.missing(*CIA) or romhacking_root.missing(*SOURCE)
if MISSING is None and not KEY_FILE:
    MISSING = "PICORIPI_3DS_KEY_FILE is not set: the encrypted CIA is not read"
pytestmark = pytest.mark.skipif(MISSING is not None, reason=MISSING or "")


def _tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _key_path(console: str):
    return KEY_FILE if console == "3ds" else None


def _extract(target: Path) -> Path:
    with console_crypto.key_source(_key_path):
        return Path(unpack.extract(str(romhacking_root.path(*CIA)), str(target), lambda p, t: None, lambda: False))


def test_x_unpack_matches_the_workspace_source_file_by_file(tmp_path):
    out = _extract(tmp_path)

    ours = _tree(out / "romfs")
    workspace = _tree(romhacking_root.path(*SOURCE))
    assert len(ours) == len(workspace) == 718
    assert ours.keys() == workspace.keys()
    assert [k for k in ours if ours[k] != workspace[k]] == []


def test_x_build_puts_a_longer_line_and_a_darc_picture_into_the_mod(tmp_path):
    source = tmp_path / "source"
    _extract(source)
    text = source / "romfs" / "a" / "0" / "7" / "4" / "000.dat"
    lines = gfmsg.read(text.read_bytes())
    longer = gfmsg.to_editor(lines[0][0]) + " UA TEST with a longer line"
    translation = tmp_path / "translation" / "romfs" / "a" / "0" / "7" / "4"
    translation.mkdir(parents=True)
    (translation / "000.dat").write_bytes(gfmsg.write([(gfmsg.from_editor(longer), lines[0][1])] + lines[1:]))
    picture = source / "romfs" / "a" / "2" / "3" / "9" / "000.2" / "timg" / "eng.bclim"
    changed = bytearray(picture.read_bytes())
    changed[0x40] ^= 0x01
    pictures = tmp_path / "translation" / "romfs" / "a" / "2" / "3" / "9" / "000.2" / "timg"
    pictures.mkdir(parents=True)
    (pictures / "eng.bclim").write_bytes(bytes(changed))

    rules.GameRules().build_target("layeredfs", str(source), str(tmp_path / "translation"), str(tmp_path / "out"),
                                   lambda p, t: None, lambda: False)

    mod = tmp_path / "out" / "titles" / TITLE / "romfs" / "a"
    text_back = Garc((mod / "0" / "7" / "4").read_bytes())
    assert gfmsg.to_editor(gfmsg.read(text_back.member(0, 0)[0])[0][0]) == longer
    pack_back = Garc((mod / "2" / "3" / "9").read_bytes())
    plain, _ = pack_back.member(0, 2)
    at = pack.pack_darc_at(plain)
    off, size = darc_files(plain[at:])["timg/eng.bclim"]
    assert plain[at:][off:off + size] == bytes(changed)
