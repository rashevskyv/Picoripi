"""Subtitle box of Conker: Live & Reloaded (Xbox): the wrap width, the line limit and the fixed height in default.xbe.

The layout routine of the subtitle bubble (see the recomp session's report) uses three constants. Each site is checked
against the bytes of the original XBE before it is changed; a site whose bytes differ refuses the whole patch.

- Wrap width: a 32-bit immediate, 20 characters, at two sites (the wrap test and the width passed on).
- Line limit: an 8-bit immediate, 4 lines, at four compares (two layout routines, two checks each).
- Fixed height: a float, 160.0, for a bubble with more lines than the limit.

Virtual addresses map to file offsets through the XBE section table. A site that crosses a section end is refused.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

ORIGINAL_WRAP = 20
ORIGINAL_LINES = 4
ORIGINAL_HEIGHT = 160.0
WRAP_VAS = (0x000DFDF7, 0x000DFE24)           # imm32 of "mov dword [esp+0x14], 20" and "mov eax, 20"
LINE_VAS = (0x000E0B9E, 0x000E0C03, 0x000E129A, 0x000E12FE)   # imm8 of the four "cmp ..., 4"
HEIGHT_VA = 0x00649428                        # float32 160.0
MAX_LINES = 127                               # cmp takes a sign-extended 8-bit immediate
MAX_WRAP = 0x7FFFFFFF


class XbeError(ValueError):
    """The bytes are not the expected XBE, or a patch cannot be applied to them."""


@dataclass(frozen=True)
class Section:
    va: int
    virtual_size: int
    raw: int
    raw_size: int


@dataclass(frozen=True)
class Site:
    """One byte patch: file offset, the bytes the original holds, the new bytes, and what it is for."""

    offset: int
    expected: bytes
    new: bytes
    note: str


def sections(xbe: bytes) -> List[Section]:
    """The section table of an XBE (header 0x104 base, 0x11C count, 0x120 table address; 0x38 bytes an entry)."""
    if xbe[:4] != b"XBEH":
        raise XbeError("not an XBE file")
    base = struct.unpack_from("<I", xbe, 0x104)[0]
    count = struct.unpack_from("<I", xbe, 0x11C)[0]
    table = struct.unpack_from("<I", xbe, 0x120)[0] - base
    out: List[Section] = []
    for index in range(count):
        at = table + 0x38 * index
        if at + 0x38 > len(xbe):
            raise XbeError("the section table runs past the end of the file")
        _flags, va, vsize, raw, rsize = struct.unpack_from("<IIIII", xbe, at)
        out.append(Section(va, vsize, raw, rsize))
    return out


def va_to_offset(xbe: bytes, va: int, length: int) -> int:
    """The file offset of ``length`` bytes at virtual address ``va``; they must lie inside one section."""
    for section in sections(xbe):
        if section.va <= va and va + length <= section.va + section.virtual_size:
            offset = section.raw + (va - section.va)
            if offset + length > len(xbe):
                raise XbeError(f"the bytes at 0x{va:08X} lie past the end of the file")
            return offset
    raise XbeError(f"0x{va:08X} is not inside a section")


def _height_bytes(height: float) -> bytes:
    return struct.pack("<f", height)


def box_sites(xbe: bytes, wrap: int = ORIGINAL_WRAP, lines: int = ORIGINAL_LINES,
              height: Optional[float] = None) -> Tuple[Site, ...]:
    """The byte patches for a subtitle box. ``height=None`` leaves the fixed height alone."""
    if not 1 <= wrap <= MAX_WRAP:
        raise XbeError("the wrap width must be a positive number of characters")
    if not 1 <= lines <= MAX_LINES:
        raise XbeError(f"the line limit must be between 1 and {MAX_LINES}")
    sites: List[Site] = []
    for va in WRAP_VAS:
        sites.append(Site(va_to_offset(xbe, va, 4), struct.pack("<I", ORIGINAL_WRAP), struct.pack("<I", wrap),
                          "wrap width"))
    for va in LINE_VAS:
        sites.append(Site(va_to_offset(xbe, va, 1), bytes([ORIGINAL_LINES]), bytes([lines]), "line limit"))
    if height is not None:
        if not height > 0:
            raise XbeError("the height must be positive")
        sites.append(Site(va_to_offset(xbe, HEIGHT_VA, 4), _height_bytes(ORIGINAL_HEIGHT), _height_bytes(height),
                          "fixed height"))
    return tuple(sites)


def scaled_height(lines: int) -> float:
    """The fixed height for a line limit: the original 160.0 for 4 lines, in proportion for other limits."""
    return ORIGINAL_HEIGHT * lines / ORIGINAL_LINES


def apply_sites(xbe: bytes, sites: Sequence[Site]) -> bytes:
    """Return the XBE with the sites changed. Raises ``XbeError`` if any site does not hold its expected bytes."""
    out = bytearray(xbe)
    for site in sites:
        if len(site.expected) != len(site.new):
            raise XbeError(f"{site.note} at 0x{site.offset:X} changes its length")
        end = site.offset + len(site.expected)
        if end > len(xbe):
            raise XbeError(f"{site.note} at 0x{site.offset:X} lies outside the file")
        if bytes(out[site.offset:end]) != site.expected:
            raise XbeError(f"{site.note}: the bytes at 0x{site.offset:X} are not the original ones")
        out[site.offset:end] = site.new
    return bytes(out)


def patched_box(xbe: bytes, wrap: int, lines: int, height: Optional[float]) -> bytes:
    """The XBE with the subtitle box changed: the wrap width, the line limit and (if ``height``) the fixed height."""
    return apply_sites(xbe, box_sites(xbe, wrap=wrap, lines=lines, height=height))
