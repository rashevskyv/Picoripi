"""Nintendo 3DS images: a .cia, a card image (.3ds, .cci) or one bare program (NCCH, .cxi or .cfa).

``locate`` finds the main program and says whether it is encrypted. ``N3dsImage`` lists the files of a decrypted
program: ``exheader.bin``, ``exefs/<name>`` and ``romfs/<path>``. A decrypted program (NCCH flag NoCrypto, and a CIA
whose content is not encrypted) needs no key. Names follow the workspace (3dstool): ``exefs/<name>.bin``. An encrypted program raises ``encrypted_error`` from
``core.containers.console_crypto``. Every table pointer is bounds-checked and every name goes through ``check_name``,
so no entry can point outside the image or name a path outside the output folder.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Optional, Tuple

from core.containers.console_crypto import encrypted_error
from core.containers.image_files import ImageError, ImageFile, ImageReader, check_name
from core.i18n import tr

UNIT = 0x200                 # a media unit: NCSD and NCCH offsets and sizes count in these
NCCH_MAGIC = b"NCCH"
NCSD_MAGIC = b"NCSD"
CIA_HEADER_SIZE = 0x2020
EXHEADER_SIZE = 0x800
NO_ENTRY = 0xFFFFFFFF
MAX_FILES = 200_000          # guards the file walks against a corrupt table
MAX_TMD = 0x10000
SIG_SIZES = {0x10000: 0x240, 0x10001: 0x140, 0x10002: 0x80, 0x10003: 0x240, 0x10004: 0x140, 0x10005: 0x80}
LABEL = "Nintendo 3DS"


Program = Dict[str, Any]   # keys: base (the NCCH offset in the image), encrypted, title_id (hex), product ("" if unknown)


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _align(value: int, size: int) -> int:
    return (value + size - 1) // size * size


def locate(reader: ImageReader, head: bytes) -> Optional[Program]:
    """The main program of a 3DS image, or None when ``head`` is not a 3DS image. Reads headers only.

    Raises ImageError for a 3DS header whose tables do not fit the file.
    """
    if head[0x100:0x104] == NCSD_MAGIC:
        base = _u32(head, 0x120) * UNIT
        if base == 0:
            raise ImageError("the card image has no main partition")
        return _ncch_program(reader, base)
    if head[0x100:0x104] == NCCH_MAGIC:
        return _ncch_program(reader, 0)
    if len(head) >= 0x20 and _u32(head, 0) == CIA_HEADER_SIZE:
        return _cia_program(reader, head)
    return None


def _ncch_program(reader: ImageReader, base: int) -> Program:
    head = reader.read_at(base, 0x200)
    if head[0x100:0x104] != NCCH_MAGIC:
        raise ImageError("the main partition is not a 3DS program")
    nocrypto = bool(head[0x188 + 7] & 0x04)
    product = head[0x150:0x160].split(b"\0", 1)[0].decode("ascii", "replace")
    return dict(base=base, encrypted=not nocrypto, product=product, title_id=head[0x118:0x120][::-1].hex())


def _cia_program(reader: ImageReader, head: bytes) -> Program:
    """A CIA: its ticket and title metadata sit before the contents; the main content is index 0."""
    hsize, _typ, _ver, cert, tik, tmd, _meta, _csize = struct.unpack_from("<IHHIIIIQ", head, 0)
    tik_off = _align(hsize, 0x40) + _align(cert, 0x40)
    tmd_off = tik_off + _align(tik, 0x40)
    con_off = tmd_off + _align(tmd, 0x40)
    if tik > MAX_TMD or tmd > MAX_TMD or tmd < 0x10:
        raise ImageError("the CIA metadata has a bad size")
    ticket = reader.read_at(tik_off, tik)
    meta = reader.read_at(tmd_off, tmd)
    if struct.unpack_from(">I", ticket, 0)[0] not in SIG_SIZES:
        raise ImageError("the CIA ticket has an unknown signature type")
    tmd_sig = struct.unpack_from(">I", meta, 0)[0]
    if tmd_sig not in SIG_SIZES:
        raise ImageError("the CIA title metadata has an unknown signature type")
    body = meta[SIG_SIZES[tmd_sig]:]
    if len(body) < 0xC4:
        raise ImageError("the CIA title metadata is too short")
    title_id = body[0x4C:0x54].hex()
    count = struct.unpack_from(">H", body, 0x9E)[0]
    mask = head[0x20:0x40]
    offset = con_off
    for index in range(count):
        start = 0xC4 + 0x900 + index * 0x30
        if start + 0x10 > len(body):
            raise ImageError("the CIA content table does not fit")
        _cid, content_index, ctype, size = struct.unpack_from(">IHHQ", body, start)
        present = bool(mask[content_index // 8] & (0x80 >> (content_index % 8))) if content_index < 0x100 else False
        if content_index == 0:
            if not present:
                raise ImageError("the CIA has no main content")
            if offset + size > reader.size:
                raise ImageError("the CIA main content ends past the file")
            if ctype & 1:
                return dict(base=offset, encrypted=True, product="", title_id=title_id)
            return _ncch_program(reader, offset)
        if present:
            offset = _align(offset + size, 0x40)
    raise ImageError("the CIA has no main content")


class N3dsImage(ImageReader):
    """A decrypted 3DS program: its exheader, ExeFS and RomFS files. Raises ImageError for encrypted content."""

    def __init__(self, stream: Any) -> None:
        super().__init__(stream)
        head = self.read_at(0, 0x200)
        program = locate(self, head)
        if program is None:
            raise ImageError("not a Nintendo 3DS image")
        if program["encrypted"]:
            raise encrypted_error("3ds", tr(LABEL))
        self.program = program
        self.product = program["product"]
        self._entries = self._list(program["base"])

    def entries(self) -> List[ImageFile]:
        return list(self._entries)

    def _list(self, base: int) -> List[ImageFile]:
        head = self.read_at(base, 0x200)
        entries: List[ImageFile] = []
        if _u32(head, 0x180):
            entries.append(ImageFile("exheader.bin", base + 0x200, self._fit(base + 0x200, EXHEADER_SIZE)))
        exefs_off, exefs_size = _u32(head, 0x1A0) * UNIT, _u32(head, 0x1A4) * UNIT
        romfs_off, romfs_size = _u32(head, 0x1B0) * UNIT, _u32(head, 0x1B4) * UNIT
        if exefs_size:
            entries += self._exefs(self._region(base + exefs_off, exefs_size))
        if romfs_size:
            entries += self._romfs(self._region(base + romfs_off, romfs_size))
        if not entries:
            raise ImageError("the program has no exheader, ExeFS or RomFS")
        return entries

    def _region(self, start: int, size: int) -> Tuple[int, int]:
        if start < 0 or size < 0 or start + size > self.size:
            raise ImageError("a 3DS section ends past the image")
        return start, size

    def _fit(self, start: int, size: int) -> int:
        self._region(start, size)
        return size

    # -- ExeFS -------------------------------------------------------------

    def _exefs(self, region: Tuple[int, int]) -> List[ImageFile]:
        start, size = region
        if size < 0x200:
            raise ImageError("the ExeFS is shorter than its header")
        head = self.read_at(start, 0x200)
        files: List[ImageFile] = []
        for index in range(10):
            raw = head[index * 16:index * 16 + 8]
            if raw[0] == 0:
                continue
            offset, length = struct.unpack_from("<II", head, index * 16 + 8)
            try:
                name = raw.split(b"\0", 1)[0].decode("ascii")
            except UnicodeDecodeError as exc:
                raise ImageError("unsafe ExeFS file name") from exc
            check_name(name)
            if 0x200 + offset + length > size:
                raise ImageError(f"ExeFS file {name} ends past its section")
            # The names of the workspace (3dstool): ".code" is "exefs/code.bin".
            files.append(ImageFile(f"exefs/{name.lstrip('.')}.bin", start + 0x200 + offset, length))
        return files

    # -- RomFS (IVFC level 3) ------------------------------------------------

    def _romfs(self, region: Tuple[int, int]) -> List[ImageFile]:
        start, size = region
        ivfc = self.read_at(start, 0x60)
        if ivfc[:4] != b"IVFC":
            raise ImageError("the RomFS has no IVFC header")
        master = _u32(ivfc, 8)
        log2 = _u32(ivfc, 0x4C)
        if log2 > 24:
            raise ImageError("the RomFS block size is not plausible")
        level3 = start + _align(0x60 + master, 1 << log2)
        if level3 + 0x28 > start + size:
            raise ImageError("the RomFS level 3 header ends past the RomFS")
        header = self.read_at(level3, 0x28)
        dir_base = level3 + _u32(header, 0x0C)
        dir_len = _u32(header, 0x10)
        file_base = level3 + _u32(header, 0x1C)
        file_len = _u32(header, 0x20)
        data_base = level3 + _u32(header, 0x24)
        for table, length in ((dir_base, dir_len), (file_base, file_len)):
            if table + length > start + size:
                raise ImageError("a RomFS table ends past the RomFS")
        return self._walk_romfs(
            dir_base, dir_len, file_base, file_len, data_base, start + size)

    def _walk_romfs(self, dir_base: int, dir_len: int, file_base: int, file_len: int,
                    data_base: int, romfs_end: int) -> List[ImageFile]:
        files: List[ImageFile] = []
        stack: List[Tuple[int, str]] = [(0, "")]
        seen_dirs: set = set()
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
                if absolute + length > romfs_end:
                    raise ImageError(f"RomFS file {name} ends past the RomFS")
                files.append(ImageFile(f"romfs/{prefix}{name}", absolute, length))
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


def identify_fields(program: Program) -> Dict[str, Any]:
    """The fields ``core.project_library.images.identify`` reports for a 3DS program."""
    product = str(program.get("product") or "")
    game_id = product.rsplit("-", 1)[-1] if product else str(program["title_id"]).upper()
    return {"kind": "3ds", "game_id": game_id, "title_id": str(program["title_id"]),
            "encrypted": bool(program["encrypted"])}
