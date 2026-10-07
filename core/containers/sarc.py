"""SARC archives, plain or zstd-compressed like TotK's ``Mals/<Lang>.Product.<ver>.sarc.zs``.

TotK compresses most files with zstd against dictionaries kept in ``romfs/Pack/ZsDic.pack.zs`` (itself
a zstd SARC without a dictionary). A frame names its dictionary by id, so the dictionaries are found by
looking for ``ZsDic.pack.zs`` in the places ``dictionary_dirs`` lists (the TotK plugin sets it: the project folders and
``~/.picoripi/plugins/zelda_totk``) and loaded once.

``SarcContainer`` plugs these archives into the project's archive support: each ``.msbt`` inside
becomes a project block, and saving repacks the archive and compresses it with the same dictionary.
zstd comes from the standard library (``compression.zstd``, Python 3.14+).
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from core.containers.base_container import BaseArchiveContainer

try:
    from compression import zstd
except ImportError:  # Python < 3.14: plain SARC still works, .zs files report why they cannot open.
    zstd = None

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
_DICT_MAGIC = b"\x37\xa4\x30\xec"
DICTIONARY_PACK = "ZsDic.pack.zs"
COMPRESSION_LEVEL = 19

# Folders to look for ZsDic.pack.zs in; the plugin sets it (rules.py).
dictionary_dirs: Callable[[], Iterable[Path]] = lambda: ()
_dictionaries: Dict[int, object] = {}
_searched: set = set()


def _need_zstd() -> None:
    if zstd is None:
        raise ValueError("zstd-compressed files need Python 3.14 or newer (compression.zstd)")


def add_dictionary_pack(raw: bytes) -> List[int]:
    """Load every ``*.zsdic`` in a ZsDic.pack.zs; returns their ids."""
    _need_zstd()
    pack = Sarc(zstd.decompress(raw))
    ids = []
    for name, data in pack.files.items():
        if name.endswith(".zsdic") and data[:4] == _DICT_MAGIC:
            dict_id = struct.unpack_from("<I", data, 4)[0]
            _dictionaries[dict_id] = zstd.ZstdDict(data)
            ids.append(dict_id)
    return ids


def _dictionary(dict_id: int):
    if dict_id == 0:
        return None
    if dict_id not in _dictionaries:
        for folder in dictionary_dirs():
            folder = Path(folder)
            for base in (folder, *list(folder.parents)[:3]):
                for candidate in (base / DICTIONARY_PACK, base / "Pack" / DICTIONARY_PACK):
                    if candidate in _searched or not candidate.is_file():
                        continue
                    _searched.add(candidate)
                    add_dictionary_pack(candidate.read_bytes())
            if dict_id in _dictionaries:
                break
    if dict_id not in _dictionaries:
        raise ValueError(
            f"zstd dictionary {dict_id:#x} not found: put the game's romfs/Pack/{DICTIONARY_PACK} next to "
            f"the project's romfs (Pack/{DICTIONARY_PACK}) or into ~/.picoripi/plugins/zelda_totk/"
        )
    return _dictionaries[dict_id]


def decompress(raw: bytes) -> Tuple[bytes, int]:
    """``(data, dictionary id)`` of a zstd frame; id 0 means no dictionary."""
    _need_zstd()
    dict_id = zstd.get_frame_info(raw).dictionary_id
    return zstd.decompress(raw, zstd_dict=_dictionary(dict_id)), dict_id


def compress(data: bytes, dict_id: int) -> bytes:
    """``data`` as one zstd frame against the same dictionary the original used."""
    _need_zstd()
    return zstd.compress(data, level=COMPRESSION_LEVEL, zstd_dict=_dictionary(dict_id))


class Sarc:
    """A parsed SARC. Files keep their names, order and data alignment; only their contents change."""

    def __init__(self, raw: bytes):
        raw = bytes(raw)
        if raw[:4] != b"SARC":
            raise ValueError("Not a SARC archive")
        self.endian = "<" if raw[6:8] == b"\xff\xfe" else ">"
        e = self.endian
        self.data_offset = struct.unpack_from(e + "I", raw, 0x0C)[0]
        header_size = struct.unpack_from(e + "H", raw, 0x04)[0]
        sfat = header_size
        if raw[sfat:sfat + 4] != b"SFAT":
            raise ValueError("SARC without an SFAT section")
        node_count = struct.unpack_from(e + "H", raw, sfat + 6)[0]
        names_base = sfat + 12 + node_count * 16 + 8
        self._head = bytearray(raw[:self.data_offset])
        self._nodes: List[Tuple[str, int, int]] = []   # name, start, end (relative to data_offset)
        for index in range(node_count):
            _hash, attributes, start, end = struct.unpack_from(e + "IIII", raw, sfat + 12 + index * 16)
            if attributes >> 24:
                name_at = names_base + (attributes & 0xFFFFFF) * 4
                name = raw[name_at:raw.index(b"\x00", name_at)].decode("utf-8")
            else:
                name = f"{_hash:08x}"
            self._nodes.append((name, start, end))
        self.files: Dict[str, bytes] = {
            name: raw[self.data_offset + start:self.data_offset + end] for name, start, end in self._nodes
        }
        # Every file start is a multiple of this (capped); new layouts keep to it. A file whose start is
        # aligned more (a Wii U layout's GX2 images at 0x800-0x2000; a Switch BNTX, used in place, at 0x1000)
        # keeps its own alignment.
        starts = [start for _name, start, _end in self._nodes if start]
        self.alignment = min((start & -start for start in starts), default=8)
        self.alignment = min(self.alignment, 0x2000)
        self._aligns = [max(self.alignment, min(start & -start, 0x2000)) if start else self.alignment
                        for _name, start, _end in self._nodes]

    def build(self) -> bytes:
        """The archive with the current ``files``: same names and order, offsets moved as sizes changed."""
        e = self.endian
        head = bytearray(self._head)
        node_table = struct.unpack_from(e + "H", head, 0x04)[0] + 12
        order = sorted(range(len(self._nodes)), key=lambda index: self._nodes[index][1])
        data = bytearray()
        for index in order:
            name = self._nodes[index][0]
            data += b"\x00" * (-len(data) % self._aligns[index])
            start = len(data)
            data += self.files[name]
            struct.pack_into(e + "II", head, node_table + index * 16 + 8, start, len(data))
        struct.pack_into(e + "I", head, 0x08, len(head) + len(data))
        return bytes(head + data)


class SarcContainer(BaseArchiveContainer):
    """A SARC (zstd-compressed or not) as a project archive; writes go back in the same compression."""

    MAGIC = b"SARC"

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        if data[:4] == b"SARC":
            return True
        if data[:4] != ZSTD_MAGIC or zstd is None:
            return False
        try:
            dict_id = zstd.get_frame_info(data).dictionary_id
        except (ValueError, zstd.ZstdError):
            return False
        try:
            dictionary = _dictionary(dict_id)
        except ValueError:
            return True  # opening it reports which dictionary file is missing, instead of skipping silently
        try:
            head = zstd.ZstdDecompressor(zstd_dict=dictionary).decompress(data, max_length=4)
        except zstd.ZstdError:
            return False
        return head == b"SARC"

    def __init__(self, data: bytes) -> None:
        self._original = bytes(data)
        self._dict_id: Optional[int] = None
        if data[:4] == ZSTD_MAGIC:
            data, self._dict_id = decompress(data)
        self._sarc = Sarc(data)
        self._overlay: Dict[str, bytes] = {}

    def list_files(self) -> List[str]:
        return list(self._sarc.files)

    def read_file(self, path: str) -> bytes:
        if path in self._overlay:
            return self._overlay[path]
        return self._sarc.files[path]

    def write_file(self, path: str, data: bytes) -> None:
        if path not in self._sarc.files:
            raise KeyError(path)
        self._overlay[path] = bytes(data)

    def pack(self) -> bytes:
        changed = {path: data for path, data in self._overlay.items() if data != self._sarc.files[path]}
        if not changed:
            return self._original
        self._sarc.files.update(changed)
        self._overlay.clear()
        raw = self._sarc.build()
        self._original = raw if self._dict_id is None else compress(raw, self._dict_id)
        return self._original
