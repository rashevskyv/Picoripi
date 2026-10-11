"""Silent Hill 3 (PC) ``.tex`` textures of pic.arc: the PS2 8-bit and 32-bit layouts.

The real-data tests read the installed game's ``data\\pic.arc`` and skip when it is missing.
"""
from pathlib import Path

import pytest
from PIL import Image

from core.containers import sh3_arc
from core.texture_formats import sh3_tex

PIC = Path(r"E:\Emulators\RomHacking\Silent Hill\Silent Hill 3\PC\ISO\data\pic.arc")
ARC = Path(r"E:\Emulators\RomHacking\Silent Hill\Silent Hill 3\PC\ISO\data\arc.arc")
needs_game = pytest.mark.skipif(not (PIC.is_file() and ARC.is_file()), reason="Silent Hill 3 data not installed here")


def _tex_files():
    data = PIC.read_bytes()
    _, entries = sh3_arc.parse(data)
    names = dict(sh3_arc.parse_catalog(ARC.read_bytes())["pic"])
    for index, entry in enumerate(entries):
        name = names.get(index, "")
        if name.endswith(".tex"):
            yield name, data[entry.offset:entry.offset + entry.size]


def test_header_search_and_unsupported_layout_raise_value_error():
    with pytest.raises(ValueError):
        sh3_tex.read(b"\x00" * 64, {})


@needs_game
def test_supported_textures_round_trip_byte_for_byte():
    supported = unsupported = 0
    for name, raw in _tex_files():
        try:
            textures = sh3_tex.read(raw, {})
        except ValueError:
            unsupported += 1
            continue
        supported += 1
        assert sh3_tex.write(raw, {0: textures[0].image}, {}) == raw, name
    assert supported >= 200
    assert unsupported < 100


@needs_game
def test_one_changed_pixel_changes_only_its_texel():
    raw = next(data for name, data in _tex_files() if name.endswith("ura0000.tex"))
    before = sh3_tex.read(raw, {})[0].image
    edited = before.copy()
    edited.putpixel((10, 10), (255, 0, 0, 255))
    out = sh3_tex.write(raw, {0: edited}, {})
    after = sh3_tex.read(out, {})[0].image
    assert after.getpixel((10, 10)) != before.getpixel((10, 10))
    diff = [(x, y) for x in range(before.width) for y in range(before.height)
            if before.getpixel((x, y)) != after.getpixel((x, y))]
    assert diff == [(10, 10)]


@needs_game
def test_png_preview_of_a_palette_texture_is_written(tmp_path):
    raw = next(data for name, data in _tex_files() if name.endswith("ura0000.tex"))
    image = sh3_tex.read(raw, {})[0].image
    out = tmp_path / "ura0000.png"
    image.save(out)
    assert Image.open(out).size == (256, 512)
