"""The sparse layer of a Switch NCA section: its bucket tree maps logical offsets to physical bytes, and the rest reads as zeros.

A section with a sparse layer has a bucket tree (``SparseInfo`` in the section's FS header): the table is AES-CTR encrypted
with the section's upper IV, its generation replaced by the sparse generation. The tree maps each logical range to storage
0 (the physical data, at ``physical_offset`` in the NCA) or storage 1 (zeros). The section's own CTR, if any, is applied
after the sparse mapping, by logical offset. Only a two-level tree (one offset node and its entry sets) is read.
"""
from __future__ import annotations

import bisect
import struct
from typing import Any, List, Tuple

from core.containers.console_crypto import BLOCK, CtrView, PlainView, read_raw
from core.containers.image_files import ImageError
from core.containers.switch_bktr import _shallow_tree
from core.i18n import tr

SPARSE_TABLE_AT = 0x148       # TableOffset (u64), TableSize (u64), BKTR header (16 bytes), PhysicalOffset (u64), Generation (u16)
ENTRY_COUNT_AT = 0x160        # entry count inside the BKTR header
PHYSICAL_OFFSET_AT = 0x168
GENERATION_AT = 0x170
ENTRY = struct.Struct("<qqi")  # virtual offset, physical offset, storage index: 0x14 bytes
STORAGE_DATA = 0
STORAGE_ZERO = 1


def is_sparse(fsh: bytes) -> bool:
    """True when the section has a sparse layer (a BKTR bucket tree in its FS header)."""
    return fsh[0x158:0x15C] == b"BKTR"


def is_empty_sparse(fsh: bytes) -> bool:
    """True for a sparse section whose tree has no entries: every logical byte is zero before the section's CTR."""
    return is_sparse(fsh) and struct.unpack_from("<I", fsh, ENTRY_COUNT_AT)[0] == 0


def _sparse_upper(fsh: bytes) -> int:
    """The AES-CTR upper IV of the sparse table: the section's secure value with the sparse generation (``gen << 16``)."""
    secure = struct.unpack_from("<I", fsh, 0x144)[0]
    generation = struct.unpack_from("<H", fsh, GENERATION_AT)[0]
    return ((secure << 32) | (generation << 16)) << 64


def read_entries(stream: Any, nca_offset: int, key: bytes, fsh: bytes, nca_size: int) -> List[Tuple[int, int, int]]:
    """The mapped ranges of a sparse section, sorted by virtual offset: (virtual, physical, storage index)."""
    table_off, table_size = struct.unpack_from("<QQ", fsh, SPARSE_TABLE_AT)
    physical_offset = struct.unpack_from("<Q", fsh, PHYSICAL_OFFSET_AT)[0]
    total = struct.unpack_from("<I", fsh, ENTRY_COUNT_AT)[0]
    meta = physical_offset + table_off
    if meta % BLOCK or meta + table_size > nca_size:
        raise ImageError(tr("the sparse table of the section is not inside its NCA"))
    upper = _sparse_upper(fsh)

    def read(offset: int, size: int) -> bytes:
        return CtrView(stream, nca_offset + meta + offset, size, key, upper | ((meta + offset) // BLOCK)).read(size)

    entries = [ENTRY.unpack(e) for e in _shallow_tree(read, 0, ENTRY.size, total)]
    virtuals = [virt for virt, _phys, _storage in entries]
    if virtuals != sorted(virtuals) or any(storage not in (STORAGE_DATA, STORAGE_ZERO) for *_x, storage in entries):
        raise ImageError(tr("the sparse table of the section is not sorted or has a bad storage index"))
    return entries


class SparseView(PlainView):
    """The logical bytes of a sparse section before its own CTR: mapped ranges from the NCA, others zeros."""

    def __init__(self, stream: Any, nca_offset: int, physical_offset: int,
                 entries: List[Tuple[int, int, int]], size: int) -> None:
        super().__init__(size)
        self._stream = stream
        self._nca = nca_offset
        self._physical = physical_offset
        self._entries = entries
        self._virtuals = [virt for virt, _phys, _storage in entries]

    def _plain(self, offset: int, size: int) -> bytes:
        out = bytearray()
        while size > 0:
            i = bisect.bisect_right(self._virtuals, offset) - 1
            if i < 0:
                raise ImageError(tr("a sparse section read starts before its first range"))
            virt, phys, storage = self._entries[i]
            end = self._virtuals[i + 1] if i + 1 < len(self._virtuals) else self.size
            count = min(size, end - offset)
            if storage == STORAGE_ZERO:
                out += bytes(count)
            else:
                out += read_raw(self._stream, self._nca + self._physical + phys + (offset - virt), count)
            offset += count
            size -= count
        return bytes(out)


def open_sparse_section(stream: Any, nca_offset: int, section: Tuple[int, int, bytes], key: bytes,
                        nca_size: int) -> PlainView:
    """The decrypted logical view of a sparse section: the sparse mapping, then the section's CTR (crypto type 3) if any."""
    start, end, fsh = section
    size = end - start
    if is_empty_sparse(fsh):
        entries = [(0, 0, STORAGE_ZERO)]
    else:
        entries = read_entries(stream, nca_offset, key, fsh, nca_size)
    physical_offset = struct.unpack_from("<Q", fsh, PHYSICAL_OFFSET_AT)[0]
    sparse = SparseView(stream, nca_offset, physical_offset, entries, size)
    crypto = fsh[4]
    if crypto == 1:
        return sparse
    if crypto == 3:
        counter = (int.from_bytes(fsh[0x140:0x148], "little") << 64) | (start // BLOCK)
        return CtrView(sparse, 0, size, key, counter)
    raise ImageError(tr("a section uses encryption type {0}, which is not read", crypto))
