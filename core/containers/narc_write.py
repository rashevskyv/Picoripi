"""Writes a NARC archive with changed members: the layout of zt/pkgen5.py ``Narc.pack``, in core.

Members are 4-byte aligned with 0xFF filler. The BTAF table is rebuilt, the BTNF block is kept as it is, the GMIF block
holds the members and the total size in the header is written again. Unchanged members give the archive back as it is.
"""
from __future__ import annotations

import struct
from typing import Sequence

from core.containers.narc_members import narc_members

ALIGN = 4
FILLER = 0xFF


class NarcWriteError(ValueError):
    """The bytes are not a NARC archive this writer can rebuild."""


def _blocks(data: bytes) -> tuple:
    """(the header, the raw BTNF block or b"") of a NARC."""
    if data[:4] != b"NARC" or len(data) < 16:
        raise NarcWriteError("not a NARC archive")
    header = bytes(data[:16])
    btnf = b""
    at = struct.unpack_from("<H", data, 12)[0]
    while at + 8 <= len(data):
        magic, size = struct.unpack_from("<4sI", data, at)
        if magic == b"BTNF":
            btnf = bytes(data[at:at + size])
        if size < 8:
            break
        at += size
    return header, btnf


def _pack(header: bytes, btnf: bytes, members: Sequence[bytes]) -> bytes:
    fat = bytearray()
    body = bytearray()
    for member in members:
        body += bytes([FILLER]) * (-len(body) % ALIGN)
        fat += struct.pack("<II", len(body), len(body) + len(member))
        body += member
    body += bytes([FILLER]) * (-len(body) % ALIGN)
    btaf = b"BTAF" + struct.pack("<II", 12 + len(fat), len(members)) + bytes(fat)
    gmif = b"GMIF" + struct.pack("<I", 8 + len(body)) + bytes(body)
    total = 16 + len(btaf) + len(btnf) + len(gmif)
    return header[:8] + struct.pack("<I", total) + header[12:] + btaf + btnf + gmif


def narc_rebuild(data: bytes, members: Sequence[bytes]) -> bytes:
    """The NARC ``data`` with its members replaced by ``members`` (same count, in table order)."""
    try:
        original = narc_members(data)
    except ValueError as error:
        raise NarcWriteError(str(error)) from None
    members = [bytes(m) for m in members]
    if len(members) != len(original):
        raise NarcWriteError(f"the archive has {len(original)} members, not {len(members)}")
    if members == original:
        return bytes(data)
    header, btnf = _blocks(data)
    return _pack(header, btnf, members)


def narc_repack(data: bytes) -> bytes:
    """The NARC ``data`` laid out again with its own members: a check that the writer reproduces the archive."""
    header, btnf = _blocks(data)
    return _pack(header, btnf, narc_members(data))
