"""In-place writer of a Wii disc's DATA partition: patch files of an ISO copy, then re-hash and re-encrypt the clusters.

The title key comes from the ticket (decrypted with the Wii common key). A cluster is a 0x400-byte hash block and
0x7C00 bytes of data, both encrypted with the title key; the data IV is the 16 bytes at 0x3D0 of the encrypted hash
block. A changed group gets new hashes H0..H2, H3 and the TMD (fake-signed, as the owner's Twilight Princess and
Metroid build do). A file that grows moves to the first free gap of the partition; nothing else moves, so an
unchanged file gives a byte-identical disc. Reads and writes use the decrypted view of the partition.
"""
from __future__ import annotations

import hashlib
import struct
from typing import BinaryIO, Dict, List, Tuple

CLUSTER, HASHES, DATA = 0x8000, 0x400, 0x7C00
GROUP = 64
PARTITION_TABLE = 0x40000
DATA_TYPE = 0
ZERO_IV = bytes(16)


def _aes(key: bytes, iv: bytes):
    from Crypto.Cipher import AES  # pycryptodome, imported here as in console_crypto
    return AES.new(key, AES.MODE_CBC, iv)


def title_key(stream: BinaryIO, common_key: bytes) -> bytes:
    """The title key of the DATA partition of a Wii ISO (its ticket, decrypted with ``common_key``)."""
    part = data_partition(stream)
    header = _read(stream, part, 0x2C0)
    if header[0x1F1]:
        raise ValueError("the Wii partition uses a common key other than the first; not supported")
    title_id = header[0x1DC:0x1E4]
    return _aes(common_key, title_id + bytes(8)).decrypt(header[0x1BF:0x1CF])


def _read(stream: BinaryIO, at: int, size: int) -> bytes:
    stream.seek(at)
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("the image ends before the Wii partition data")
    return data


def data_partition(stream: BinaryIO) -> int:
    """Byte offset of the DATA partition (type 0) of a Wii disc."""
    count, table = struct.unpack(">II", _read(stream, PARTITION_TABLE, 8))
    if not count:
        raise ValueError("the Wii disc has no partitions")
    groups = _read(stream, table << 2, 8 * count)
    for index in range(count):
        offset, kind = struct.unpack_from(">II", groups, 8 * index)
        if kind == DATA_TYPE:
            return offset << 2
    raise ValueError("the Wii disc has no DATA partition")


class Partition:
    """The DATA partition of a Wii disc image opened for in-place patching, with a cache of decrypted groups."""

    def __init__(self, stream: BinaryIO, offset: int, key: bytes) -> None:
        self.f, self.off, self.key = stream, offset, key
        head = self._disc(offset, 0x2C0)
        self.tmd_size, tmd_off = struct.unpack_from(">II", head, 0x2A4)
        self.tmd_off = offset + (tmd_off << 2)
        self.h3_off = offset + (struct.unpack_from(">I", head, 0x2B4)[0] << 2)
        self.data_off = offset + (struct.unpack_from(">I", head, 0x2B8)[0] << 2)
        self.clusters = (struct.unpack_from(">I", head, 0x2BC)[0] << 2) // CLUSTER
        self.groups: Dict[int, List[list]] = {}
        self.dirty: set = set()

    def _disc(self, at: int, size: int) -> bytes:
        self.f.seek(at)
        return self.f.read(size)

    def _load(self, group: int) -> List[list]:
        if group not in self.groups:
            first = group * GROUP
            count = min(GROUP, self.clusters - first)
            raw = self._disc(self.data_off + first * CLUSTER, count * CLUSTER)
            items = []
            for i in range(count):
                c = raw[i * CLUSTER:(i + 1) * CLUSTER]
                h = _aes(self.key, ZERO_IV).decrypt(c[:HASHES])
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
                raise ValueError("a file does not fit in the DATA partition")
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
                eh = _aes(self.key, ZERO_IV).encrypt(bytes(h))
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
        tmd[0x04:0x104] = bytes(0x100)                        # fake-sign: zero signature, then a filler whose
        for n in range(0x10000):                              # body hash starts with 00
            struct.pack_into(">H", tmd, 0x1D2, n)
            if hashlib.sha1(bytes(tmd[0x140:])).digest()[0] == 0:
                break
        self.f.seek(self.tmd_off)
        self.f.write(tmd)


def files_of(part: Partition) -> Tuple[Dict[str, Tuple[int, int, int]], int]:
    """``({path: (FST entry offset, file offset, size)}, end of the FST)`` of the partition's file system."""
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

    walk(1, count, "")
    return out, fst_off + fst_size


def patch_stream(stream: BinaryIO, key: bytes, changes: Dict[str, bytes], say=None) -> None:
    """Write ``{path: bytes}`` (paths of the DATA partition's files, no ``files/`` prefix) into the disc on ``stream``."""
    part = Partition(stream, data_partition(stream), key)
    table, fst_end = files_of(part)
    used = {rel: (a, a + s) for rel, (_e, a, s) in table.items()}
    capacity = part.clusters * DATA
    for rel, blob in changes.items():
        if rel not in table:
            raise ValueError(f"{rel}: no such file on the disc (new files are not written)")
        entry, offset, size = table[rel]
        spans = sorted([(0, fst_end)] + [span for other, span in used.items() if other != rel])
        room = min([a for a, _b in spans if a > offset] or [capacity]) - offset
        if len(blob) > room:
            # Retail Wii discs keep their files at the end of the partition: take the first free gap.
            offset = None
            for (_a, end), (start, _b) in zip(spans, spans[1:] + [(capacity, capacity)]):
                at = (end + 0x7FFF) // 0x8000 * 0x8000
                if at + len(blob) <= start:
                    offset = at
                    break
            if offset is None:
                raise ValueError(f"{rel} does not fit in the DATA partition")
            if say is not None:
                say(f"{rel}: larger than the original, moved to a free place of the partition ({offset:#x})")
        used[rel] = (offset, offset + len(blob))
        part.write(offset, blob)
        if offset == table[rel][1] and len(blob) < size:
            part.write(offset + len(blob), bytes(size - len(blob)))
        part.write(entry + 4, struct.pack(">II", offset >> 2, len(blob)))
    part.flush()


def patch_iso(path: str, key: bytes, changes: Dict[str, bytes], say=None) -> None:
    """``patch_stream`` on the ISO file at ``path`` (the file is changed in place: pass a copy)."""
    with open(path, "r+b") as stream:
        patch_stream(stream, key, changes, say)

