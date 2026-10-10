"""Silent Hill 2 texture reader (core/texture_formats/sh2tex.py): round trip on real files (skips without the game data)."""
import pathlib
import struct

import pytest

from core.texture_formats import sh2tex

DATA = pathlib.Path(r"E:\Emulators\RomHacking\Silent Hill\Silent Hill 2\PC\ISO\data")
CARBON = DATA / "pic" / "carbon.tex"


def test_detect_magic_and_layout_on_synthetic_8bit():
    width, height = 4, 2
    header = bytearray(sh2tex.HEADER)
    header[:4] = sh2tex.MAGIC
    struct.pack_into("<HH", header, 0x14, width, height)
    body = bytes(range(width * height))
    data = bytes(header) + body
    assert sh2tex.detect(data)
    textures = sh2tex.read(data, {})
    assert textures[0].image.size == (width, height)
    assert sh2tex.write(data, {0: textures[0].image}, {}) == data


def test_edit_changes_only_one_index_byte_on_synthetic_8bit():
    width, height = 4, 2
    header = bytearray(sh2tex.HEADER)
    header[:4] = sh2tex.MAGIC
    struct.pack_into("<HH", header, 0x14, width, height)
    data = bytes(header) + bytes(width * height)
    img = sh2tex.read(data, {})[0].image.copy()
    img.putpixel((1, 1), (255, 255, 255, 255))
    new = sh2tex.write(data, {0: img}, {})
    assert [i for i in range(len(data)) if data[i] != new[i]] == [sh2tex.HEADER + 1 * width + 1]


@pytest.mark.skipif(not CARBON.is_file(), reason="Silent Hill 2 game data not present")
def test_real_carbon_round_trip_is_byte_identical():
    data = CARBON.read_bytes()
    textures = sh2tex.read(data, {})
    assert textures[0].image.size == (512, 512)
    assert sh2tex.write(data, {0: textures[0].image}, {}) == data
