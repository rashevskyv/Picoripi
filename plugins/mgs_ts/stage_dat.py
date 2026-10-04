"""``stage.dat`` of Twin Snakes as an archive: the textures (and other files) of every stage.

Header (big endian): u32 build date, u16 version, u16 blocks, u16 stage count, u16 0xCCCC, u32 hash,
then per stage ``char name[8], u32 sector``. A stage at ``sector * 0x800``: ``u32 count``, ``count *
(u32 word, u32 value)``, then data from the next sector. The entries form folders: ``(0x7F0000nn,
unpacked size) (0x7E000000 | packed size, data offset) (ext << 24 | name hash, offset)... (0x7F000000,
size)``; a folder is one zlib stream at a sector, its files start 0x20-aligned.

Members are ``<stage>/<file word as 8 hex digits>.<kind>``. An ext 0x13 file is a texture pack
(``u32 count`` at 0x10, ``u32 TPL offset`` at 0x18, a 0x80-byte record per image, then a standard
TPL): its member, ``.tpl``, is that embedded TPL. Every other file is ``.bin``, as stored.

Packing re-deflates only the folders that changed (zlib level 9) and rebuilds only their stages. A
stage that still fits its old place stays there and nothing else moves; one that grew pushes the
stages after it (the table follows). Nothing changed gives the original bytes back. A file with one
stage (the workspace keeps the texture stages one per file) is the same format.
"""
from __future__ import annotations

import struct
import zlib
from typing import Dict, List, Optional, Tuple

from core.containers.base_container import BaseArchiveContainer

SECTOR = 0x800
PACK_EXT = 0x13
_FOLDER_END = 0x7F000000


def _align(value: int, step: int) -> int:
    return (value + step - 1) // step * step


class _Folder:
    """One zlib folder of a stage: where its entries are and the files in it."""

    def __init__(self, entry: int, word: int, csize: int, offset: int, files: List[Tuple[int, int]], end: int):
        self.entry, self.word, self.csize, self.offset, self.files, self.end = entry, word, csize, offset, files, end


class StageDatContainer(BaseArchiveContainer):
    """Twin Snakes ``stage.dat`` (or a file holding some of its stages)."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        if len(data) < SECTOR or data[0xA:0xC] != b"\xcc\xcc":
            return False
        count = struct.unpack_from(">H", data, 8)[0]
        if not count or 0x10 + 12 * count > SECTOR:
            return False
        for index in range(count):
            name = data[0x10 + 12 * index:0x18 + 12 * index].rstrip(b"\0")
            sector = struct.unpack_from(">I", data, 0x18 + 12 * index)[0]
            if not name or not all(0x20 < c < 0x7F for c in name) or not 0 < sector * SECTOR < len(data):
                return False
        return True

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        count = struct.unpack_from(">H", data, 8)[0]
        self._stages = [(data[0x10 + 12 * i:0x18 + 12 * i].split(b"\0")[0].decode("ascii"),
                         struct.unpack_from(">I", data, 0x18 + 12 * i)[0]) for i in range(count)]
        self._layouts: Dict[int, Tuple[int, List[Tuple[int, int]], List[_Folder]]] = {}
        self._members: Dict[str, Tuple[int, int, int]] = {}      # name -> (sector, folder index, file index)
        for name, sector in self._stages:
            _count, _ents, folders = self._layout(sector)
            for f, folder in enumerate(folders):
                for k, (word, _off) in enumerate(folder.files):
                    member = f"{name}/{word:08x}.{'tpl' if word >> 24 == PACK_EXT else 'bin'}"
                    if member in self._members:
                        member = f"{name}/{folder.word:08x}/{member.split('/', 1)[1]}"
                    self._members[member] = (sector, f, k)
        self._changes: Dict[Tuple[int, int, int], bytes] = {}
        self._cache: Optional[Tuple[Tuple[int, int], bytes]] = None

    # -- the table ------------------------------------------------------------------------------

    def _layout(self, sector: int) -> Tuple[int, List[Tuple[int, int]], List[_Folder]]:
        if sector in self._layouts:
            return self._layouts[sector]
        base = sector * SECTOR
        count = struct.unpack_from(">I", self._data, base)[0]
        ents = [struct.unpack_from(">II", self._data, base + 4 + 8 * j) for j in range(count)]
        folders, j = [], 0
        while j < count:
            word, _usize = ents[j]
            if word == 0 and _usize == 0:
                break
            if word >> 24 != 0x7F or word == _FOLDER_END or j + 1 >= count:
                raise ValueError(f"stage.dat: unknown entry {word:#x} at sector {sector:#x}")
            cword, offset = ents[j + 1]
            files, k = [], j + 2
            while k < count and ents[k][0] != _FOLDER_END:
                files.append(ents[k])
                k += 1
            if k >= count:
                raise ValueError(f"stage.dat: folder {word:#x} at sector {sector:#x} has no end")
            folders.append(_Folder(j, word, cword & 0xFFFFFF, offset, files, ents[k][1]))
            j = k + 1
        self._layouts[sector] = (count, ents, folders)
        return self._layouts[sector]

    def _data0(self, sector: int) -> int:
        return sector * SECTOR + _align(4 + 8 * self._layout(sector)[0], SECTOR)

    def _folder_bytes(self, sector: int, index: int) -> bytes:
        if self._cache and self._cache[0] == (sector, index):
            return self._cache[1]
        folder = self._layout(sector)[2][index]
        at = self._data0(sector) + folder.offset
        blob = zlib.decompress(self._data[at:at + folder.csize])
        self._cache = ((sector, index), blob)
        return blob

    def _stored(self, key: Tuple[int, int, int]) -> bytes:
        """The file as the stage holds it now (a pending change first)."""
        return self._changes[key] if key in self._changes else self._original(key)

    def _original(self, key: Tuple[int, int, int]) -> bytes:
        sector, f, k = key
        folder = self._layout(sector)[2][f]
        end = folder.files[k + 1][1] if k + 1 < len(folder.files) else folder.end
        return self._folder_bytes(sector, f)[folder.files[k][1]:end]

    def _key(self, path: str) -> Tuple[int, int, int]:
        try:
            return self._members[path]
        except KeyError:
            raise KeyError(f"No {path} in stage.dat") from None

    # -- the archive interface -------------------------------------------------------------------

    def list_files(self) -> List[str]:
        return list(self._members)

    def read_file(self, path: str) -> bytes:
        stored = self._stored(self._key(path))
        if path.endswith(".tpl"):
            return stored[struct.unpack_from(">I", stored, 0x18)[0]:]
        return stored

    def write_file(self, path: str, data: bytes) -> None:
        key = self._key(path)
        if path.endswith(".tpl"):
            stored = self._stored(key)
            data = stored[:struct.unpack_from(">I", stored, 0x18)[0]] + bytes(data)
        self._changes[key] = bytes(data)

    def has_pending_changes(self) -> bool:
        return bool(self._changed())

    def _changed(self) -> Dict[Tuple[int, int, int], bytes]:
        return {key: data for key, data in self._changes.items() if data != self._original(key)}

    def pack(self) -> bytes:
        changed = self._changed()
        if not changed:
            return self._data
        stages = {sector: self._rebuild(sector, {k[1:]: v for k, v in changed.items() if k[0] == sector})
                  for sector in {key[0] for key in changed}}
        return self._place(stages)

    def _rebuild(self, sector: int, files: Dict[Tuple[int, int], bytes]) -> bytes:
        """The stage at ``sector`` with ``files`` ((folder, file) -> bytes) replaced."""
        count, ents, folders = self._layout(sector)
        ents = list(ents)
        data0 = self._data0(sector)
        body = bytearray()
        for f, folder in enumerate(folders):
            raw = self._data[data0 + folder.offset:data0 + folder.offset + folder.csize]
            if any(key[0] == f for key in files):
                blob = self._folder_bytes(sector, f)
                out = bytearray()
                for k, (word, offset) in enumerate(folder.files):
                    end = folder.files[k + 1][1] if k + 1 < len(folder.files) else folder.end
                    piece = files.get((f, k), blob[offset:end])
                    if k + 1 < len(folder.files) and len(piece) % 0x20:
                        piece += bytes(0x20 - len(piece) % 0x20)
                    ents[folder.entry + 2 + k] = (word, len(out))
                    out += piece
                ents[folder.entry] = (folder.word, len(out))
                ents[folder.entry + 2 + len(folder.files)] = (_FOLDER_END, len(out))
                raw = zlib.compress(bytes(out), 9)
                ents[folder.entry + 1] = (0x7E000000 | len(raw), len(body))
            else:
                ents[folder.entry + 1] = (ents[folder.entry + 1][0], len(body))
            body += raw + bytes(_align(len(raw), SECTOR) - len(raw))
        header = bytearray(struct.pack(">I", count))
        for word, value in ents:
            header += struct.pack(">II", word, value)
        header += bytes(_align(len(header), SECTOR) - len(header))
        return bytes(header + body)

    def _place(self, stages: Dict[int, bytes]) -> bytes:
        """The file with the rebuilt stages: each stays at its sector when it fits, else the rest moves."""
        starts = sorted({sector for _n, sector in self._stages})
        out = bytearray(self._data[:starts[0] * SECTOR])
        moved: Dict[int, int] = {}
        for i, sector in enumerate(starts):
            end = starts[i + 1] * SECTOR if i + 1 < len(starts) else len(self._data)
            blob = stages.get(sector, self._data[sector * SECTOR:end])
            if len(out) < sector * SECTOR:
                out += bytes(sector * SECTOR - len(out))     # a stage that shrank keeps the next one in place
            moved[sector] = len(out) // SECTOR
            out += blob
            out += bytes(_align(len(out), SECTOR) - len(out))
        for index, (_name, sector) in enumerate(self._stages):
            struct.pack_into(">I", out, 0x18 + 12 * index, moved[sector])
        return bytes(out) + bytes(max(0, len(self._data) - len(out)))     # never shorter than it was
