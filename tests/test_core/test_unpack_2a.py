"""Unpack steps of Castlevania DS, Tactics A2 and Dragon Quest IX, on images built in the test (no game bytes)."""
import struct

import pytest

from core.containers.image_files import ImageError, ImageFile
from core.project_library import images
from plugins.castlevania_ds import unpack as cv
from plugins.dq9 import unpack as dq9
from plugins.ffta2 import unpack as a2

REGIONS = (("Names", 0, 1, 0),)
TABLE_RAM = 0x02000000


def _cv_rom(code: bytes, strings) -> bytes:
    """A tiny DS cartridge: overlay 0 holds the pointer table, then the strings (``01 00`` text ``EA``)."""
    head = 4 * len(strings)
    body, pointers = bytearray(), []
    for text in strings:
        pointers.append(TABLE_RAM + head + len(body))
        body += b"\x01\x00" + text + b"\xEA"
    overlay = struct.pack(f"<{len(strings)}I", *pointers) + bytes(body)
    rom = bytearray(0x500 + len(overlay))
    rom[0x0C:0x10] = code
    struct.pack_into("<4I", rom, 0x20, 0x200, TABLE_RAM, TABLE_RAM, 8)     # ARM9 at 0x200
    struct.pack_into("<4I", rom, 0x40, 0x380, 17, 0x300, 8)                 # FNT at 0x380, FAT at 0x300
    struct.pack_into("<II", rom, 0x50, 0x400, 32)                           # ARM9 overlay table at 0x400
    struct.pack_into("<II", rom, 0x300, 0x500, 0x500 + len(overlay))        # file 0 (overlay 0)
    struct.pack_into("<8I", rom, 0x400, 0, TABLE_RAM, len(overlay), 0, 0, 0, 0, 0)
    struct.pack_into("<IHH", rom, 0x380, 16, 0, 0xF000)                     # empty root directory
    struct.pack_into("<H", rom, 0x15C, 0xCF56)                              # Nintendo logo CRC
    rom[0x200:0x208] = b"ARM9DATA"
    rom[0x500:] = overlay
    return bytes(rom)


def test_castlevania_string_table_is_read_from_the_overlay(tmp_path):
    path = tmp_path / "cv.nds"
    path.write_bytes(_cv_rom(b"ACVE", [b"Ab", b"C"]))
    with images.open_image(path) as image:
        assert cv.read_strings(image, TABLE_RAM, REGIONS) == [b"Ab", b"C"]


def test_castlevania_rejects_a_game_it_does_not_know(tmp_path):
    path = tmp_path / "cv.nds"
    path.write_bytes(_cv_rom(b"ZZZZ", [b"Ab"]))
    with pytest.raises(ImageError, match="not a Castlevania DS game"):
        cv.extract(str(path), str(tmp_path / "out"), lambda p, t: None, lambda: False)


def test_tactics_a2_archive_reads_a_single_file_member():
    name = "system/rom/a.bin"
    blob = b"abcdefgh"
    idx = bytearray(8 + 9 * 1024)
    struct.pack_into("<I", idx, 0, 1024)
    words = len(blob) // 4
    struct.pack_into("<II", idx, 8 + 9 * a2.name_hash(name), (0x40 // 2) | words << 26, words >> 6)
    data = bytes(0x40) + blob
    assert a2.PcArchive(bytes(idx), data).read(name) == blob


def test_tactics_a2_join_puts_magic_kind_index_and_data_in_order():
    assert a2.a2_join("T", b"IDX", b"DATA") == b"A2MS" + b"T" + struct.pack("<I", 3) + b"IDX" + b"DATA"


def test_dq9_filter_takes_loose_and_picture_files_without_reading_them():
    def no_read(entry):
        raise AssertionError("the data of a plain file must not be read")

    assert dq9._wanted(ImageFile("data/bin/res.nat", 0, 0), no_read)
    assert dq9._wanted(ImageFile("data/menu/title.pac", 0, 0), no_read)
    assert not dq9._wanted(ImageFile("data/bin/other.bin", 0, 0), no_read)


def test_dq9_filter_skips_an_archive_that_is_not_gpc2():
    assert not dq9._wanted(ImageFile("data/x.gp2", 0, 4), lambda entry: b"NOPE")
