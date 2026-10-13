"""Picture archives of the DS Zelda games: NARC / LZ10 round trip, an NCGR edit, nested archives."""
import os
from pathlib import Path

import pytest

from plugins.zelda_ds import pictures
from plugins.zelda_ds.rom import nitro_files

SCRATCH = Path(os.environ.get("PICORIPI_SCRATCH", "scratch"), r"zelda_ds\rom_clean")
PH = SCRATCH / "ph_usa.nds"
ST = SCRATCH / "st_usa.nds"


@pytest.mark.skipif(not PH.is_file(), reason="clean Phantom Hourglass ROM not in the scratch folder")
def test_unchanged_picture_file_is_written_back_byte_for_byte():
    data = nitro_files(PH.read_bytes())["English/Menu/Bg/endlogoS.bin"]
    assert pictures.is_picture_file(data)
    assert pictures.write_images(data, pictures.read_images(data)) == data


@pytest.mark.skipif(not PH.is_file(), reason="clean Phantom Hourglass ROM not in the scratch folder")
def test_edited_tile_block_reads_back_and_other_members_stay():
    data = nitro_files(PH.read_bytes())["English/Menu/Bg/endlogoS.bin"]
    images = pictures.read_images(data)
    name, image = next(iter(images.items()))
    edited = image.copy()
    colours = sorted(set(image.getdata()))
    target = colours[-1] if colours[-1] != image.getpixel((0, 0)) else colours[0]
    for x in range(8, 40):
        for y in range(8, 24):
            edited.putpixel((x, y), target)
    out = pictures.write_images(data, {name: edited})
    assert out != data
    back = pictures.read_images(out)[name]
    assert back.getpixel((20, 16)) == target
    assert back.getpixel((image.width - 1, image.height - 1)) == image.getpixel((image.width - 1, image.height - 1))


@pytest.mark.skipif(not ST.is_file(), reason="clean Spirit Tracks ROM not in the scratch folder")
def test_child_program_pictures_are_found_one_archive_down():
    child = nitro_files(ST.read_bytes())["English_Child.srl"]
    members = nitro_files(child)
    assert members
    assert any(pictures.is_picture_file(body) for body in members.values())


def test_plain_bytes_are_not_a_picture_file():
    assert not pictures.is_picture_file(b"not a picture at all")
