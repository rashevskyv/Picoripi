"""Game Freak Trinity archives (Pokémon Scarlet / Violet, Legends: Z-A): the file index, the ONEPACK archive and the packs.

``arc/data.trpfd`` is a FlatBuffer: the file hashes (sorted), the pack names, the pack of each file and the pack
sizes. ``arc/data.trpfs`` starts with ``ONEPACK\\0`` and a table (FlatBuffer) of the packs' offsets by name hash. A
pack (``*.trpak``) is a FlatBuffer of file hashes and entries (compression -1 stored, 3 Oodle; the data of an entry
is at the position the FlatBuffer gives). The hashes are FNV-1a 64 of the paths (``game_freak.path_hash``); the paths
themselves are not stored, so ``resolve`` finds them from the pack name and a list of folders.

Decompression needs the Oodle library. The caller gives a ``decompress(packed, size)`` function; nothing here loads a
library.
"""
from __future__ import annotations

import re
import struct
from typing import Callable, Dict, Iterator, List, Sequence, Tuple

from core.containers.game_freak import path_hash as fnv

TRPFD = "arc/data.trpfd"
TRPFS = "arc/data.trpfs"
PREFIXES = ("message/dat/", "ik_message/dat/", "appli/font/bin/", "ui/font/bin/", "appli/data/", "ui/data/",
            "appli/tex/", "ui/tex/", "appli/", "ui/", "")
KIND_STORED = -1
KIND_OODLE = 3
NAME_RE = re.compile(rb"[A-Za-z0-9_./-]+\.(?:bffnt|bfotf|bfttf|otf|ttf|arc|bntx|bin|dat|tbl)\b")


class TrinityError(ValueError):
    """The bytes are not a Trinity index or pack this reader supports."""


class FlatBuffer:
    """Just enough FlatBuffers to read Trinity's tables."""

    def __init__(self, data: bytes):
        self.d = data

    def u32(self, at: int) -> int:
        return struct.unpack_from("<I", self.d, at)[0]

    def root(self) -> int:
        return self.u32(0)

    def field(self, table: int, index: int) -> int:
        """Absolute position of a field (0 when absent)."""
        vt = table - struct.unpack_from("<i", self.d, table)[0]
        size = struct.unpack_from("<H", self.d, vt)[0]
        if 4 + 2 * index >= size:
            return 0
        off = struct.unpack_from("<H", self.d, vt + 4 + 2 * index)[0]
        return table + off if off else 0

    def vector(self, table: int, index: int) -> Tuple[int, int]:
        """(first element position, count) of a vector field."""
        at = self.field(table, index)
        if not at:
            return 0, 0
        at += self.u32(at)
        return at + 4, self.u32(at)

    def tables(self, table: int, index: int) -> List[int]:
        start, count = self.vector(table, index)
        return [start + 4 * i + self.u32(start + 4 * i) for i in range(count)]

    def u64s(self, table: int, index: int) -> List[int]:
        start, count = self.vector(table, index)
        return list(struct.unpack_from(f"<{count}Q", self.d, start))

    def scalar(self, table: int, index: int, fmt: str, default: int = 0) -> int:
        at = self.field(table, index)
        return struct.unpack_from("<" + fmt, self.d, at)[0] if at else default

    def string(self, at: int) -> str:
        at += self.u32(at)
        return self.d[at + 4:at + 4 + self.u32(at)].decode("utf-8")


class Trinity:
    """The index and the archive: which pack holds a file, and the files of each pack.

    ``read_trpfs(offset, size)`` reads bytes of ``arc/data.trpfs``.
    """

    def __init__(self, trpfd: bytes, read_trpfs: Callable[[int, int], bytes]):
        fd = FlatBuffer(trpfd)
        root = fd.root()
        self.file_hashes = fd.u64s(root, 0)
        names_at, count = fd.vector(root, 1)
        self.pack_names = [fd.string(names_at + 4 * i) for i in range(count)]
        self.file_pack = [fd.scalar(t, 0, "Q") for t in fd.tables(root, 2)]
        self.pack_sizes = [fd.scalar(t, 0, "Q") for t in fd.tables(root, 3)]
        self.read = read_trpfs
        head = read_trpfs(0, 16)
        if head[:8] != b"ONEPACK\0":
            raise TrinityError("arc/data.trpfs is not a ONEPACK archive")
        table_at = struct.unpack_from("<Q", head, 8)[0]
        tail = FlatBuffer(read_trpfs(table_at, 0x10 + 16 * len(self.pack_names) + 0x40))
        root = tail.root()
        self.pack_offset = dict(zip(tail.u64s(root, 0), tail.u64s(root, 1)))

    def pack_index(self, pattern: str) -> Iterator[int]:
        """Indexes of the packs whose name matches ``pattern`` (a regular expression)."""
        return (i for i, name in enumerate(self.pack_names) if re.search(pattern, name))

    def pack_files(self, index: int, decompress: Callable[[bytes, int], bytes]) -> List[Tuple[int, bytes]]:
        """[(file hash, data)] of one pack, decompressed."""
        name = self.pack_names[index]
        data = self.read(self.pack_offset[fnv(name)], self.pack_sizes[index])
        return read_pack(data, decompress)


def read_pack(data: bytes, decompress: Callable[[bytes, int], bytes]) -> List[Tuple[int, bytes]]:
    """[(file hash, data)] of a .trpak FlatBuffer; ``decompress(packed, size)`` decodes Oodle entries."""
    fb = FlatBuffer(data)
    root = fb.root()
    out = []
    for h, entry in zip(fb.u64s(root, 0), fb.tables(root, 1)):
        kind = fb.scalar(entry, 1, "b", KIND_STORED)
        size = fb.scalar(entry, 3, "Q")
        start, count = fb.vector(entry, 4)
        raw = data[start:start + count]
        if kind == KIND_OODLE:
            raw = decompress(raw, size)
        elif kind != KIND_STORED:
            raise TrinityError(f"unknown compression {kind} in a pack")
        out.append((h, raw))
    return out


def _tries(text: str, slashes: int) -> Iterator[str]:
    if slashes == 0:
        yield text
        return
    for i in range(1, len(text)):
        for rest in _tries(text[i:], slashes - 1):
            yield text[:i] + "/" + rest


def resolve(pack_name: str, hashes: Sequence[int]) -> Dict[int, str]:
    """{hash: path} for the files of a pack, found from the pack name (the main file's path without slashes)."""
    flat = pack_name[len("arc/"):-len(".trpak")]
    want = set(hashes)
    found: Dict[int, str] = {}
    for prefix in PREFIXES:
        joined = prefix.replace("/", "")
        if not flat.startswith(joined):
            continue
        for slashes in range(4):
            for tail in _tries(flat[len(joined):], slashes):
                path = prefix + tail
                if fnv(path) in want:
                    found[fnv(path)] = path
                    break
            if found:
                break
        if found:
            break
    if found and len(found) < len(want):           # other files of the pack: the same name, other extensions
        main = next(iter(found.values()))
        stem = main.rsplit(".", 1)[0]
        for ext in ("dat", "tbl", "bntx", "bflyt", "arc", "bin", "bffnt", "bfotf", "truiv", "truis"):
            if fnv(f"{stem}.{ext}") in want:
                found[fnv(f"{stem}.{ext}")] = f"{stem}.{ext}"
    return found


def quoted_names(data: bytes, folder: str) -> set:
    """Paths quoted in a file, as they are and in ``folder`` (font settings name fonts by .otf/.ttf)."""
    names = set()
    for m in NAME_RE.findall(data):
        text = re.sub(r"\.(otf|ttf)$", r".bf\1", m.decode("ascii", "replace"))
        names.update((text, f"{folder}/{text.rsplit('/', 1)[-1]}"))
    return names


def name_others(found: Dict[int, str], files: Sequence[Tuple[int, bytes]]) -> None:
    """Name the pack's files that ``resolve`` missed: paths quoted in the pack's files, a layout archive named after
    its BFLYT with the main archive's suffix, the sizes of a font setting, and textures named in a BNTX string table."""
    if not found:
        return
    main = next(iter(found.values()))
    folder = main.rsplit("/", 1)[0]
    want = {h for h, _d in files} - set(found)
    names = {f"{folder}/TextFontSetting.bin"}
    for _h, data in files:
        names.update(quoted_names(data, folder))
    stem = main.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if re.search(r"\d", stem):  # settings for other sizes: system26_bold_efigs -> system32_efigs
        for n in range(256):
            other = re.sub(r"\d+", str(n), stem, count=1)
            names.update(main.replace(stem, v) for v in (other, other.replace("_bold", ""),
                                                          re.sub(r"(\d+)", r"\1_bold", other, count=1)))
    suffix = re.search(r"(_[a-z]{3})?\.arc$", main)
    if suffix:
        for _h, data in files:
            if data[:4] == b"SARC":
                names.update(f"{folder}/{m.decode()}{suffix.group(0)}"
                             for m in re.findall(rb"blyt/([A-Za-z0-9_]+)\.bflyt", data[:16384]))
    for _h, data in files:      # a texture named inside (BNTX string table): the main path with its name
        at = data.find(b"_STR") if data[:4] == b"BNTX" else -1
        if at >= 0:
            names.update(main.replace(stem, m.decode()) for m in re.findall(rb"[A-Za-z0-9_]{4,}", data[at:at + 4096]))
    for name in names:
        if fnv(name) in want:
            found[fnv(name)] = name
