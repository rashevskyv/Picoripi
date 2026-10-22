"""The RomFS of a Switch update as the game reads it: the base RomFS with the update's BKTR patch applied.

An update's RomFS section is a patch. An indirect table maps each virtual range to a place: storage 0 is the base
RomFS, storage 1 is the patch data. The patch data is AES-CTR encrypted, and a second table gives each range a
generation number that goes into the counter. Both tables are bucket trees; only shallow trees (one offset node and
its entry sets) are read. A deeper tree raises ImageError.

``PatchSection`` reads the decrypted bytes of the patch section; ``PatchedRomFs`` is the virtual RomFS. The keys are
passed in by the caller and never stored here.
"""
from __future__ import annotations

from core.i18n import tr
import bisect
import struct
from typing import Any, Callable, List, Optional

from core.containers.console_crypto import PlainView, read_raw
from core.containers.image_files import ImageError

BKTR = b"BKTR"
NODE_STRIDE = 0x4000   # each entry set of a shallow tree starts this many bytes after the one before
IND_ENTRY = 0x14       # virtual offset, physical offset, storage index
CTR_ENTRY = 0x10       # offset, and the generation at 0x0C
CRYPTO_NONE = 1


def _ctr(key: bytes, iv: bytes, data: bytes) -> bytes:
    from Crypto.Cipher import AES
    from Crypto.Util import Counter
    counter = Counter.new(128, initial_value=int.from_bytes(iv, "big"))
    return AES.new(key, AES.MODE_CTR, counter=counter).decrypt(data)


class PatchSection:
    """The decrypted bytes of one update section. ``start`` is the section's offset inside the NCA; ``base`` is the
    NCA's offset in ``stream``. ``plain`` means the bytes are stored decrypted (an NCZ's copy)."""

    def __init__(self, stream: Any, base: int, start: int, key: bytes, fsh: bytes, plain: bool) -> None:
        self._stream = stream
        self._base = base
        self._start = start
        self._key = key
        self._crypto = fsh[4]
        self._plain = plain
        self._iv = bytearray(fsh[0x140:0x148][::-1] + b"\0" * 8)

    def __call__(self, offset: int, size: int, generation: Optional[int] = None) -> bytes:
        """``size`` bytes at section offset ``offset``; ``generation`` selects the AES-CTR generation of that range."""
        abs_off = self._start + offset
        aligned = abs_off & ~0xF
        pad = abs_off - aligned
        raw = read_raw(self._stream, self._base + aligned, size + pad)
        if self._plain or self._crypto == CRYPTO_NONE:
            return raw[pad:pad + size]
        iv = bytearray(self._iv)
        if generation is not None:
            iv[4:8] = struct.pack(">I", generation)
        iv[8:16] = struct.pack(">Q", aligned >> 4)
        return _ctr(self._key, bytes(iv), raw)[pad:pad + size]


def _shallow_tree(read: Callable[[int, int], bytes], table_off: int, entry_size: int, total: int) -> List[bytes]:
    """The entries of a shallow bucket tree at ``table_off``; ImageError when the count does not match."""
    _index, sets, _end = struct.unpack("<iiq", read(table_off, 0x10))
    entries: List[bytes] = []
    for s in range(sets):
        set_off = table_off + NODE_STRIDE * (s + 1)
        _i, count, _e = struct.unpack("<iiq", read(set_off, 0x10))
        blob = read(set_off + 0x10, count * entry_size)
        entries.extend(blob[k * entry_size:(k + 1) * entry_size] for k in range(count))
    if len(entries) != total:
        raise ImageError(tr("a bucket tree is deeper than this reader reads"))
    return entries


class PatchedRomFs(PlainView):
    """The update's RomFS: ranges from the base RomFS (``base``, a readable view) or from the patch data."""

    def __init__(self, base: PlainView, patch: PatchSection, fsh: bytes, size: int) -> None:
        super().__init__(size)
        self._base = base
        self._patch = patch
        if fsh[0x110:0x114] != BKTR or fsh[0x130:0x134] != BKTR:
            raise ImageError(tr("the RomFS section is not a BKTR patch"))
        ind_off = struct.unpack_from("<Q", fsh, 0x100)[0]
        ind_n = struct.unpack_from("<i", fsh, 0x118)[0]
        ctr_off = struct.unpack_from("<Q", fsh, 0x120)[0]
        ctr_n = struct.unpack_from("<i", fsh, 0x138)[0]
        ind = [struct.unpack("<qqi", e) for e in _shallow_tree(patch, ind_off, IND_ENTRY, ind_n)]
        ctr = [(struct.unpack_from("<q", e)[0], struct.unpack_from("<I", e, 0xC)[0])
               for e in _shallow_tree(patch, ctr_off, CTR_ENTRY, ctr_n)]
        self._ind = ind
        self._ind_keys = [virt for virt, _phys, _storage in ind]
        self._ctr = ctr
        self._ctr_keys = [offset for offset, _generation in ctr]
        self._ctr_end = ind_off

    def _plain(self, offset: int, size: int) -> bytes:
        out = bytearray()
        while size > 0:
            i = bisect.bisect_right(self._ind_keys, offset) - 1
            if i < 0:
                raise ImageError(tr("a RomFS read starts before the first patch range"))
            virt, phys, storage = self._ind[i]
            nxt = self._ind_keys[i + 1] if i + 1 < len(self._ind_keys) else self.size
            count = min(size, nxt - offset)
            place = phys + (offset - virt)
            out += self._from_base(place, count) if storage == 0 else self._from_patch(place, count)
            offset += count
            size -= count
        return bytes(out)

    def _from_base(self, place: int, count: int) -> bytes:
        self._base.seek(place)
        data = self._base.read(count)
        if len(data) != count:
            raise ImageError(tr("the base RomFS ends inside a patch range"))
        return data

    def _from_patch(self, place: int, count: int) -> bytes:
        out = bytearray()
        while count > 0:
            i = bisect.bisect_right(self._ctr_keys, place) - 1
            if i < 0:
                raise ImageError(tr("a patch read starts before the first generation range"))
            nxt = self._ctr_keys[i + 1] if i + 1 < len(self._ctr_keys) else self._ctr_end
            take = min(count, nxt - place)
            out += self._patch(place, take, self._ctr[i][1])
            place += take
            count -= take
        return bytes(out)
