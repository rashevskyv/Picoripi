"""Game images of the owner's RomHacking workspace: the files a plugin unpacks equal the workspace's source files.

Needs ``PICORIPI_ROMHACKING`` (see tests/romhacking_root.py); each test skips with the reason when its file is missing.
"""
import romhacking_root
from core.project_library import images

WW_IMAGE = ("Zelda", "Wind Waker", "GC", "image", "original (USA).iso")
WW_SOURCE = ("Zelda", "Wind Waker", "GC", "source")
FSAE_ROM = ("Zelda", "Four Swords Anniversary", "ISO", "Zelda-_Four_Swords-Anniversary_Edition-Nintendo (EUR).nds")
FSAE_SOURCE = ("Zelda", "Four Swords Anniversary", "source")
PH_ROM = ("_new", "1456 - Legend of Zelda, The - Phantom Hourglass (USA) (En,Fr,Es).nds")
PH_SOURCE = ("Zelda", "Phantom Hourglass", "DS", "source")


def _tree(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


@romhacking_root.needs(WW_IMAGE, WW_SOURCE)
def test_wind_waker_disc_lists_the_workspace_files_with_their_sizes():
    source = romhacking_root.path(*WW_SOURCE)
    on_disk = {p.relative_to(source).as_posix(): p.stat().st_size for p in source.rglob("*") if p.is_file()}
    with images.open_image(romhacking_root.path(*WW_IMAGE)) as disc:
        assert disc.game_id == "GZLE01"
        listed = {entry.path: entry.size for entry in disc.entries()}
    assert listed == on_disk


@romhacking_root.needs(FSAE_ROM, FSAE_SOURCE)
def test_four_swords_unpack_equals_the_workspace_source(tmp_path):
    from plugins.zelda_fsae.rules import GameRules

    folder = GameRules(None).unpack_sources({"base": str(romhacking_root.path(*FSAE_ROM))},
                                            str(tmp_path / "unpacked"), lambda p, t: None, lambda: False)
    assert _tree(tmp_path / "unpacked") == _tree(romhacking_root.path(*FSAE_SOURCE))
    assert folder == str(tmp_path / "unpacked")


@romhacking_root.needs(PH_ROM, PH_SOURCE)
def test_phantom_hourglass_unpack_contains_every_workspace_source_file(tmp_path):
    from plugins.zelda_ds.rules import GameRules

    GameRules(None).unpack_sources({"base": str(romhacking_root.path(*PH_ROM))},
                                   str(tmp_path / "unpacked"), lambda p, t: None, lambda: False)
    unpacked = _tree(tmp_path / "unpacked")
    workspace = _tree(romhacking_root.path(*PH_SOURCE))
    assert {path: unpacked.get(path) for path in workspace} == workspace
