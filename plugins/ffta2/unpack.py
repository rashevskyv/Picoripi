"""The files the unpack step takes from Final Fantasy Tactics A2 (DS, Europe): the same set as zt/ffds.py ``unpack``.

Every game file is a member of ``master/pc.bin``, found through ``master/pc.idx`` by a hash of its name (read only
here; the layout follows FFTA2 Editor's archive). The five English message packs are written as ``.a2msg`` files
(``A2MS``, the kind, the index length, the index, the data), the menu pack as ``.a2pak``; the font, the width table,
and the title logo and two other ``.efx`` files are copied as they are.
"""
import os
import struct
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from core.containers.image_files import ImageError
from core.project_library import images

# workspace file -> (index member, data member, kind: T string tables / S single strings / P menu pictures)
A2_TEXT = {
    "system/rom/JD_message_0.a2msg": ("system/rom/JD_message_rom_0.idx", "system/rom/JD_message_0.pak", "T"),
    "system/rom/JH_questtext_0.a2msg": ("system/rom/JH_questtext_rom_0.idx", "system/rom/JH_questtext_0.pak", "S"),
    "system/rom/JH_uwasatext_0.a2msg": ("system/rom/JH_uwasatext_rom_0.idx", "system/rom/JH_uwasatext_0.pak", "S"),
    "system/rom/JH_freepapermes_0.a2msg": ("system/rom/JH_freepapermes_rom_0.idx",
                                           "system/rom/JH_freepapermes_0.pak", "S"),
    "event/rom/ev_msg0.a2msg": ("event/rom/ev_msg0_rom.idx", "event/rom/ev_msg0.pak", "T"),
    "menu/nc_rom/us/nc.a2pak": ("menu/nc_rom/us/nc_rom.idx", "menu/nc_rom/us/nc.pak", "P"),
}
A2_FILES = ("menu/font/UseMoji_image.bin", "menu/font/FontWidthTable.bin", "effect/common/c_all_title_eu.efx",
            "effect/common/us/c_all_auction.efx", "effect/common/us/c_all_worldmap.efx")
A2_MAGIC = b"A2MS"
PC_IDX, PC_BIN = "master/pc.idx", "master/pc.bin"


def name_hash(name: str) -> int:
    """The pc.idx slot of a file name."""
    raw = name.encode("ascii")
    value = raw[0]
    for byte in raw[1:]:
        value = (value * 0x25 + byte) & 0xFFFFFFFF
    return value & 0x3FF


class PcArchive:
    """Read-only ``pc.idx`` + ``pc.bin``. A slot holds one file, or a list of files that share its hash."""

    def __init__(self, idx: bytes, data: bytes):
        self.idx, self.data = idx, data

    def _entries(self, slot: int) -> List[Tuple[int, int, Optional[str], Optional[int]]]:
        """``[(offset, size, first character of the name, its position in the name)]`` of a slot."""
        at = 8 + 9 * slot
        a, b = struct.unpack_from("<II", self.idx, at)
        if a == 0 and b == 0:
            return []
        size = ((a >> 26) + (b & 0xFFFF) * 64) * 4
        offset = (a & 0x3FFFFFF) * 2
        if not a & 1:
            return [(offset, size, None, None)]
        out, pos = [], offset // 4 + 1
        for k in range(self.idx[offset // 4]):
            start = struct.unpack_from("<I", self.idx, pos)[0] * 4
            if k == 0:
                length = size
                pos += 4
            else:
                length = struct.unpack_from("<I", self.idx, pos + 4)[0] * 4
                pos += 12
            out.append((start, length, chr(self.idx[pos]), self.idx[pos + 1]))
            pos += 3
        return out

    def read(self, name: str) -> bytes:
        entries = self._entries(name_hash(name))
        if len(entries) == 1 and entries[0][2] is None:
            offset, size = entries[0][:2]
        else:
            found = [e for e in entries if e[3] < len(name) and name[e[3]] == e[2]]
            if not found:
                raise ImageError(f"{name} is not in master/pc.bin")
            offset, size = found[0][:2]
        return bytes(self.data[offset:offset + size])


def a2_join(kind: str, index: bytes, data: bytes) -> bytes:
    return A2_MAGIC + kind.encode("ascii") + struct.pack("<I", len(index)) + index + data


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    with images.open_image(base) as image:
        members = {entry.path: entry for entry in image.entries()}
        for name in (PC_IDX, PC_BIN):
            if name not in members:
                raise ImageError(f"the ROM has no file {name}")
        archive = PcArchive(image.read(members[PC_IDX]), image.read(members[PC_BIN]))
    files = [(rel, a2_join(kind, archive.read(index), archive.read(data)))
             for rel, (index, data, kind) in A2_TEXT.items()]
    files += [(rel, archive.read(rel)) for rel in A2_FILES]
    for number, (rel, data) in enumerate(files):
        if is_cancelled():
            return None
        progress(100 * number // len(files), rel)
        _write(Path(target_dir, *rel.split("/")), data)
    progress(100, "")
    return str(target_dir)
