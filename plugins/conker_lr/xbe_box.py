"""Subtitle box of Conker: Live & Reloaded (Xbox): the wrap width, the line limit and the fixed height in default.xbe.

The layout routine of the subtitle bubble (see the recomp session's report) uses three constants. Each site is checked
against the bytes of the original XBE before it is changed; a site whose bytes differ refuses the whole patch.

- Wrap width: a 32-bit immediate, 20 characters, at two sites (the wrap test and the width passed on).
- Line limit: an 8-bit immediate, 4 lines, at four compares (two layout routines, two checks each).
- Fixed height: a bubble above the line limit gets a fixed height of 160.0. The float 0x00649428 is shared with other
  routines, so it is not changed. The two loads that read it for the bubble (movss in the layout routines) are pointed
  at a different float with the wanted value, found in a data section that nothing references.

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
HEIGHT_CONST_VA = 0x00649428                  # float32 160.0, read by the layout routines and by other code
HEIGHT_LOAD_VAS = (0x000E0BDE, 0x000E12D9)    # imm32 of "movss xmm0, [0x00649428]" in the two layout routines
MAX_LINES = 127                               # cmp takes a sign-extended 8-bit immediate
MAX_WRAP = 0x7FFFFFFF


class XbeError(ValueError):
    """The bytes are not the expected XBE, or a patch cannot be applied to them."""


@dataclass(frozen=True)
class Section:
    flags: int
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
        flags, va, vsize, raw, rsize = struct.unpack_from("<IIIII", xbe, at)
        out.append(Section(flags, va, vsize, raw, rsize))
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


def _referenced(xbe: bytes, va: int) -> bool:
    """True when some 32-bit value in the file equals ``va`` (an absolute address the code or a table may use)."""
    return xbe.find(struct.pack("<I", va)) >= 0


def height_constant(xbe: bytes, value: float) -> int:
    """The virtual address of a float32 ``value`` in a data section that no 32-bit value refers to.

    The first such address is used, so the choice is the same for the same XBE. The code section is not searched.
    """
    pattern = struct.pack("<f", value)
    code = [s for s in sections(xbe) if s.va <= LINE_VAS[0] < s.va + s.virtual_size]
    for section in sections(xbe):
        if section in code:  # the code section holds the sites, not constants
            continue
        start = section.raw
        end = min(len(xbe), section.raw + section.raw_size)  # the file holds only the raw part
        at = xbe.find(pattern, start, end)
        while at >= 0:
            va = section.va + (at - section.raw)
            if va % 4 == 0 and va - section.va < section.virtual_size and not _referenced(xbe, va):
                return va
            at = xbe.find(pattern, at + 1, end)
    raise XbeError(f"no unreferenced float {value} in the data sections")


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
        constant = HEIGHT_CONST_VA if height == ORIGINAL_HEIGHT else height_constant(xbe, height)
        for va in HEIGHT_LOAD_VAS:
            sites.append(Site(va_to_offset(xbe, va, 4), struct.pack("<I", HEIGHT_CONST_VA),
                              struct.pack("<I", constant), "fixed height load"))
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
