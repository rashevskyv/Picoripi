"""Luigi's Mansion: Dark Moon unpack: the text tables and picture bundles of ``art/fe`` as a source folder.

The game keeps them in ``.dict`` + ``.data`` pairs. The workspace's ``1_unpack.bat`` writes the raw pair into ``romfs/``
and the members into ``source/romfs/`` as folders: ``english.data/strings.nloc`` (member 3 of ``english.dict``) and
``febundle*_res.data/bundle.nlgb`` (member 2, the table, and member 3, the pixels, joined as ``NLGB``). The Switch HD
pairs differ: their entry table sits before ``.data`` / ``.debug`` at the end of the dict, members are not zlib, and the
bundle is one member, written as ``bundle.nlgh`` (``NLGH`` and member 2). This module writes the same tree under
``source/romfs/``; the raw pairs stay in ``romfs/``. Only unpacking: it does not rebuild a pair.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Tuple

from core.i18n import tr
from core.texture_formats import nlg_tex

SOURCE_SUBFOLDER = "source/romfs"
DICT_MAGIC = 0xA9F32458
HD_NAMES = b".data\x00.debug\x00"   # the names that end a Switch HD dict, after its entry table
TABLE_MEMBER, DATA_MEMBER = 2, 3
# (pattern under romfs, kind). "nloc": member 3 is strings.nloc. "bundle": members 2 and 3 are one bundle.nlgb.
PAIRS = (("art/fe/english.dict", "nloc"), ("art/fe/ukenglish.dict", "nloc"), ("art/fe/russian.dict", "nloc"),
         ("art/fe/febundle*_res.dict", "bundle"))
# raw file -> its name in the source folder (the staff roll is read as .credits)
RENAMES = {"art/fe/credits.txt": "art/fe/credits.credits"}
PAIR_FOLDER = "romfs/art/fe/"   # the Switch HD RomFS: its pairs and staff roll are the only files the plugin reads


def switch_pairs_only(path: str) -> bool:
    """True for the Switch HD RomFS files the plugin reads (``extract`` ``select``): the pairs and the staff roll.
    The rest of the RomFS (about six gigabytes) is not written."""
    return path.lower().startswith(PAIR_FOLDER)


class _Pair:
    """One ``.dict`` table and its ``.data`` file. Entries are 16 bytes: offset, size, stored size, flags. ``hd``: the
    Switch HD layout (the table is the last 16 x count bytes before the ``.data`` / ``.debug`` names, nothing is zlib)."""

    def __init__(self, name: str, dict_bytes: bytes, data: bytes, hd: bool = False):
        if len(dict_bytes) < 0x2C or struct.unpack_from("<I", dict_bytes, 0)[0] != DICT_MAGIC:
            raise ValueError(tr("{0} is not a Luigi's Mansion pair table.", name))
        self.name, self.dict, self.data = name, dict_bytes, data
        self.count = struct.unpack_from("<I", dict_bytes, 8)[0]
        self.packed = bool(dict_bytes[6]) and not hd
        self.table = len(dict_bytes) - len(HD_NAMES) - 16 * self.count if hd else 0x2C + self.count
        if self.count <= DATA_MEMBER or self.table + 16 * self.count > len(dict_bytes):
            raise ValueError(tr("{0} is not a Luigi's Mansion pair table.", name))

    def member(self, index: int) -> bytes:
        offset, size, stored, _flags = struct.unpack_from("<IIII", self.dict, self.table + 16 * index)
        if size == 0:
            return b""
        packed = self.packed and stored
        length = stored if packed else size
        raw = self.data[offset:offset + length]
        if len(raw) != length:
            raise ValueError(tr("The member {0} of {1} is outside its data file.", index, self.name))
        if not packed:
            return raw
        try:
            out = zlib.decompress(raw)
        except zlib.error:
            raise ValueError(tr("The member {0} of {1} is not a valid stream.", index, self.name)) from None
        if len(out) != size:
            raise ValueError(tr("The member {0} of {1} has the wrong size.", index, self.name))
        return out


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def expand_pairs(unpacked: Path, hd: bool = False) -> Tuple[int, ...]:
    """Write the source tree under ``unpacked/source/romfs`` from the raw files in ``unpacked/romfs``. ``hd``: the pairs
    are the Switch HD ones (their bundle is ``bundle.nlgh``).

    Returns the number of files written, one per pair or renamed file.
    """
    romfs = unpacked / "romfs"
    target = unpacked.joinpath(*SOURCE_SUBFOLDER.split("/"))
    written = []
    for raw, new in RENAMES.items():
        if (romfs / raw).is_file():
            _write(target / new, (romfs / raw).read_bytes())
            written.append(new)
    for pattern, kind in PAIRS:
        for dict_path in sorted(romfs.glob(pattern)):
            data_path = dict_path.with_suffix(".data")
            if not data_path.is_file():
                continue
            pair = _Pair(dict_path.name, dict_path.read_bytes(), data_path.read_bytes(), hd)
            rel = dict_path.with_suffix("").relative_to(romfs).as_posix().lower()   # the workspace uses lower case
            if kind == "nloc":
                _write(target / f"{rel}.data" / "strings.nloc", pair.member(DATA_MEMBER))
            elif hd:
                _write(target / f"{rel}.data" / "bundle.nlgh", b"NLGH" + pair.member(TABLE_MEMBER))
            else:
                bundle = nlg_tex.join(pair.member(TABLE_MEMBER), pair.member(DATA_MEMBER))
                _write(target / f"{rel}.data" / "bundle.nlgb", bundle)
            written.append(rel)
    return tuple(written)
