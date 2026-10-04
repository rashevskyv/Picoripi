"""Raise TotK's resource size table entries for translated text archives. Offline tool.

    python -m plugins.zelda_totk.restbl <game romfs> <mod romfs>

TotK reserves memory for a file from ``System/Resource/ResourceSizeTable.Product.<ver>.rsizetable.zs``.
A translated ``Mals/*.sarc.zs`` that decompresses to more bytes than the game's own may not fit, so for
every archive in the mod this scales its entry by how much the archive grew (never lowers it) and
writes the table into the mod. Entries are keyed by the path without ``.zs``
(``Mals/USen.Product.121.sarc``): a CRC32 table, plus a name table for colliding paths.
"""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path
from typing import Dict, List, Tuple

from utils.atomic_io import atomic_write_bytes

from . import sarc

_HEADER = 0x16


class Restbl:
    """A parsed RESTBL; ``set_size`` changes a value in place, ``build`` writes it back."""

    def __init__(self, raw: bytes):
        if raw[:6] != b"RESTBL":
            raise ValueError("Not a resource size table")
        self.raw = bytearray(raw)
        _version, self.name_size, crc_count, name_count = struct.unpack_from("<IIII", raw, 6)
        self._crc: Dict[int, int] = {}        # hash -> offset of its value
        for index in range(crc_count):
            position = _HEADER + index * 8
            self._crc[struct.unpack_from("<I", raw, position)[0]] = position + 4
        self._names: Dict[str, int] = {}
        start = _HEADER + crc_count * 8
        for index in range(name_count):
            position = start + index * (self.name_size + 4)
            name = raw[position:position + self.name_size].split(b"\x00")[0].decode("utf-8")
            self._names[name] = position + self.name_size

    def _offset(self, path: str):
        return self._names.get(path, self._crc.get(zlib.crc32(path.encode("utf-8"))))

    def size(self, path: str):
        offset = self._offset(path)
        return None if offset is None else struct.unpack_from("<I", self.raw, offset)[0]

    def set_size(self, path: str, value: int) -> None:
        struct.pack_into("<I", self.raw, self._offset(path), value)

    def build(self) -> bytes:
        return bytes(self.raw)


def scaled_size(entry: int, original_size: int, new_size: int) -> int:
    """The entry grown in proportion to the file, rounded up to 0x100; never smaller than before."""
    if new_size <= original_size or original_size <= 0:
        return entry
    grown = -(-entry * new_size // original_size)
    return max(entry, (grown + 0xFF) & ~0xFF)


def update(game_romfs: Path, mod_romfs: Path) -> List[Tuple[str, int, int]]:
    """Update the mod's size table for its Mals archives; ``[(path, old, new)]`` of the changed entries."""
    tables = sorted((game_romfs / "System" / "Resource").glob("ResourceSizeTable.Product.*.rsizetable.zs"))
    if not tables:
        raise FileNotFoundError(f"No ResourceSizeTable.Product.*.rsizetable.zs under {game_romfs}/System/Resource")
    source_table = tables[-1]
    sarc.dictionary_dirs = lambda: [game_romfs]
    table_data, dict_id = sarc.decompress(source_table.read_bytes())
    table = Restbl(table_data)
    changes = []
    for archive in sorted((mod_romfs / "Mals").glob("*.sarc.zs")):
        game_archive = game_romfs / "Mals" / archive.name
        key = f"Mals/{archive.name[:-3]}"
        entry = table.size(key)
        if entry is None or not game_archive.is_file():
            continue
        original_size = len(sarc.decompress(game_archive.read_bytes())[0])
        new_size = len(sarc.decompress(archive.read_bytes())[0])
        value = scaled_size(entry, original_size, new_size)
        if value != entry:
            table.set_size(key, value)
            changes.append((key, entry, value))
    if changes:
        target = mod_romfs / "System" / "Resource" / source_table.name
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(target, sarc.compress(table.build(), dict_id))
    return changes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("game_romfs", type=Path)
    parser.add_argument("mod_romfs", type=Path)
    args = parser.parse_args(argv)
    changes = update(args.game_romfs, args.mod_romfs)
    for key, old, new in changes:
        print(f"{key}: {old} -> {new}")
    if not changes:
        print("No entry needed a change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
