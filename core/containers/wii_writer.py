"""The Wii disc writer: change the files of a Wii disc's DATA partition in place, or write a plain ISO from a WIA or RVZ.

A cluster is a 0x400-byte hash block and 0x7C00 bytes of data, both encrypted with the title key; the data IV is the 16
bytes at 0x3D0 of the encrypted hash block. A changed group gets new hashes H0..H2, a new H3 entry and a new TMD (fake
signed: the TMD signature is zeroed and a filler is searched). A file that grows moves to the first free gap of the
partition; nothing else moves, so an unchanged file gives a byte-identical disc.

A WIA or RVZ image holds each partition decrypted, with its hash blocks removed. ``copy_as_iso`` copies such an image
to a plain ISO and seals every partition again (hashes, H3, encryption) with the title key from its ticket. The raw
areas (disc header, partition table, tickets, TMDs, H3 tables) are copied as they are, so an unchanged RVZ gives the
same ISO as the disc it was made from.

The title key comes from the ticket, decrypted with the common key (the console key store). Keys are never printed.
"""
from __future__ import annotations

import hashlib
import struct
from typing import BinaryIO, Callable, Dict, Tuple

from core.containers.image_files import ImageError
from core.containers.wia import WiaStream, is_wia_or_rvz
from core.i18n import tr

CLUSTER, HASH_BLOCK, CLUSTER_DATA = 0x8000, 0x400, 0x7C00
GROUP = 64                  # clusters per group (one H3 entry each)
H3_SIZE = 0x18000
PARTITION_TABLE = 0x40000
PARTITION_HEADER = 0x2C0    # the ticket and the offsets that follow it
DATA_PARTITION = 0
DATA_IV_AT = 0x3D0
ZERO_IV = bytes(16)
COPY_CHUNK = 8 << 20
Progress = Callable[[int, str], None]


def _aes(key: bytes, iv: bytes):
    from Crypto.Cipher import AES  # pycryptodome, as core/containers/wii_disc.py imports it
    return AES.new(key, AES.MODE_CBC, iv)


def _read(stream: BinaryIO, at: int, size: int) -> bytes:
    stream.seek(at)
    data = stream.read(size)
    if len(data) != size:
        raise ImageError(tr("the image ends inside a Wii partition"))
    return data


def partitions(stream: BinaryIO) -> list:
    """``[(partition offset, type)]`` of every Wii partition in the partition table."""
    out = []
    for group in range(4):
        count, table_at = struct.unpack(">II", _read(stream, PARTITION_TABLE + group * 8, 8))
        if not count:
            continue
        table = _read(stream, table_at << 2, count * 8)
        for index in range(count):
            part_at, kind = struct.unpack_from(">II", table, index * 8)
            out.append((part_at << 2, kind))
    return out


def data_partition(stream: BinaryIO) -> int:
    """The byte offset of the DATA partition (type 0) of a Wii disc."""
    for part_at, kind in partitions(stream):
        if kind == DATA_PARTITION:
            return part_at
    raise ImageError(tr("the disc has no DATA partition"))


def title_key(stream: BinaryIO, part_at: int, common_key: bytes) -> bytes:
    """The decrypted title key of the partition at ``part_at`` (from its ticket, with the common key)."""
    header = _read(stream, part_at, PARTITION_HEADER)
    if header[0x1F1]:
        raise ImageError(tr("the Wii partition uses common key {0}, which is not supported", header[0x1F1]))
    return _aes(common_key, header[0x1DC:0x1E4] + bytes(8)).decrypt(header[0x1BF:0x1CF])


class Layout:
    """Where a partition keeps its TMD, H3 table, data and cluster count (read from its header)."""

    def __init__(self, stream: BinaryIO, part_at: int) -> None:
        head = _read(stream, part_at, PARTITION_HEADER)
        self.part_at = part_at
        self.tmd_size = struct.unpack_from(">I", head, 0x2A4)[0]
        self.tmd_at = part_at + (struct.unpack_from(">I", head, 0x2A8)[0] << 2)
        self.h3_at = part_at + (struct.unpack_from(">I", head, 0x2B4)[0] << 2)
        self.data_at = part_at + (struct.unpack_from(">I", head, 0x2B8)[0] << 2)
        self.clusters = (struct.unpack_from(">I", head, 0x2BC)[0] << 2) // CLUSTER


def seal_group(items: list, key: bytes) -> Tuple[bytes, bytes]:
    """Hash and encrypt one group. ``items`` is ``[[hash block, data], ...]`` of bytearrays, one per cluster, changed in
    place: H0 of every cluster, H1 of every 8-cluster subgroup, and H2 (the same in every hash block).

    Returns ``(encrypted group, H2 table)``. The group's H3 entry is the SHA-1 of the H2 table. A last group with fewer
    than ``GROUP`` clusters is hashed as if the missing clusters held zero data (retail discs hash them so); only the
    ``items`` clusters are encrypted and returned.
    """
    real = len(items)
    items = items + [[bytearray(HASH_BLOCK), bytearray(CLUSTER_DATA)] for _ in range(GROUP - real)]
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
    for h, d in items[:real]:
        h[0x340:0x3E0] = h2
        eh = _aes(key, ZERO_IV).encrypt(bytes(h))
        out += eh + _aes(key, eh[0x3D0:0x3E0]).encrypt(bytes(d))
    return bytes(out), bytes(h2)


def _update_h3_and_tmd(stream: BinaryIO, lay: Layout, h3: bytes, old: bytes) -> None:
    """Write a changed H3 table and fake-sign the TMD that holds its hash. An unchanged H3 keeps the TMD as it is."""
    if h3 == old:
        return
    stream.seek(lay.h3_at)
    stream.write(h3)
    stream.seek(lay.tmd_at)
    tmd = bytearray(_read(stream, lay.tmd_at, lay.tmd_size))
    tmd[0x1F4:0x208] = hashlib.sha1(h3).digest()          # content 0 hash
    tmd[0x04:0x104] = bytes(0x100)                        # fake-sign: zero signature, then a filler whose
    for n in range(0x10000):                              # body hash starts with 00
        struct.pack_into(">H", tmd, 0x1D2, n)
        if hashlib.sha1(bytes(tmd[0x140:])).digest()[0] == 0:
            break
    stream.seek(lay.tmd_at)
    stream.write(tmd)


class Partition:
    """A DATA partition opened for in-place patching: its decrypted clusters are cached per group."""

    def __init__(self, stream: BinaryIO, part_at: int, key: bytes) -> None:
        self.f, self.key = stream, key
        self.lay = Layout(stream, part_at)
        self.clusters = self.lay.clusters
        self.groups: Dict[int, list] = {}      # group -> [[hash block, data] per cluster], decrypted
        self.dirty: set = set()

    def _load(self, group: int) -> list:
        if group not in self.groups:
            first = group * GROUP
            count = min(GROUP, self.clusters - first)
            raw = _read(self.f, self.lay.data_at + first * CLUSTER, count * CLUSTER)
            items = []
            for i in range(count):
                c = raw[i * CLUSTER:(i + 1) * CLUSTER]
                h = _aes(self.key, ZERO_IV).decrypt(c[:HASH_BLOCK])
                d = _aes(self.key, c[DATA_IV_AT:DATA_IV_AT + 16]).decrypt(c[HASH_BLOCK:])
                items.append([bytearray(h), bytearray(d)])
            self.groups[group] = items
        return self.groups[group]

    def read(self, at: int, size: int) -> bytes:
        out = bytearray()
        while size > 0:
            cluster, inner = divmod(at, CLUSTER_DATA)
            take = min(size, CLUSTER_DATA - inner)
            out += self._load(cluster // GROUP)[cluster % GROUP][1][inner:inner + take]
            at, size = at + take, size - take
        return bytes(out)

    def write(self, at: int, blob: bytes) -> None:
        pos = 0
        while pos < len(blob):
            cluster, inner = divmod(at + pos, CLUSTER_DATA)
            if cluster >= self.clusters:
                raise ValueError(tr("a file does not fit the DATA partition of the disc"))
            take = min(len(blob) - pos, CLUSTER_DATA - inner)
            self._load(cluster // GROUP)[cluster % GROUP][1][inner:inner + take] = blob[pos:pos + take]
            self.dirty.add(cluster // GROUP)
            pos += take

    def flush(self) -> None:
        """Seal every changed group, then write H3 and the TMD."""
        if not self.dirty:
            return
        h3 = bytearray(_read(self.f, self.lay.h3_at, H3_SIZE))
        old = bytes(h3)
        for group in sorted(self.dirty):
            enc, h2 = seal_group(self.groups[group], self.key)
            self.f.seek(self.lay.data_at + group * GROUP * CLUSTER)
            self.f.write(enc)
            h3[group * 20:(group + 1) * 20] = hashlib.sha1(h2).digest()
        self.dirty.clear()
        _update_h3_and_tmd(self.f, self.lay, bytes(h3), old)


def files_of(part: Partition) -> Tuple[Dict[str, Tuple[int, int, int]], int]:
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
    table, fst_end = files_of(part)
    used = {rel: (a, a + s) for rel, (_e, a, s) in table.items()}
    capacity = part.clusters * CLUSTER_DATA
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


def copy_as_iso(image: str, dst: str, common_key: bytes, progress: Progress,
                is_cancelled: Callable[[], bool]) -> bool:
    """Write the plain ISO of the disc ``image`` (an ISO, or a WIA or RVZ) to ``dst``; False when cancelled.

    An ISO is copied as it is. A WIA or RVZ is copied raw, then every partition it holds is sealed again: hashes,
    H3 and encryption, with the title key from its ticket. An unchanged image gives the disc the image was made from.
    """
    with open(image, "rb") as src:
        magic = src.read(4)
        if not is_wia_or_rvz(magic):
            src.seek(0)
            with open(dst, "wb") as out:
                done = 0
                total = src.seek(0, 2) or 1
                src.seek(0)
                while True:
                    if is_cancelled():
                        return False
                    chunk = src.read(COPY_CHUNK)
                    if not chunk:
                        return True
                    out.write(chunk)
                    done += len(chunk)
                    progress(70 * done // total, tr("Copying the disc image"))
    with open(image, "rb") as src, WiaStream(src) as wia_disc, open(dst, "w+b") as out:
        total = wia_disc.size or 1
        done = 0
        wia_disc.seek(0)
        while True:
            if is_cancelled():
                return False
            chunk = wia_disc.read(COPY_CHUNK)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            progress(70 * done // total, tr("Copying the disc image"))
        for part_at, _kind in partitions(out):
            try:
                plain = wia_disc.partition_view(_data_at(out, part_at))
            except ImageError:
                continue   # a partition the image holds no data for stays as the copy has it
            if not _seal_plain(out, part_at, title_key(out, part_at, common_key), plain, progress, is_cancelled):
                return False
        out.flush()
    return True


def _data_at(stream: BinaryIO, part_at: int) -> int:
    return part_at + (struct.unpack_from(">I", _read(stream, part_at, PARTITION_HEADER), 0x2B8)[0] << 2)


def _seal_plain(out: BinaryIO, part_at: int, key: bytes, plain, progress: Progress,
                is_cancelled: Callable[[], bool]) -> bool:
    """Write the encrypted clusters of one partition from its decrypted data, group by group, then its H3 and TMD."""
    lay = Layout(out, part_at)
    h3_old = _read(out, lay.h3_at, H3_SIZE)
    h3 = bytearray(h3_old)
    for first in range(0, lay.clusters, GROUP):
        if is_cancelled():
            return False
        count = min(GROUP, lay.clusters - first)
        plain.seek(first * CLUSTER_DATA)
        data = plain.read(count * CLUSTER_DATA)
        items = [[bytearray(HASH_BLOCK), bytearray(data[i * CLUSTER_DATA:(i + 1) * CLUSTER_DATA])]
                 for i in range(count)]
        enc, h2 = seal_group(items, key)
        out.seek(lay.data_at + first * CLUSTER)
        out.write(enc)
        h3[(first // GROUP) * 20:(first // GROUP + 1) * 20] = hashlib.sha1(h2).digest()
        progress(70 + 25 * (first + count) // max(1, lay.clusters), tr("Re-encrypting the Wii partition"))
    _update_h3_and_tmd(out, lay, bytes(h3), h3_old)
    return True
