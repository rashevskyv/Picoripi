"""Windows PE program (.exe): its largest application icon, read from the resource section.

The RT_GROUP_ICON entry names the icons; the RT_ICON payloads (PNG or DIB) are put into one in-memory ``.ico``
file, which Pillow opens. Resource data offsets are RVAs and are mapped through the section table.
"""
from __future__ import annotations

import io
import struct
from typing import Dict, List, Optional, Tuple

from PIL import Image

from core.game_icons.common import FileSource

RT_ICON, RT_GROUP_ICON = 3, 14
DIR_BIT = 0x80000000


def _sections(src: FileSource, opt_at: int, nsec: int, opt_size: int) -> List[Tuple[int, int, int, int]]:
    table = src.take(opt_at + opt_size, nsec * 40)
    out = []
    for i in range(nsec):
        vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", table, i * 40 + 8)
        out.append((va, max(vsize, rawsize), rawptr, rawsize))
    return out


def _to_file(sections, rva: int) -> int:
    for va, span, rawptr, _rawsize in sections:
        if va <= rva < va + span:
            return rawptr + rva - va
    raise ValueError("RVA outside the sections")


def _leaves(chunk: bytes, at: int, path: Tuple[int, ...]):
    _c, _t, _mj, _mn, named, ids = struct.unpack_from("<IIHHHH", chunk, at)
    for i in range(named + ids):
        name_id, child = struct.unpack_from("<II", chunk, at + 16 + 8 * i)
        if child & DIR_BIT:
            yield from _leaves(chunk, child & ~DIR_BIT, path + (name_id,))
        else:
            yield path + (name_id,), child


def _icon_file(group: bytes, icons: Dict[int, bytes]) -> Optional[bytes]:
    count = struct.unpack_from("<H", group, 4)[0]
    best = None
    for i in range(count):
        w, h, colours, _r, planes, bpp, size, icon_id = struct.unpack_from("<BBBBHHIH", group, 6 + 14 * i)
        if icon_id not in icons:
            continue
        key = ((w or 256) * (h or 256), bpp)
        if best is None or key > best[0]:
            best = (key, (w, h, colours, planes, bpp, icons[icon_id]))
    if best is None:
        return None
    w, h, colours, planes, bpp, payload = best[1]
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", w, h, colours, 0, planes, bpp, len(payload), 6 + 16)
    return header + entry + payload


def read(src: FileSource) -> Optional[Image.Image]:
    if src.take(0, 2) != b"MZ":
        return None
    (pe_at,) = struct.unpack("<I", src.take(0x3C, 4))
    pe = src.take(pe_at, 24)
    if pe[:4] != b"PE\0\0":
        return None
    nsec = struct.unpack_from("<H", pe, 6)[0]
    opt_size = struct.unpack_from("<H", pe, 20)[0]
    opt_at = pe_at + 24
    magic = struct.unpack("<H", src.take(opt_at, 2))[0]
    if magic == 0x10B:
        dirs_at = opt_at + 96
    elif magic == 0x20B:
        dirs_at = opt_at + 112
    else:
        return None
    rsrc_rva, rsrc_size = struct.unpack("<II", src.take(dirs_at + 16, 8))
    if rsrc_rva == 0 or rsrc_size == 0:
        return None
    sections = _sections(src, opt_at, nsec, opt_size)
    chunk = src.take(_to_file(sections, rsrc_rva), rsrc_size)
    groups: Dict[int, bytes] = {}
    icons: Dict[int, bytes] = {}
    for path, entry_at in _leaves(chunk, 0, ()):
        if not path or path[0] not in (RT_ICON, RT_GROUP_ICON) or len(path) < 2:
            continue
        rva, size, _cp, _res = struct.unpack_from("<IIII", chunk, entry_at)
        data = src.take(_to_file(sections, rva), size)
        if path[0] == RT_GROUP_ICON:
            groups.setdefault(path[1], data)
        else:
            icons.setdefault(path[1], data)
    for group in groups.values():
        icon = _icon_file(group, icons)
        if icon is not None:
            return Image.open(io.BytesIO(icon))
    return None
