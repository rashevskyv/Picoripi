"""Metroid Prime (GameCube, USA GM8E01): the unpack equals the workspace's source folder, file by file.

Needs ``PICORIPI_ROMHACKING`` (see tests/romhacking_root.py); the test skips with the reason when its files are missing.
"""
import hashlib
from pathlib import Path

import romhacking_root

MP_ISO = ("Metroid", "Prime (GC + PC port)", "ISO", "Metroid Prime (USA) GM8E01 rev2.iso")
MP_SOURCE = ("Metroid", "Prime (GC + PC port)", "source")


def _tree(folder: Path):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file()}


@romhacking_root.needs(MP_ISO, MP_SOURCE)
def test_metroid_prime_unpack_equals_the_workspace_source(tmp_path):
    from plugins.metroid_prime_trilogy.rules import GameRules

    folder = GameRules(None).unpack_sources({"base": str(romhacking_root.path(*MP_ISO))},
                                            str(tmp_path / "unpacked"), lambda p, t: None, lambda: False)
    assert folder == str(tmp_path / "unpacked")
    assert _tree(tmp_path / "unpacked") == _tree(romhacking_root.path(*MP_SOURCE))
