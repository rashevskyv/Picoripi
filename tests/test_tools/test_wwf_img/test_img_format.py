"""WWF WrestleMania (arcade): the IMG library reader and the override size rule, on a small synthetic library.
The real-data check reads the port's IMG files from a read-only scratch clone and skips when that clone is absent."""
import glob
import os
import struct

import pytest

from tools import wwf_img_format as f

IMG_DIR = os.environ.get("PICORIPI_WWF_IMG", "")   # the port's IMG folder, read only: unset skips the real-data check


def _library() -> bytes:
    """One 2x2 image (stride 4) and one palette (two colours) in the version 0x0626 layout."""
    data = bytearray(f.HEADER_SIZE)
    struct.pack_into("<HHIH", data, 0, 1, 4, 40, 0x0626)          # 1 image, 3 built-in + 1 palette, records at 40
    colours = struct.pack("<2H", 0x7FFF, 0x001F)                    # white, red, at offset 28
    data += colours                                                  # 28..31
    data += bytes([1, 2, 0, 0, 3, 0, 0, 0])                          # pixels at 32..39 (stride 4)
    record = bytearray(50)
    record[0:1] = b"T"
    struct.pack_into("<hhHHH", record, 18, 5, -3, 2, 2, 3)          # anchor, width, height, palette 3 (= stored 0)
    struct.pack_into("<I", record, 28, 32)                           # pixel offset
    data += record                                                   # 40..89
    palette = bytearray(26)
    palette[0:4] = b"PAL1"
    palette[11] = 5
    struct.pack_into("<HI", palette, 12, 2, 28)                      # two colours at 28
    data += palette                                                  # 90..115
    return bytes(data)


def test_synthetic_library_gives_its_image_pixels_palette_and_anchor():
    images, palettes = f.parse(_library())
    assert len(images) == 1 and len(palettes) == 1
    image = images[0]
    assert (image.name, image.width, image.height, image.anix, image.aniy) == ("T", 2, 2, 5, -3)
    assert image.palette == 0
    assert image.pixels == bytes([1, 2, 3, 0])
    assert palettes[0].name == "PAL1" and palettes[0].bits == 5
    assert palettes[0].colors == (0x7FFF, 0x001F)


def test_a_table_past_the_end_of_the_file_is_refused():
    with pytest.raises(f.FormatError):
        f.parse(_library()[:60])


def test_colours_scale_to_eight_bits():
    assert f.rgb_of(0x7FFF) == (255, 255, 255)
    assert f.rgb_of(0x001F) == (0, 0, 255)


def test_override_must_be_a_whole_scale_of_the_original():
    assert f.check_override(2, 2, (2, 2)) is None
    assert f.check_override(2, 2, (8, 8)) is None
    assert f.check_override(2, 2, (18, 18)) is not None         # scale 9 is above the limit
    assert f.check_override(2, 2, (3, 3)) is not None           # not a whole multiple
    assert f.check_override(2, 2, (4, 6)) is not None           # the axes disagree


@pytest.mark.skipif(not os.path.isdir(IMG_DIR), reason="scratch clone of the port's IMG folder is not on disk")
def test_every_library_of_the_port_parses_to_the_documented_image_count():
    total = 0
    for path in glob.glob(os.path.join(IMG_DIR, "*.IMG")):
        with open(path, "rb") as stream:
            data = stream.read()
        if not data:
            continue
        images, _palettes = f.parse(data)
        total += len(images)
    assert total == 17514
