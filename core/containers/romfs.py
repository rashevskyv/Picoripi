"""RomFS (IVFC level 3): the file tree of a Nintendo 3DS or Switch program, as ``ImageFile`` entries.

``RomFS(stream)`` reads a RomFS region; ``stream`` is that region from its first byte (a file view or a decrypting
view). Every table pointer is bounds-checked, every name goes through ``check_name``, and the walk refuses loops and
oversized trees. Entries are named ``romfs/<path>`` and address the region: ``offset`` is relative to ``stream``.
"""
from __future__ import annotations

import struct
from typing import Any, List, Tuple

from core.containers.image_files import ImageError, ImageFile, ImageReader, check_name

NO_ENTRY = 0xFFFFFFFF
MAX_FILES = 200_000          # caps the RomFS files and, separately, its directories (a corrupt table)


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _align(value: int, size: int) -> int:
    return (value + size - 1) // size * size


class RomFS(ImageReader):
    """The files of one RomFS region. Raises ImageError when the region is not a RomFS or its tables do not fit."""

    def __init__(self, stream: Any) -> None:
        super().__init__(stream)
        self._entries = self._list()

    def entries(self) -> List[ImageFile]:
        return list(self._entries)

    def _list(self) -> List[ImageFile]:
        ivfc = self.read_at(0, 0x60)
        if ivfc[:4] != b"IVFC":
            raise ImageError("the RomFS has no IVFC header")
        master = _u32(ivfc, 8)
        log2 = _u32(ivfc, 0x4C)
        if log2 > 24:
            raise ImageError("the RomFS block size is not plausible")
        level3 = _align(0x60 + master, 1 << log2)
        if level3 + 0x28 > self.size:
            raise ImageError("the RomFS level 3 header ends past the RomFS")
        header = self.read_at(level3, 0x28)
        dir_base = level3 + _u32(header, 0x0C)
        dir_len = _u32(header, 0x10)
        file_base = level3 + _u32(header, 0x1C)
        file_len = _u32(header, 0x20)
        data_base = level3 + _u32(header, 0x24)
        for table, length in ((dir_base, dir_len), (file_base, file_len)):
            if table + length > self.size:
                raise ImageError("a RomFS table ends past the RomFS")
        return self._walk(dir_base, dir_len, file_base, file_len, data_base)

    def _walk(self, dir_base: int, dir_len: int, file_base: int, file_len: int, data_base: int) -> List[ImageFile]:
        files: List[ImageFile] = []
        stack: List[Tuple[int, str]] = [(0, "")]
        seen_dirs: set = set()
        directories = 1   # the root; each child directory found below adds one
        while stack:
            pos, prefix = stack.pop()
            if pos in seen_dirs:
                raise ImageError("the RomFS directory tree loops")
            seen_dirs.add(pos)
            root = self._entry(dir_base, dir_len, pos, 0x18)
            child_dir, child_file = _u32(root, 0x08), _u32(root, 0x0C)
            seen_files: set = set()
            file_pos = child_file
            while file_pos != NO_ENTRY:
                if file_pos in seen_files:
                    raise ImageError("the RomFS file list loops")
                seen_files.add(file_pos)
                raw, name = self._name_entry(file_base, file_len, file_pos, 0x20, 0x1C)
                offset, length = struct.unpack_from("<QQ", raw, 0x08)
                absolute = data_base + offset
                if absolute + length > self.size:
                    raise ImageError(f"RomFS file {name} ends past the RomFS")
                files.append(ImageFile(f"romfs/{prefix}{name}", absolute, length, None, self.stream))
                if len(files) > MAX_FILES:
                    raise ImageError("the RomFS holds too many files")
                file_pos = _u32(raw, 0x04)
            seen_children: set = set()
            dir_pos = child_dir
            while dir_pos != NO_ENTRY:
                if dir_pos in seen_children:
                    raise ImageError("the RomFS directory list loops")
                seen_children.add(dir_pos)
                raw, name = self._name_entry(dir_base, dir_len, dir_pos, 0x18, 0x14)
                stack.append((dir_pos, f"{prefix}{name}/"))
                directories += 1
                if directories > MAX_FILES:
                    raise ImageError("the RomFS holds too many directories")
                dir_pos = _u32(raw, 0x04)
        return files

    def _entry(self, base: int, length: int, pos: int, header: int) -> bytes:
        if pos % 4 or pos + header > length:
            raise ImageError("a RomFS table entry is out of range")
        return self.read_at(base + pos, header)

    def _name_entry(self, base: int, length: int, pos: int, header: int, name_at: int) -> Tuple[bytes, str]:
        raw = self._entry(base, length, pos, header)
        name_len = _u32(raw, name_at)
        if name_len == 0 or name_len % 2 or name_len > 0x200 or pos + header + name_len > length:
            raise ImageError("a RomFS name is out of range")
        try:
            name = self.read_at(base + pos + header, name_len).decode("utf-16-le")
        except UnicodeDecodeError as exc:
            raise ImageError("unsafe RomFS name") from exc
        return raw, check_name(name)
