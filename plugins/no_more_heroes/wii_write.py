"""Write changed files into the DATA partition of a Wii disc image in place.

Core reads Wii discs (``core/containers/wii_disc.py``) but has no writer. The clusters are decrypted, patched,
re-hashed (H0..H3), encrypted again, and the TMD gets the new H3 hash and is fake-signed. A file that grows moves to
the first free gap of the partition. The title key is decrypted from the ticket with the common key, as core does.
Ported from the owner's ``zt/tpwii.py`` and ``zt/ikenie.py``; an unchanged input gives the same bytes.
"""
from __future__ import annotations

import hashlib
import struct
from typing import BinaryIO, Dict, Tuple

from core.containers.wii_disc import CLUSTER
from core.i18n import tr

HASHES, DATA, GROUP = 0x400, 0x7C00, 64
PARTITION_TABLE = 0x40000


def _aes(key: bytes, iv: bytes):
    from Crypto.Cipher import AES  # pycryptodome, as core/containers/wii_disc.py imports it
    return AES.new(key, AES.MODE_CBC, iv)


def data_partition(stream: BinaryIO) -> int:
    """The byte offset of the DATA partition (type 0) in the partition table."""
    stream.seek(PARTITION_TABLE)
    count, table = struct.unpack(">II", stream.read(8))
    stream.seek(table << 2)
    for _ in range(count):
        offset, kind = struct.unpack(">II", stream.read(8))
        if kind == 0:
            return offset << 2
    raise ValueError(tr("the disc has no DATA partition"))


def title_key(stream: BinaryIO, part_at: int, common_key: bytes) -> bytes:
    """The decrypted title key of the partition at ``part_at`` (from its ticket)."""
    stream.seek(part_at)
    header = stream.read(0x2C0)
    return _aes(common_key, header[0x1DC:0x1E4] + bytes(8)).decrypt(header[0x1BF:0x1CF])


class Partition:
    """The DATA partition opened for in-place patching; offsets are the decrypted data's."""

    def __init__(self, stream: BinaryIO, offset: int, key: bytes) -> None:
        self.f, self.off, self.key = stream, offset, key
        head = self._disc(offset, 0x2C0)
        self.tmd_size, tmd_off = struct.unpack_from(">II", head, 0x2A4)
        self.tmd_off = offset + (tmd_off << 2)
        self.h3_off = offset + (struct.unpack_from(">I", head, 0x2B4)[0] << 2)
        self.data_off = offset + (struct.unpack_from(">I", head, 0x2B8)[0] << 2)
        self.clusters = (struct.unpack_from(">I", head, 0x2BC)[0] << 2) // CLUSTER
        self.groups: Dict[int, list] = {}      # group -> [[hash block, data] per cluster], decrypted
        self.dirty: set = set()

    def _disc(self, at: int, size: int) -> bytes:
        self.f.seek(at)
        return self.f.read(size)

    def _load(self, group: int) -> list:
        if group not in self.groups:
            first = group * GROUP
            count = min(GROUP, self.clusters - first)
            raw = self._disc(self.data_off + first * CLUSTER, count * CLUSTER)
            items = []
            for i in range(count):
                c = raw[i * CLUSTER:(i + 1) * CLUSTER]
                h = _aes(self.key, bytes(16)).decrypt(c[:HASHES])
                d = _aes(self.key, c[0x3D0:0x3E0]).decrypt(c[HASHES:])
                items.append([bytearray(h), bytearray(d)])
            self.groups[group] = items
        return self.groups[group]

    def read(self, at: int, size: int) -> bytes:
        out = bytearray()
        while size > 0:
            cluster, inner = divmod(at, DATA)
            take = min(size, DATA - inner)
            out += self._load(cluster // GROUP)[cluster % GROUP][1][inner:inner + take]
            at, size = at + take, size - take
        return bytes(out)

    def write(self, at: int, blob: bytes) -> None:
        pos = 0
        while pos < len(blob):
            cluster, inner = divmod(at + pos, DATA)
            if cluster >= self.clusters:
                raise ValueError(tr("a file does not fit the DATA partition of the disc"))
            take = min(len(blob) - pos, DATA - inner)
            self._load(cluster // GROUP)[cluster % GROUP][1][inner:inner + take] = blob[pos:pos + take]
            self.dirty.add(cluster // GROUP)
            pos += take

    def flush(self) -> None:
        """Re-hash and encrypt every changed group, then update H3 and the TMD (fake-signed)."""
        if not self.dirty:
            return
        h3 = bytearray(self._disc(self.h3_off, 0x18000))
        old_h3 = bytes(h3)
        for group in sorted(self.dirty):
            items = self.groups[group]
            for h, d in items:
                h[0:0x26C] = b"".join(hashlib.sha1(d[i * 0x400:(i + 1) * 0x400]).digest() for i in range(31))
            h2 = bytearray(items[0][0][0x340:0x3E0])
            for sub in range(0, len(items), 8):
                block = items[sub:sub + 8]
                h1 = bytearray(block[0][0][0x280:0x320])
                for j, (h, _d) in enumerate(block):
                    h1[j * 20:(j + 1) * 20] = hashlib.sha1(bytes(h[0:0x26C])).digest()
                for h, _d in block:
                    h[0x280:0x320] = h1
                h2[(sub // 8) * 20:(sub // 8 + 1) * 20] = hashlib.sha1(bytes(h1)).digest()
            out = bytearray()
            for h, d in items:
                h[0x340:0x3E0] = h2
                eh = _aes(self.key, bytes(16)).encrypt(bytes(h))
                out += eh + _aes(self.key, eh[0x3D0:0x3E0]).encrypt(bytes(d))
            self.f.seek(self.data_off + group * GROUP * CLUSTER)
            self.f.write(out)
            h3[group * 20:(group + 1) * 20] = hashlib.sha1(bytes(h2)).digest()
        self.dirty.clear()
        if bytes(h3) == old_h3:          # the same data written back: the signed TMD stays valid
            return
        self.f.seek(self.h3_off)
        self.f.write(h3)
        tmd = bytearray(self._disc(self.tmd_off, self.tmd_size))
        tmd[0x1F4:0x208] = hashlib.sha1(bytes(h3)).digest()   # content 0 hash
        tmd[0x04:0x104] = bytes(0x100)                        # fake-sign: zero RSA signature, then
        for n in range(0x10000):                              # find a filler whose body hash starts with 00
            struct.pack_into(">H", tmd, 0x1D2, n)
            if hashlib.sha1(bytes(tmd[0x140:])).digest()[0] == 0:
                break
        self.f.seek(self.tmd_off)
        self.f.write(tmd)


def fst_files(part: Partition) -> Tuple[Dict[str, Tuple[int, int, int]], int]:
    """``({'files/<path>': (FST entry offset, file offset, size)}, end of the FST)``, in the decrypted data."""
    boot = part.read(0, 0x440)
    fst_off, fst_size = (v << 2 for v in struct.unpack_from(">II", boot, 0x424))
    fst = part.read(fst_off, fst_size)
    count = struct.unpack_from(">I", fst, 8)[0]
    names = count * 12
    out: Dict[str, Tuple[int, int, int]] = {}

    def walk(first: int, end: int, prefix: str) -> None:
        i = first
        while i < end:
            word, a, b = struct.unpack_from(">III", fst, i * 12)
            at = names + (word & 0xFFFFFF)
            name = fst[at:fst.index(b"\0", at)].decode("shift_jis", "replace")
            if word >> 24:
                walk(i + 1, b, prefix + name + "/")
                i = b
            else:
                out[prefix + name] = (fst_off + i * 12, a << 2, b)
                i += 1

    walk(1, count, "files/")
    return out, fst_off + fst_size


def write_changes(stream: BinaryIO, common_key: bytes, changes: Dict[str, bytes]) -> None:
    """Write ``{'files/...': bytes, 'sys/main.dol': bytes}`` into the DATA partition of the disc open in ``stream``.

    A file keeps its place when the new bytes fit (the tail is zero-filled); a file that grew moves to the first
    free gap. ``sys/main.dol`` may change only within its size. No new files: a path the disc does not hold fails.
    """
    part_at = data_partition(stream)
    part = Partition(stream, part_at, title_key(stream, part_at, common_key))
    table, fst_end = fst_files(part)
    used = {rel: (a, a + s) for rel, (_e, a, s) in table.items()}
    capacity = part.clusters * DATA
    for rel, blob in changes.items():
        if rel.startswith("files/"):
            _write_file(part, table, used, fst_end, capacity, rel, blob)
    dol = changes.get("sys/main.dol")
    if dol is not None:
        at = struct.unpack_from(">I", part.read(0x420, 4))[0] << 2
        head = part.read(at, 0x100)
        room = max(o + s for o, s in zip(struct.unpack_from(">18I", head), struct.unpack_from(">18I", head, 0x90)))
        if len(dol) > room:
            raise ValueError(tr("main.dol is larger than the original ({0} > {1})", len(dol), room))
        part.write(at, dol)
    part.flush()


def _write_file(part: Partition, table: dict, used: dict, fst_end: int, capacity: int, rel: str, blob: bytes) -> None:
    if rel not in table:
        raise ValueError(tr("{0} is not a file of the disc (new files are not supported)", rel))
    entry, offset, size = table[rel]
    spans = sorted([(0, fst_end)] + [span for other, span in used.items() if other != rel])
    room = min([a for a, _b in spans if a > offset] or [capacity]) - offset
    if len(blob) > room:
        offset = None
        for (_a, end), (start, _b) in zip(spans, spans[1:] + [(capacity, capacity)]):
            at = (end + 0x7FFF) // 0x8000 * 0x8000
            if at + len(blob) <= start:
                offset = at
                break
        if offset is None:
            raise ValueError(tr("{0} does not fit the DATA partition of the disc", rel))
    used[rel] = (offset, offset + len(blob))
    part.write(offset, blob)
    if offset == table[rel][1] and len(blob) < size:
        part.write(offset + len(blob), bytes(size - len(blob)))
    part.write(entry + 4, struct.pack(">II", offset >> 2, len(blob)))
