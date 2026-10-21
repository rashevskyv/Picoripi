"""The NCZ table reader refuses a block size that would make it hold more than 16 MiB at once."""
import io
import struct

import pytest

from core.containers.image_files import ImageError, ImageReader
from core.containers.switch_nsz import MAX_BLOCK_EXP, NCA_HEADER_SIZE, read_ncz


def _ncz(exp: int) -> ImageReader:
    """One 0x10000-byte section after the NCA header copy, then an NCZBLOCK header with one block of 2**exp bytes."""
    table = b"NCZSECTN" + struct.pack("<Q", 1) + struct.pack("<3Q", NCA_HEADER_SIZE, 0x10000, 0).ljust(0x40, b"\0")
    blocks = b"NCZBLOCK" + bytes([2, 1, 0, exp]) + struct.pack("<IQ", 1, 0x10000) + struct.pack("<I", 0x100)
    return ImageReader(io.BytesIO(bytes(NCA_HEADER_SIZE) + table + blocks + bytes(0x100)))


def test_a_block_size_above_16_mib_is_refused_and_16_mib_is_read():
    assert MAX_BLOCK_EXP == 24
    assert read_ncz(_ncz(24)).block_exp == 24
    with pytest.raises(ImageError, match="block size is out of range"):
        read_ncz(_ncz(32))                     # a hostile header asking for 4 GiB blocks


def test_an_update_with_more_than_four_contiguous_sections_is_read():
    """nsz writes one section entry per AES-CTR-EX subsection of an update's patch (17 in Yo-kai Watch 1's update)."""
    entries = b"".join(struct.pack("<3Q", NCA_HEADER_SIZE + 0x100 * index, 0x100, 3).ljust(0x40, b"\0")
                       for index in range(17))
    table = b"NCZSECTN" + struct.pack("<Q", 17) + entries
    ncz = read_ncz(ImageReader(io.BytesIO(bytes(NCA_HEADER_SIZE) + table + bytes(17 * 0x100))))
    assert len(ncz.sections) == 17 and ncz.body_size == 17 * 0x100
