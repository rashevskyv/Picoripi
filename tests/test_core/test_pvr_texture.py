"""Dreamcast PVR textures (core/texture_formats/pvr.py): a synthetic square twiddled block (one changed texel changes
exactly its two bytes), the refusals, and the owner's title texture when the disc is on disk."""
import os
import struct

import pytest
from PIL import Image

from core.containers import afs
from core.containers.gdrom import GdRomImage, GdRomStream
from core.texture_formats import pvr, read, write

REAL_CUE = r"E:\Emulators\RomHacking\Grandia\Grandia II\Dreamcast\ISO\Grandia II (USA).cue"


def pvr_block(width, height, fmt=0, dtype=1, texels=None):
    """A GBIX block then a PVRT block of ``width`` x ``height`` 16-bit texels, stored in twiddled order."""
    count = width * height
    values = texels if texels is not None else [(i * 37) & 0xFFFF for i in range(count)]
    offsets = pvr.twiddled_offsets(width, height)
    body = bytearray(2 * count)
    for pixel, at in enumerate(offsets):
        body[at:at + 2] = struct.pack("<H", values[pixel])
    gbix = b"GBIX" + struct.pack("<II", 8, 0) + b"    "   # 16 bytes, as on the disc
    head = b"PVRT" + struct.pack("<I", 8 + len(body)) + bytes([fmt, dtype, 0, 0]) + struct.pack("<HH", width, height)
    return gbix + head + bytes(body)


def test_an_unchanged_texture_writes_the_same_bytes():
    raw = pvr_block(16, 16)
    image = read("pvr", raw)[0].image
    assert image.size == (16, 16)
    assert write("pvr", raw, {0: image}) == raw


def test_one_changed_texel_changes_exactly_its_two_bytes():
    raw = pvr_block(16, 16)
    image = read("pvr", raw)[0].image.convert("RGBA")
    image.putpixel((5, 9), (255, 0, 0, 255))
    out = write("pvr", raw, {0: image})
    changed = [i for i in range(len(raw)) if raw[i] != out[i]]
    assert len(changed) <= 2
    assert all(i >= 0x20 for i in changed)
    assert read("pvr", out)[0].image.getpixel((5, 9))[0] >= 240


def test_a_block_that_is_not_pvr_is_refused():
    with pytest.raises(ValueError):
        read("pvr", b"not a texture at all, only text" * 4)


def test_a_data_type_other_than_square_twiddled_is_refused():
    with pytest.raises(ValueError):
        read("pvr", pvr_block(16, 16, dtype=9))


def test_a_rectangle_is_refused():
    raw = bytearray(pvr_block(16, 16))
    struct.pack_into("<HH", raw, 16 + 12, 32, 16)   # the PVRT block starts after the 16-byte GBIX: width, height
    assert raw[16:20] == b"PVRT"
    with pytest.raises(ValueError):
        read("pvr", bytes(raw))


@pytest.mark.skipif(not os.path.isfile(REAL_CUE), reason="the owner's Grandia II image is not on disk")
def test_the_title_texture_of_the_disc_round_trips_and_is_512_square():
    stream = GdRomStream(REAL_CUE)
    try:
        image = GdRomImage(stream)
        data = image.read({e.path: e for e in image.entries()}["files/WINDOW/TITLE_DATA.AFS"])
    finally:
        stream.close()
    entry = [e for e in afs.parse(data) if e.index == 12][0]
    blob = data[entry.offset:entry.offset + entry.size]
    tex = read("pvr", blob)[0]
    assert tex.image.size == (512, 512)
    assert tex.pixel_format == "pvr:ARGB1555"
    assert write("pvr", blob, {0: tex.image}) == blob
    assert isinstance(tex.image, Image.Image)
