"""The compression layer of a Switch NCA section (firmware 12 and later): the RomFS as the game reads it.

A compressed RomFS section keeps its data in blocks: stored, zero-filled or LZ4. A bucket tree (``BKTR``, in the section's
FS header at 0x178: table offset, table size, then the tree header) maps each logical offset to one block. The tree and
the blocks sit inside the section, counted from its IVFC data level (FS header 0x90). The logical space keeps the section
bytes before the level as they are (the IVFC hash levels), then the RomFS image from the level on.

``CompressedView`` is that logical space as a seekable view: decrypted stored bytes in, plain bytes out. Only the one-node
root of the tree and its entry sets are read; a deeper tree is refused. ``lz4_decode`` is the LZ4 block format with every
offset and length checked, so a damaged block raises ImageError and never reads past its input.
"""
from __future__ import annotations

import bisect
import struct
from typing import Dict, List, Tuple

from core.containers.console_crypto import PlainView, read_raw
from core.containers.image_files import ImageError
from core.containers.switch_bktr import _shallow_tree
from core.i18n import tr

TABLE_AT = 0x178            # table offset (s64), table size (s64), then the BKTR header
BKTR = b"BKTR"
BKTR_AT = 0x188             # magic, version (u32), entry count (u32)
LEVEL_AT = 0x90             # the IVFC data level: the RomFS image starts here
ENTRY = struct.Struct("<qqBbHI")   # logical offset, stored offset, type, level, reserved, stored size: 0x18 bytes
STORED, ZERO, LZ4 = 0, 1, 3
MAX_ENTRIES = 1 << 20       # no real RomFS has more blocks; caps a looping or damaged table
CACHE_BLOCKS = 8            # decoded LZ4 blocks kept: a file read in chunks does not decode its block again


def is_compressed(fsh: bytes) -> bool:
    """True when the section's FS header holds a compression table."""
    return fsh[BKTR_AT:BKTR_AT + 4] == BKTR and struct.unpack_from("<q", fsh, TABLE_AT + 8)[0] != 0


def lz4_decode(src: bytes, out_size: int) -> bytes:
    """One LZ4 block (no frame header) decoded to exactly ``out_size`` bytes. ImageError for a damaged block."""
    out = bytearray()
    i, end = 0, len(src)

    def length(value: int) -> int:
        nonlocal i
        if value == 15:
            while True:
                if i >= end:
                    raise ImageError(tr("a compressed block is cut short"))
                extra = src[i]
                i += 1
                value += extra
                if extra != 255:
                    return value
        return value

    while True:
        if i >= end:
            raise ImageError(tr("a compressed block is cut short"))
        token = src[i]
        i += 1
        literals = length(token >> 4)
        if i + literals > end or len(out) + literals > out_size:
            raise ImageError(tr("a compressed block has a bad literal length"))
        out += src[i:i + literals]
        i += literals
        if i == end:
            break
        if i + 2 > end:
            raise ImageError(tr("a compressed block is cut short"))
        offset = src[i] | src[i + 1] << 8
        i += 2
        if not 0 < offset <= len(out):
            raise ImageError(tr("a compressed block has a bad match offset"))
        match = length(token & 15) + 4
        if len(out) + match > out_size:
            raise ImageError(tr("a compressed block has a bad match length"))
        start = len(out) - offset
        if offset >= match:
            out += out[start:start + match]
        else:   # the match overlaps what it copies: repeat the last ``offset`` bytes
            out += (out[start:] * (match // offset + 1))[:match]
    if len(out) != out_size:
        raise ImageError(tr("a compressed block decodes to the wrong size"))
    return bytes(out)


class CompressedView(PlainView):
    """The logical space of a compressed RomFS section over ``stored``, the decrypted section bytes."""

    def __init__(self, stored: PlainView, fsh: bytes) -> None:
        if not is_compressed(fsh):
            raise ImageError(tr("the section has no compression table"))
        self._stored = stored
        self._level = struct.unpack_from("<Q", fsh, LEVEL_AT)[0]
        table_at, table_size = struct.unpack_from("<qq", fsh, TABLE_AT)
        _magic, _version, total = struct.unpack_from("<4sII", fsh, BKTR_AT)
        if table_at < 0 or table_size < 0 or total > MAX_ENTRIES or self._level + table_at > stored.size:
            raise ImageError(tr("the compression table of the section is not inside it"))
        self._table = self._level + table_at

        def read(offset: int, size: int) -> bytes:
            return read_raw(stored, self._table + offset, size)

        _index, _sets, logical_end = struct.unpack("<iiq", read(0, 0x10))
        entries = [ENTRY.unpack(raw) for raw in _shallow_tree(read, 0, ENTRY.size, total)]
        keys = [entry[0] for entry in entries]
        if not entries or keys[0] != 0 or any(a >= b for a, b in zip(keys, keys[1:])) or logical_end <= keys[-1]:
            raise ImageError(tr("the compression table of the section is not sorted"))
        for _virt, phys, kind, _lvl, _res, _size in entries:
            if kind not in (STORED, ZERO, LZ4):
                raise ImageError(tr("compression type {0} is not read", kind))
            if phys < 0:
                raise ImageError(tr("a compressed block starts before the section"))
        self._entries: List[Tuple[int, int, int, int]] = [(v, p, k, s) for v, p, k, _l, _r, s in entries]
        self._keys = keys
        self._end = logical_end
        self._cache: Dict[int, bytes] = {}
        super().__init__(self._level + logical_end)

    def _block_end(self, index: int) -> int:
        return self._keys[index + 1] if index + 1 < len(self._keys) else self._end

    def _decoded(self, index: int) -> bytes:
        got = self._cache.get(index)
        if got is not None:
            return got
        virt, phys, _kind, size = self._entries[index]
        raw = read_raw(self._stored, self._level + phys, size)
        data = lz4_decode(raw, self._block_end(index) - virt)
        if len(self._cache) >= CACHE_BLOCKS:
            self._cache.pop(next(iter(self._cache)))
        self._cache[index] = data
        return data

    def _plain(self, offset: int, size: int) -> bytes:
        out = bytearray()
        while size > 0:
            if offset < self._level:   # the section bytes before the RomFS level: no compression
                take = min(size, self._level - offset)
                out += read_raw(self._stored, offset, take)
            else:
                rel = offset - self._level
                index = bisect.bisect_right(self._keys, rel) - 1
                virt, phys, kind, _size = self._entries[index]
                take = min(size, self._block_end(index) - rel)
                if kind == STORED:
                    out += read_raw(self._stored, self._level + phys + rel - virt, take)
                elif kind == ZERO:
                    out += bytes(take)
                else:
                    out += self._decoded(index)[rel - virt:rel - virt + take]
            offset += take
            size -= take
        return bytes(out)
