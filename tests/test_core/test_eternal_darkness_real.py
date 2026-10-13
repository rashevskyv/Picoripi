"""Eternal Darkness (GameCube, USA GEDE01): the disc's files equal the workspace's source\\game files.

The whole unpack takes minutes (every *SK_ASC* file is decoded), so this checks a sample: a plain copy, a room text and
a credits file. Needs ``PICORIPI_ROMHACKING`` (see tests/romhacking_root.py); skips with the reason when files are missing.
"""
import romhacking_root
from core.containers import edasc
from core.project_library import images

ED_ISO = ("Eternal Darkness - Sanity’s Requiem", "image", "original (USA).iso")
ED_GAME = ("Eternal Darkness - Sanity’s Requiem", "source", "game")


@romhacking_root.needs(ED_ISO, ED_GAME)
def test_disc_files_equal_the_workspace_game_folder():
    game = romhacking_root.path(*ED_GAME)
    with images.open_image(romhacking_root.path(*ED_ISO)) as disc:
        entries = {entry.path: entry for entry in disc.entries()}
        assert disc.game_id == "GEDE01"
        assert disc.read(entries["files/EBootPak.bin"]) == (game / "EBootPak.bin").read_bytes()
        for rel in ("RmTxt00.cmp", "credits/cr0001.cmp"):
            body = edasc.decompress(disc.read(entries["files/" + rel]))[4:]
            assert body == (game / rel).read_bytes(), rel
