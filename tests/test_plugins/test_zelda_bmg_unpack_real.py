"""Twilight Princess GameCube and Wii: the disc's res/Msgus folder is the project source, as in the owner's workspace;
Wii U HD: the unpacked title folder, whose source is content/res/Msguk.

Needs ``PICORIPI_ROMHACKING`` (see tests/romhacking_root.py). Only the ten message archives are read from the disc,
so the test does not write the whole 1.4 GB image.
"""
import hashlib

import romhacking_root
from core.project_library import images
from core.project_library.source_folder import validate_source_folder
from plugins.zelda_bmg.rules import GameRules

TP_IMAGE = ("Zelda", "Twilight Princess", "GC + Wii", "ISO", "Legend of Zelda, The - Twilight Princess (USA).iso")
TP_MSGUS = ("Zelda", "Twilight Princess", "GC + Wii", "ISO", "ENG", "root", "res", "Msgus")
DISC_MSGUS = "files/res/Msgus/"
TP_WII_IMAGE = ("Zelda", "Twilight Princess", "GC + Wii", "ISO", "wii_Legend of Zelda, The - Twilight Princess (USA).iso")
TP_HD_TITLE = ("Zelda", "Twilight Princess", "HD - Wii U", "iso", "The Legend of Zelda Twilight Princess HD [AZAP01]")


def _digests(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file()}


@romhacking_root.needs(TP_IMAGE)
def test_gamecube_disc_is_recognised_and_its_source_folder_is_res_msgus():
    image = romhacking_root.path(*TP_IMAGE)

    assert GameRules().identify_source(str(image)) == {"role": "base", "platform": "gc"}
    assert GameRules().get_source_subfolder()[0] == "files/res/Msgus"
    with images.open_image(image) as disc:
        assert len([e for e in disc.entries() if e.path.startswith(DISC_MSGUS)]) == 10


@romhacking_root.needs(TP_IMAGE, TP_MSGUS)
def test_msgus_archives_equal_the_workspace_source(tmp_path):
    image = romhacking_root.path(*TP_IMAGE)
    images.extract(image, tmp_path, lambda p, t: None, lambda: False,
                   select=lambda path: path.startswith(DISC_MSGUS))

    unpacked = _digests(tmp_path / "files" / "res" / "Msgus")
    assert unpacked == _digests(romhacking_root.path(*TP_MSGUS))
    assert len(unpacked) == 10


@romhacking_root.needs(TP_WII_IMAGE)
def test_wii_disc_is_recognised_and_needs_the_wii_key():
    image = romhacking_root.path(*TP_WII_IMAGE)

    assert GameRules().identify_source(str(image)) == {"role": "base", "platform": "wii"}
    assert images.needs_key(image) == "wii"


@romhacking_root.needs(TP_HD_TITLE)
def test_hd_title_folder_is_wii_u_and_its_source_is_res_msguk():
    folder = romhacking_root.path(*TP_HD_TITLE)

    assert GameRules().identify_source(str(folder)) == {"role": "base", "platform": "wiiu"}
    assert validate_source_folder(GameRules(), folder, lambda: False) == str(folder / "content" / "res" / "Msguk")
