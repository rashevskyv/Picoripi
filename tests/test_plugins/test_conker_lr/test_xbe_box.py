"""Conker: Live & Reloaded subtitle box in default.xbe: the sites hold the original bytes, change only where asked,
and refuse an XBE whose bytes or sections differ. The XBE is synthetic (built in the test)."""
import struct

import pytest

from plugins.conker_lr import xbe_box

BASE = 0x10000
FLOAT_240_VA = 0x640100  # an unreferenced float 240.0 in the data section of the synthetic XBE


def _xbe():
    """A small XBE: header fields, a section table, two sections that cover the box sites with the original bytes.
    The bubble's height is loaded from the shared 160.0 constant; a 240.0 constant sits unreferenced beside it."""
    xbe = bytearray(0x40000)
    xbe[0:4] = b"XBEH"
    struct.pack_into("<I", xbe, 0x104, BASE)
    sections = [(0xD0000, 0x20000, 0x1000, 0x20000), (0x640000, 0x10000, 0x21000, 0x10000)]
    struct.pack_into("<I", xbe, 0x11C, len(sections))
    struct.pack_into("<I", xbe, 0x120, BASE + 0x200)
    for index, (va, vsize, raw, rsize) in enumerate(sections):
        struct.pack_into("<IIIII", xbe, 0x200 + 0x38 * index, 0, va, vsize, raw, rsize)
    for va in xbe_box.WRAP_VAS:
        struct.pack_into("<I", xbe, xbe_box.va_to_offset(bytes(xbe), va, 4), xbe_box.ORIGINAL_WRAP)
    for va in xbe_box.LINE_VAS:
        xbe[xbe_box.va_to_offset(bytes(xbe), va, 1)] = xbe_box.ORIGINAL_LINES
    for va in xbe_box.HEIGHT_LOAD_VAS:
        struct.pack_into("<I", xbe, xbe_box.va_to_offset(bytes(xbe), va, 4), xbe_box.HEIGHT_CONST_VA)
    struct.pack_into("<f", xbe, xbe_box.va_to_offset(bytes(xbe), xbe_box.HEIGHT_CONST_VA, 4), 160.0)
    struct.pack_into("<f", xbe, xbe_box.va_to_offset(bytes(xbe), FLOAT_240_VA, 4), 240.0)
    return bytes(xbe)


def test_the_sites_change_to_the_new_values():
    xbe = _xbe()
    patched = xbe_box.patched_box(xbe, 40, 6, 240.0)
    for va in xbe_box.WRAP_VAS:
        assert struct.unpack_from("<I", patched, xbe_box.va_to_offset(xbe, va, 4))[0] == 40
    for va in xbe_box.LINE_VAS:
        assert patched[xbe_box.va_to_offset(xbe, va, 1)] == 6
    for va in xbe_box.HEIGHT_LOAD_VAS:
        assert struct.unpack_from("<I", patched, xbe_box.va_to_offset(xbe, va, 4))[0] == FLOAT_240_VA
    assert struct.unpack_from("<f", patched, xbe_box.va_to_offset(xbe, FLOAT_240_VA, 4))[0] == 240.0


def test_the_shared_160_constant_is_not_changed():
    xbe = _xbe()
    patched = xbe_box.patched_box(xbe, 40, 6, 240.0)
    offset = xbe_box.va_to_offset(xbe, xbe_box.HEIGHT_CONST_VA, 4)
    assert patched[offset:offset + 4] == xbe[offset:offset + 4]


def test_only_the_site_bytes_change():
    xbe = _xbe()
    patched = xbe_box.patched_box(xbe, 40, 6, 240.0)
    changed = {i for i in range(len(xbe)) if xbe[i] != patched[i]}
    allowed = set()
    for site in xbe_box.box_sites(xbe, 40, 6, 240.0):
        allowed.update(range(site.offset, site.offset + len(site.expected)))
    assert changed and changed <= allowed


def test_the_height_can_be_left_alone():
    xbe = _xbe()
    patched = xbe_box.patched_box(xbe, 40, 6, None)
    for va in xbe_box.HEIGHT_LOAD_VAS:
        assert struct.unpack_from("<I", patched, xbe_box.va_to_offset(xbe, va, 4))[0] == xbe_box.HEIGHT_CONST_VA


def test_the_original_values_give_the_same_bytes():
    xbe = _xbe()
    assert xbe_box.patched_box(xbe, xbe_box.ORIGINAL_WRAP, xbe_box.ORIGINAL_LINES, xbe_box.ORIGINAL_HEIGHT) == xbe


def test_a_site_with_other_bytes_refuses_the_patch():
    xbe = bytearray(_xbe())
    xbe[xbe_box.va_to_offset(bytes(xbe), xbe_box.LINE_VAS[2], 1)] = 0x05
    with pytest.raises(xbe_box.XbeError):
        xbe_box.patched_box(bytes(xbe), 40, 6, 240.0)


def test_a_height_constant_that_something_refers_to_is_not_used():
    xbe = bytearray(_xbe())
    struct.pack_into("<I", xbe, xbe_box.va_to_offset(bytes(xbe), 0x640200, 4), FLOAT_240_VA)  # a pointer to it
    with pytest.raises(xbe_box.XbeError):
        xbe_box.patched_box(bytes(xbe), 40, 6, 240.0)


def test_a_site_outside_its_section_is_refused():
    xbe = bytearray(_xbe())
    struct.pack_into("<I", xbe, 0x200 + 0x38 + 8, 0x100)  # the second section is now only 0x100 bytes long
    with pytest.raises(xbe_box.XbeError):
        xbe_box.patched_box(bytes(xbe), 40, 6, 240.0)


def test_a_file_that_is_not_an_xbe_is_refused():
    with pytest.raises(xbe_box.XbeError):
        xbe_box.sections(b"XXXX" + bytes(0x200))


def test_bad_settings_are_refused_and_the_scaled_height_follows_the_limit():
    xbe = _xbe()
    with pytest.raises(xbe_box.XbeError):
        xbe_box.patched_box(xbe, 0, 6, None)
    with pytest.raises(xbe_box.XbeError):
        xbe_box.patched_box(xbe, 40, 200, None)
    assert xbe_box.scaled_height(4) == 160.0
    assert xbe_box.scaled_height(6) == 240.0
