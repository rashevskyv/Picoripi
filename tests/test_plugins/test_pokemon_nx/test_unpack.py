"""Sword / Shield wizard unpack: the base game with its update's BKTR patch, read by Picoripi's Switch reader."""
import hashlib
import struct
from pathlib import Path

import pytest
import romhacking_root

from core.containers import console_crypto
from core.containers.image_files import ImageError
from core.containers.switch_bktr import _shallow_tree
from core.project_library import console_keys
from plugins.pokemon_nx import unpack

WORKSPACE = romhacking_root.under('Pokemon') / "Sword and Shield"
BASE = WORKSPACE / "nsp" / "Pokemon Sword [0100ABF008968000][v0].nsp"
UPDATE = WORKSPACE / "nsp" / "Pokemon Sword [0100ABF008968800][v458752].nsp"


def _need_real_data():
    if not (BASE.is_file() and UPDATE.is_file() and (WORKSPACE / "source").is_dir()):
        pytest.skip("the Sword packages and the workspace source are not on disk")
    if console_keys.path_for("switch") is None:
        pytest.skip("the Switch key file is not set in Picoripi's console key store")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def test_a_deeper_patch_table_is_refused():
    def read(offset, size):
        if offset == 0x100:
            return struct.pack("<iiq", 0, 1, 0)   # one entry set ...
        return (struct.pack("<iiq", 0, 1, 0) + bytes(16))[:size]   # ... holding one entry

    with pytest.raises(ImageError):
        _shallow_tree(read, 0x100, 0x10, 2)   # the table claims two entries


def test_unpack_matches_the_workspace_source(tmp_path):
    _need_real_data()
    target = tmp_path / "source"
    with console_crypto.key_source(console_keys.path_for):
        done = unpack.unpack({"base": str(BASE), "update": str(UPDATE)}, str(target),
                             lambda percent, text: None, lambda: False)
    assert done == str(target)
    ours = {p.relative_to(target).as_posix(): p for p in target.rglob("*") if p.is_file()}
    theirs = {p.relative_to(WORKSPACE / "source").as_posix(): p
              for p in (WORKSPACE / "source").rglob("*") if p.is_file()}
    assert ours.keys() == theirs.keys() and len(ours) > 2000
    assert all(_sha(ours[name]) == _sha(theirs[name]) for name in ours)


def test_a_missing_update_is_an_error_not_a_silent_unpack(tmp_path):
    _need_real_data()
    with console_crypto.key_source(console_keys.path_for):
        with pytest.raises(ImageError):
            unpack.unpack({"base": str(BASE)}, str(tmp_path / "source"), lambda percent, text: None, lambda: False)
