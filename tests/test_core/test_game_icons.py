"""Game icon readers on tiny synthetic files built in the test (no game data)."""
from __future__ import annotations

import io
import struct

from PIL import Image

from core.game_icons import extract_icon
from core.game_icons import bnr, nds, nro, pe, smdh
from core.game_icons.common import FileSource, finish
from core.texture_formats import pixels


def _write(tmp_path, name, data: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def _png(size, colour) -> bytes:
    """A PNG: the left half ``colour``, the right half green (a flat picture is not an icon)."""
    buf = io.BytesIO()
    picture = Image.new("RGBA", size, colour)
    picture.paste((0, 255, 0, 255), (size[0] // 2, 0, size[0], size[1]))
    picture.save(buf, format="PNG")
    return buf.getvalue()


def test_finish_scales_by_whole_factors_and_rejects_flat_pictures():
    def two(size):
        picture = Image.new("RGBA", size, (1, 2, 3, 255))
        picture.paste((9, 9, 9, 255), (0, 0, size[0] // 2, size[1]))
        return picture

    assert finish(two((32, 32))).size == (64, 64)
    assert finish(two((16, 16))).size == (64, 64)
    assert finish(two((400, 100))).size == (256, 64)
    assert finish(Image.new("RGBA", (32, 32), (0, 0, 0, 0))) is None


def test_nds_banner_palette_index_one_is_red_and_index_zero_transparent(tmp_path):
    banner_at = 0x200
    rom = bytearray(banner_at + 0x240)
    struct.pack_into("<I", rom, nds.BANNER_AT_FIELD, banner_at)
    struct.pack_into("<H", rom, banner_at, 1)                          # banner version 1
    rom[banner_at + 0x20:banner_at + 0x220] = bytes([0x21]) * 512      # pixels: index 1 then 2, low nibble first
    struct.pack_into("<H", rom, banner_at + 0x220 + 2, 0x001F)         # colour 1: red (BGR555)
    struct.pack_into("<H", rom, banner_at + 0x220 + 4, 0x03E0)         # colour 2: green
    image = nds.read(FileSource(_write(tmp_path, "game.nds", bytes(rom))))
    assert image.size == (32, 32)
    assert image.getpixel((0, 0)) == (255, 0, 0, 255)
    assert image.getpixel((1, 0)) == (0, 255, 0, 255)
    assert image.getpixel((0, 0))[3] == 255


def test_gamecube_banner_picture_is_rgb5a3_at_0x20(tmp_path):
    picture = Image.new("RGBA", (96, 32), (255, 0, 0, 255))
    picture.paste((0, 0, 255, 255), (48, 0, 96, 32))
    raw = pixels.codec("gx:RGB5A3").encode(picture)
    data = b"BNR1" + bytes(0x1C) + raw + bytes(0x1960 - 0x20 - len(raw))
    decoded = bnr.read(data)
    assert decoded.size == (96, 32)
    assert decoded.getpixel((0, 0)) == (255, 0, 0, 255)
    assert decoded.getpixel((95, 31)) == (0, 0, 255, 255)
    assert bnr.read(b"NOPE" + data[4:]) is None


def test_3ds_smdh_large_icon_is_rgb565_morton_tiles_at_0x24c0(tmp_path):
    picture = Image.new("RGBA", (48, 48), (255, 0, 0, 255))
    picture.paste((0, 255, 0, 255), (24, 0, 48, 48))
    body = bytearray(0x36C0)
    body[0:4] = b"SMDH"
    body[0x24C0:0x24C0 + 48 * 48 * 2] = pixels.codec("pica:RGB565").encode(picture)
    image = smdh.read(FileSource(_write(tmp_path, "icon.bin", bytes(body))))
    assert image.size == (48, 48)
    left, right = image.getpixel((0, 0)), image.getpixel((47, 47))
    assert left[0] > 200 and left[1] < 60
    assert right[1] > 200 and right[0] < 60


def test_switch_nro_icon_is_the_jpeg_of_the_asset_section(tmp_path):
    nro_size = 0x100
    jpeg = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 40, 40)).save(jpeg, format="JPEG")
    asset = b"ASET" + struct.pack("<I", 0) + struct.pack("<QQ", 0x38, len(jpeg.getvalue())) + bytes(32)
    blob = bytearray(nro_size)
    blob[0x10:0x14] = b"NRO0"
    struct.pack_into("<I", blob, 0x18, nro_size)
    data = bytes(blob) + asset + jpeg.getvalue()
    image = nro.read(FileSource(_write(tmp_path, "game.nro", data)))
    assert image.size == (64, 64)
    assert image.convert("RGB").getpixel((5, 5))[0] > 150


def _minimal_pe(icon_png: bytes) -> bytes:
    """A PE32 file with one .rsrc section: RT_GROUP_ICON 1 names one PNG RT_ICON 1 (32x32)."""
    rsrc_va, rsrc_at = 0x1000, 0x200
    group = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHIH", 32, 32, 0, 0, 1, 32, len(icon_png), 1)
    rsrc = bytearray(0xC0 + len(icon_png))
    # directories: root 0x00 -> type 3 at 0x20 -> name 1 at 0x38 -> data 0x80
    #              root -> type 14 at 0x50 -> name 1 at 0x68 -> data 0x90
    for at, pairs in ((0x00, [(3, 0x80000000 | 0x20), (14, 0x80000000 | 0x50)]), (0x20, [(1, 0x80000000 | 0x38)]),
                      (0x38, [(1033, 0x80)]), (0x50, [(1, 0x80000000 | 0x68)]), (0x68, [(1033, 0x90)])):
        struct.pack_into("<IIHHHH", rsrc, at, 0, 0, 0, 0, 0, len(pairs))
        for index, (name_id, child) in enumerate(pairs):
            struct.pack_into("<II", rsrc, at + 16 + 8 * index, name_id, child)
    struct.pack_into("<IIII", rsrc, 0x80, rsrc_va + 0xC0, len(icon_png), 0, 0)     # RT_ICON data entry
    struct.pack_into("<IIII", rsrc, 0x90, rsrc_va + 0xA0, len(group), 0, 0)        # RT_GROUP_ICON data entry
    rsrc[0xA0:0xA0 + len(group)] = group
    rsrc[0xC0:] = icon_png
    data = bytearray(rsrc_at + len(rsrc))
    data[0:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x40)
    data[0x40:0x44] = b"PE\0\0"
    struct.pack_into("<HHIII", data, 0x44, 0x14C, 1, 0, 0, 0)     # machine, one section
    struct.pack_into("<HH", data, 0x54, 0xE0, 0x102)               # optional header size, characteristics
    struct.pack_into("<H", data, 0x58, 0x10B)                       # PE32
    struct.pack_into("<II", data, 0x58 + 96 + 16, rsrc_va, len(rsrc))   # data directory 2: resource
    section = 0x58 + 0xE0
    data[section:section + 8] = b".rsrc\0\0\0"
    struct.pack_into("<IIII", data, section + 8, len(rsrc), rsrc_va, len(rsrc), rsrc_at)
    data[rsrc_at:rsrc_at + len(rsrc)] = rsrc
    return bytes(data)


def test_pe_resource_icon_is_read_from_group_and_png_payload(tmp_path):
    png = _png((32, 32), (10, 200, 30, 255))
    image = pe.read(FileSource(_write(tmp_path, "game.exe", _minimal_pe(png))))
    assert image is not None
    assert image.size == (32, 32)
    assert image.convert("RGBA").getpixel((3, 3)) == (10, 200, 30, 255)


def test_extract_icon_names_the_format_and_returns_none_for_garbage(tmp_path):
    png = _png((32, 32), (10, 200, 30, 255))
    icon = extract_icon(_write(tmp_path, "game.exe", _minimal_pe(png)))
    assert icon is not None and icon.format == "pc-exe-icon"
    assert icon.image.size == (64, 64)
    assert extract_icon(_write(tmp_path, "junk.bin", b"not a game" * 20)) is None
