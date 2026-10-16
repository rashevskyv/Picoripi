"""Wii discs: the disc header (``locate``), the key file (``load_common_key``) and the reader (``WiiImage``).

``WiiImage`` reads a Wii disc with one data partition and common key index 0. It decrypts the partition with the
title key from the ticket, then lists the files like a GameCube disc (``sys/`` and ``files/``). The partition's
cluster hash blocks are not verified. Refused: the Korean and vWii common keys, a disc with no data partition. Update
and channel partitions are ignored. A WIA or RVZ image (``core.containers.wia.WiaStream``) stores the partition
decrypted, so it is read with no key: pass the stream and ``None``.
"""
from __future__ import annotations

import struct
from typing import Any, BinaryIO, Dict, List, Optional

from core.containers.console_crypto import BLOCK, CbcView, PlainView, read_raw, wrong_key_error
from core.containers.gcm import APPLOADER_OFFSET, BI2_SIZE, FST_ENTRY, HEADER_SIZE, MAX_DEPTH, u32be
from core.containers.image_files import MAX_TABLE, ImageError, ImageFile, ImageReader, check_name
from core.containers.wia import WiaStream

WII_MAGIC_AT = 0x18
WII_MAGIC = 0x5D1C9EA3
PARTITION_TABLE = 0x40000
PARTITION_HEADER = 0x2C0  # the ticket (0x2A4 bytes) and the offsets that follow it
DATA_PARTITION = 0
MAX_PARTITIONS = 32  # per group; a real disc has a handful
KEYS_SIZE = 0x400
COMMON_KEY_AT = 0x158
CLUSTER = 0x8000
HASH_BLOCK = 0x400
CLUSTER_DATA = CLUSTER - HASH_BLOCK  # 0x7C00
DATA_IV_AT = 0x3D0  # the 16 IV bytes of a cluster's data, inside its encrypted hash block


def locate(head: bytes) -> Optional[Dict[str, Any]]:
    """``{"kind": "wii", "game_id", ...}`` for a Wii disc header, or None."""
    if len(head) < 0x20 or struct.unpack_from(">I", head, WII_MAGIC_AT)[0] != WII_MAGIC:
        return None
    game_id = head[:6].decode("ascii", "replace")
    return {"kind": "wii", "game_id": game_id, "title_id": game_id, "encrypted": True, "title_kind": "",
            "revision": head[7]}


def load_common_key(path: str) -> bytes:
    """The 16-byte common key of a keys.bin file (exactly 0x400 bytes; the key is at 0x158)."""
    try:
        with open(path, "rb") as handle:
            data = handle.read(KEYS_SIZE + 1)
    except OSError:
        raise ImageError("the Wii key file cannot be read") from None
    if len(data) != KEYS_SIZE:
        raise ImageError("the Wii key file must be 0x400 bytes")
    return data[COMMON_KEY_AT:COMMON_KEY_AT + BLOCK]


class WiiDataView(PlainView):
    """The decrypted user data of a Wii partition. A cluster is a 0x400-byte hash block and 0x7C00 bytes of data, both
    encrypted with the title key. The data IV is the 16 bytes at 0x3D0 of the encrypted hash block, so the hash block
    itself is never decrypted."""

    def __init__(self, parent: BinaryIO, base: int, clusters: int, key: bytes) -> None:
        super().__init__(clusters * CLUSTER_DATA)
        self._parent = parent
        self._base = base
        self._key = key

    def _plain(self, offset: int, size: int) -> bytes:
        if offset + size > self.size:
            raise ImageError("the image ends inside a decrypted section")
        parts = []
        while size > 0:
            index, inner = divmod(offset, CLUSTER_DATA)
            count = min(size, CLUSTER_DATA - inner)
            start = self._base + index * CLUSTER
            iv = read_raw(self._parent, start + DATA_IV_AT, BLOCK)
            view = CbcView(self._parent, start + HASH_BLOCK, CLUSTER_DATA, self._key, iv)
            view.seek(inner)
            parts.append(view.read(count))
            offset += count
            size -= count
        return b"".join(parts)


class WiiImage(ImageReader):
    """A Wii disc image: its data partition, decrypted with ``common_key``, as a GameCube-style file layout."""

    def __init__(self, stream: BinaryIO, common_key: Optional[bytes]) -> None:
        """``common_key`` is None for a WIA or RVZ stream: it holds the partition already decrypted."""
        super().__init__(stream)
        head = self.read_at(0, 0x20)
        if u32be(head, WII_MAGIC_AT) != WII_MAGIC:
            raise ImageError("not a Wii disc image")
        self.game_id = head[:6].decode("ascii", "replace")
        part = self._data_partition()
        header = self.read_at(part, PARTITION_HEADER)
        tmd_size, tmd_at = u32be(header, 0x2A4), u32be(header, 0x2A8) << 2
        if not tmd_size or part + tmd_at + tmd_size > self.size:
            raise ImageError("the Wii partition has no title metadata")
        data_at = part + (u32be(header, 0x2B8) << 2)
        clusters = (u32be(header, 0x2BC) << 2) // CLUSTER
        if not clusters or data_at + clusters * CLUSTER > self.size:
            raise ImageError("the Wii partition data is outside the image")
        if isinstance(stream, WiaStream):
            self._view = stream.partition_view(data_at)
        else:
            if header[0x1F1]:
                raise ImageError(f"the Wii partition uses common key {header[0x1F1]}, which is not supported")
            from Crypto.Cipher import AES  # pycryptodome, imported here as in console_crypto
            title_id = header[0x1DC:0x1E4]
            title_key = AES.new(common_key, AES.MODE_CBC, title_id + bytes(8)).decrypt(header[0x1BF:0x1CF])
            self._view = WiiDataView(stream, data_at, clusters, title_key)
        boot = read_raw(self._view, 0, HEADER_SIZE)
        if u32be(boot, WII_MAGIC_AT) != WII_MAGIC:
            if isinstance(stream, WiaStream):
                raise ImageError("the Wii partition data of this image is not a disc")
            raise wrong_key_error("Wii")
        self._dol_at = u32be(boot, 0x420) << 2
        self._fst_at = u32be(boot, 0x424) << 2
        self._fst_size = u32be(boot, 0x428) << 2  # divided by 4 on a Wii disc, like the two pointers above

    def entries(self) -> List[ImageFile]:
        """The ``sys/`` files, then every file of the disc under ``files/``. Offsets address the decrypted view."""
        view = self._view
        return [
            ImageFile("sys/boot.bin", 0, HEADER_SIZE, stream=view),
            ImageFile("sys/bi2.bin", HEADER_SIZE, BI2_SIZE, stream=view),
            ImageFile("sys/apploader.img", APPLOADER_OFFSET, self._apploader_size(), stream=view),
            ImageFile("sys/fst.bin", self._fst_at, self._fst_size, stream=view),
            ImageFile("sys/main.dol", self._dol_at, self._dol_size(), stream=view),
            *self._fst_files(),
        ]

    def _data_partition(self) -> int:
        """The byte offset of the first data partition (type 0) in the partition table."""
        for group in range(4):
            count, table_at = struct.unpack(">II", self.read_at(PARTITION_TABLE + group * 8, 8))
            if not count:
                continue
            if count > MAX_PARTITIONS:
                raise ImageError("the Wii partition table is too large")
            table = self.read_at(table_at << 2, count * 8)
            for index in range(count):
                part_at, kind = struct.unpack_from(">II", table, index * 8)
                if kind == DATA_PARTITION:
                    return part_at << 2
        raise ImageError("the Wii disc has no data partition")

    def _table(self, offset: int, size: int) -> bytes:
        """``size`` decrypted bytes at ``offset`` of the partition data, for a table: at most ``MAX_TABLE`` bytes."""
        if size > MAX_TABLE:
            raise ImageError(f"a table of {size:#x} bytes is too large")
        return read_raw(self._view, offset, size)

    def _apploader_size(self) -> int:
        """The apploader header (0x20) plus its code (size field) plus the trailer (trailer field)."""
        fields = self._table(APPLOADER_OFFSET + 0x14, 8)
        return 0x20 + u32be(fields, 0) + u32be(fields, 4)

    def _dol_size(self) -> int:
        """The DOL header's sections: the end of the last one (text and data, offset plus size)."""
        head = self._table(self._dol_at, 0x100)
        offsets = struct.unpack_from(">18I", head, 0)
        sizes = struct.unpack_from(">18I", head, 0x90)
        return max(offset + size for offset, size in zip(offsets, sizes))

    def _fst_files(self) -> List[ImageFile]:
        fst = self._table(self._fst_at, self._fst_size)
        if len(fst) < FST_ENTRY:
            raise ImageError("the file system table is empty")
        count = u32be(fst, 8)
        names_at = count * FST_ENTRY
        if count < 1 or names_at > len(fst):
            raise ImageError("the file system table does not hold its entries")
        found: List[ImageFile] = []
        listed = bytearray(count)  # each entry belongs to one directory; a second listing is a broken table

        def walk(first: int, end: int, prefix: str, depth: int) -> None:
            if depth > MAX_DEPTH:
                raise ImageError("the file system table nests too deep")
            if not (0 < first <= end <= count):
                raise ImageError("the file system table has a broken directory")
            index = first
            while index < end:
                if listed[index]:
                    raise ImageError("the file system table lists an entry twice")
                listed[index] = 1
                word, offset, size = struct.unpack_from(">III", fst, index * FST_ENTRY)
                name_at = names_at + (word & 0xFFFFFF)
                nul = fst.find(b"\0", name_at)
                if nul < 0:
                    raise ImageError("the file system table has an unterminated name")
                name = check_name(fst[name_at:nul].decode("shift_jis", "replace"))
                if word >> 24:
                    if size <= index:
                        raise ImageError("the file system table has a broken directory")
                    walk(index + 1, size, f"{prefix}{name}/", depth + 1)
                    index = size
                else:
                    # a file's offset is stored divided by 4 on a Wii disc
                    found.append(ImageFile(f"files/{prefix}{name}", offset << 2, size, stream=self._view))
                    index += 1

        walk(1, count, "", 0)
        return found
