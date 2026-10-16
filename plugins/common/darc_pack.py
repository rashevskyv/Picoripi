"""DARC archives inside Pokémon 3DS GARC members: list, rewrite, and find the darc inside a layout pack.

A DARC keeps a table of entries (flags, offset, size) and a name table. ``darc_replace`` writes new bytes for some
files and keeps the rest; files keep their order, and textures sit on 0x80 alignment, layouts on 8.
"""
from __future__ import annotations

import struct
from typing import Dict, Optional

from core.i18n import tr


class DarcError(ValueError):
    """The bytes are not a DARC this module can rewrite, or a file is missing."""


def darc_files(data: bytes) -> Dict[str, tuple]:
    """``{path: (offset, size)}`` of a DARC archive, in table order (folders joined with ``/``)."""
    _bom, _hlen, _ver, _fsize, toff, _tlen, _doff = struct.unpack_from("<HHIIIII", data, 4)
    count = struct.unpack_from("<I", data, toff + 8)[0]
    names_at = toff + count * 12
    files: Dict[str, tuple] = {}
    stack: list = []                                       # (end index, folder name)
    for i in range(count):
        flags, offset, size = struct.unpack_from("<III", data, toff + i * 12)
        at = end = names_at + (flags & 0xFFFFFF)
        while data[end:end + 2] != b"\0\0":                  # UTF-16 units up to the terminator
            end += 2
        name = data[at:end].decode("utf-16-le")
        while stack and i >= stack[-1][0]:
            stack.pop()
        if flags >> 24:
            stack.append((size, name))
        else:
            files["/".join([s for _, s in stack if s not in ("", ".")] + [name])] = (offset, size)
    return files


def darc_replace(data: bytes, members: Dict[str, bytes]) -> bytes:
    """The DARC with ``members`` ({path: bytes}) put in; the other files keep their bytes."""
    _bom, _hlen, _ver, _fsize, toff, _tlen, doff = struct.unpack_from("<HHIIIII", data, 4)
    files = darc_files(data)
    missing = set(members) - set(files)
    if missing:
        raise DarcError(tr("The darc has no file {0}.", ", ".join(sorted(missing))))
    out = bytearray(data[:doff])
    count = struct.unpack_from("<I", data, toff + 8)[0]
    index_of = {}
    for i in range(count):
        flags, offset, size = struct.unpack_from("<III", data, toff + i * 12)
        if not flags >> 24:
            index_of[(offset, size)] = i
    for path, (offset, size) in sorted(files.items(), key=lambda item: item[1][0]):
        blob = members.get(path, data[offset:offset + size])
        align = 8 if path.endswith((".bclan", ".bclyt")) else 0x80       # textures sit on 0x80, layouts on 8
        out += b"\0" * (-len(out) % align)
        struct.pack_into("<II", out, toff + index_of[(offset, size)] * 12 + 4, len(out), len(blob))
        out += blob
    struct.pack_into("<I", out, 0x0C, len(out))
    return bytes(out)


def pack_darc_at(plain: bytes) -> Optional[int]:
    """Offset of the DARC inside a layout pack (u32 n, n names of 64 bytes, padding, DARC), 0 for a bare DARC, else None."""
    if len(plain) < 0x80 + 0x1C or plain[:4] == b"darc":
        return 0 if plain[:4] == b"darc" else None
    n = struct.unpack_from("<I", plain)[0]
    if not 0 < n < 4096 or 4 + n * 64 > len(plain) or not plain[4:5].isalnum():
        return None
    p = 4 + n * 64
    while p + 0x1C <= len(plain) and p < 4 + n * 64 + 0x80000:
        if plain[p:p + 6] == b"darc\xff\xfe":
            return p
        p += 4
    return None
