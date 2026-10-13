"""Nintendo DS cartridge images (.nds, the raw ROM): the header, the NitroFS file names and file spans.

``entries`` lists ``main.arm9`` (the ARM9 program, the name the Zelda and Four Swords scripts use) and every NitroFS
file under its file-name-table path. The data of one file is read by its span only.
"""
from __future__ import annotations

import struct
from typing import BinaryIO, Dict, List

from core.containers.image_files import ImageError, ImageFile, ImageReader, check_name

NINTENDO_LOGO_CRC = 0xCF56
HEADER_SIZE = 0x200
ARM9_NAME = "main.arm9"
ROOT_DIR = 0xF000


def is_nds_header(head: bytes) -> bool:
    """The Nintendo logo CRC at 0x15C and a printable game code at 0x0C: the header of every licensed cartridge."""
    if len(head) < HEADER_SIZE or struct.unpack_from("<H", head, 0x15C)[0] != NINTENDO_LOGO_CRC:
        return False
    return all(0x20 < byte < 0x7F for byte in head[0x0C:0x10])


def walk_fnt(table: bytes) -> Dict[str, int]:
    """``{path: file id}`` of a file name table (the FNT, starting at its first byte; sub-tables are relative to it)."""
    found: Dict[str, int] = {}
    listed = set()  # a directory has one parent: a second visit is a loop, and would make the walk exponential

    def walk(dir_id: int, prefix: str, depth: int) -> None:
        if depth > 64:
            raise ImageError("the file name table nests too deep")
        key = dir_id & 0xFFF
        if key in listed:
            raise ImageError("the file name table lists a directory twice")
        listed.add(key)
        at_entry = key * 8
        if at_entry + 8 > len(table):
            raise ImageError("the file name table has no such directory")
        sub, first = struct.unpack_from("<IH", table, at_entry)
        at, file_id = sub, first
        while at < len(table) and table[at]:
            length = table[at] & 0x7F
            is_dir = table[at] & 0x80
            if at + 1 + length + (2 if is_dir else 0) > len(table):
                raise ImageError("the file name table is cut short")
            name = check_name(bytes(table[at + 1:at + 1 + length]).decode("ascii", "replace"))
            if is_dir:
                walk(struct.unpack_from("<H", table, at + 1 + length)[0], f"{prefix}{name}/", depth + 1)
                at += 3 + length
            else:
                found[prefix + name] = file_id
                file_id += 1
                at += 1 + length

    walk(ROOT_DIR, "", 0)
    return found


class NdsImage(ImageReader):
    def __init__(self, stream: BinaryIO) -> None:
        super().__init__(stream)
        head = self.read_at(0, min(self.size, HEADER_SIZE))
        if not is_nds_header(head):
            raise ImageError("not a Nintendo DS cartridge image")
        self.game_code = head[0x0C:0x10].decode("ascii", "replace")
        arm9_at, _entry, _load, arm9_size = struct.unpack_from("<4I", head, 0x20)
        self._arm9 = (arm9_at, arm9_size)
        fnt_at, fnt_size, fat_at, fat_size = struct.unpack_from("<4I", head, 0x40)
        self._fnt = self.read_table(fnt_at, fnt_size)
        self._fat = self.read_table(fat_at, fat_size)

    def entries(self) -> List[ImageFile]:
        """``main.arm9``, then every NitroFS file in file-name-table order (sorted by path)."""
        found = [ImageFile(ARM9_NAME, self._arm9[0], self._arm9[1])]
        spans = len(self._fat) // 8
        for path, file_id in sorted(walk_fnt(self._fnt).items()):
            if file_id >= spans:
                raise ImageError(f"the file allocation table has no entry for {path}")
            start, end = struct.unpack_from("<II", self._fat, file_id * 8)
            if end < start or end > self.size:
                raise ImageError(f"the file span of {path} lies outside the image")
            found.append(ImageFile(path, start, end - start))
        return found
