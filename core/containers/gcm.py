"""GameCube disc images (plain .iso or .gcm): the header, the file system table (FST) and the file list.

``entries`` gives the layout DolphinTool writes: ``sys/`` (boot.bin, bi2.bin, apploader.img, fst.bin, main.dol)
and ``files/`` (the disc's file system). Only the header, the FST and the bytes a caller asks for are read.
Wii discs, RVZ, WIA and NKit images are not read here: they raise ImageError.
"""
from __future__ import annotations

import struct
from typing import BinaryIO, List

from core.containers.image_files import ImageError, ImageFile, ImageReader, check_name

GC_MAGIC = 0xC2339F3D
WII_MAGIC = 0x5D1C9EA3
HEADER_SIZE = 0x440
BI2_SIZE = 0x2000
APPLOADER_OFFSET = 0x2440
FST_ENTRY = 12
MAX_DEPTH = 64


def u32be(data: bytes, at: int) -> int:
    return struct.unpack_from(">I", data, at)[0]


def is_gamecube_header(head: bytes) -> bool:
    return len(head) >= HEADER_SIZE and u32be(head, 0x1C) == GC_MAGIC


class GameCubeImage(ImageReader):
    def __init__(self, stream: BinaryIO) -> None:
        super().__init__(stream)
        head = self.read_at(0, min(self.size, HEADER_SIZE))
        if len(head) < HEADER_SIZE:
            raise ImageError("the image is shorter than a GameCube disc header")
        if u32be(head, 0x18) == WII_MAGIC:
            raise ImageError("a Wii disc: its files need a key, which Picoripi does not read yet")
        if not is_gamecube_header(head):
            raise ImageError("not a GameCube disc image")
        self.game_id = head[:6].decode("ascii", "replace")
        self.disc_number = head[6]
        self._head = head
        self._dol_at, self._fst_at, self._fst_size = struct.unpack_from(">III", head, 0x420)

    def entries(self) -> List[ImageFile]:
        """The ``sys/`` files, then every file of the disc under ``files/``."""
        dol_size = self._dol_size()
        return [
            ImageFile("sys/boot.bin", 0, HEADER_SIZE),
            ImageFile("sys/bi2.bin", HEADER_SIZE, BI2_SIZE),
            ImageFile("sys/apploader.img", APPLOADER_OFFSET, self._apploader_size()),
            ImageFile("sys/fst.bin", self._fst_at, self._fst_size),
            ImageFile("sys/main.dol", self._dol_at, dol_size),
            *self._fst_files(),
        ]

    def _apploader_size(self) -> int:
        """The apploader header (0x20) plus its code (size field) plus the trailer (trailer field)."""
        fields = self.read_at(APPLOADER_OFFSET + 0x14, 8)
        return 0x20 + u32be(fields, 0) + u32be(fields, 4)

    def _dol_size(self) -> int:
        """The DOL header's sections: the end of the last one (text and data, offset plus size)."""
        head = self.read_at(self._dol_at, 0x100)
        offsets = struct.unpack_from(">18I", head, 0)
        sizes = struct.unpack_from(">18I", head, 0x90)
        return max(offset + size for offset, size in zip(offsets, sizes))

    def _fst_files(self) -> List[ImageFile]:
        fst = self.read_table(self._fst_at, self._fst_size)
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
                    found.append(ImageFile(f"files/{prefix}{name}", offset, size))
                    index += 1

        walk(1, count, "", 0)
        return found
