"""Retro Studios ``RFRM PACK`` packages of Donkey Kong Country: Tropical Freeze (Switch), big-endian.

Unlike ``core.containers.retro_pak`` (little-endian, Metroid Prime 4 and Prime Remastered), every field here is
big-endian. Layout, checked on the base game's MiscData.pak and on the Ukrainian mod's copy:

- ``RFRM`` form header, 0x20 bytes: ``RFRM``, u64 size (the data end minus 0x20), u64 0, fourcc kind
  (``PACK``), u32 reader, u32 writer.
- ``TOCC`` form (0x20 bytes) with chunks. A chunk is fourcc, u64 size, u32 unknown, u64 skip, then ``skip``
  bytes, then the body (24 header bytes in all). Chunks: ``ADIR`` (asset directory), ``META`` (per-asset
  metadata), ``STRG`` (names).
- ``ADIR``: u32 count, then per asset: fourcc type, 16-byte GUID, u64 offset, u64 size (36 bytes each).
- ``META``: u32 count, (GUID, u32 offset) pairs (20 bytes each); at each offset a u32 size and the bytes.
- ``STRG``: u32 count, then (fourcc, GUID, u32 length, name bytes) entries.

An asset is an ``RFRM`` form of its own; its kind is the asset type (``MSBT``, ``LDTA``, ...). Chunked assets
hold children in the same chunk layout (a child tag, e.g. ``USEN`` for an MSBT language). Some assets (``CABH``)
have no chunks: their body is raw data and ``children`` raises ``ValueError`` for them.

Writing keeps every byte it did not change. A replaced asset is appended after the end of the file (16-byte
aligned); only its directory entry changes (offset and size), and the PACK size becomes the new data end minus
0x20. The old copy stays where it was, as the Ukrainian mod leaves it.
"""
from __future__ import annotations

from core.i18n import tr
import struct
from dataclasses import dataclass, field
from typing import Dict, List

FORM = struct.Struct(">4sQQ4sII")       # RFRM header (0x20 bytes)
CHUNK = struct.Struct(">4sQIQ")         # chunk header (0x18 bytes, then ``skip`` bytes, then the body)
ENTRY = 36                              # ADIR entry size
_ALIGN = 0x10


@dataclass
class Asset:
    """One ADIR entry: ``index`` is its position in the directory."""

    index: int
    type: str
    guid: bytes
    offset: int
    size: int
    names: List[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.guid.hex()

    @property
    def name(self) -> str:
        return self.names[0] if self.names else self.id


@dataclass
class Child:
    """A chunk of an asset: its tag, its header bytes (with the skip padding) and its body."""

    tag: str
    header: bytes
    body: bytes


def _chunks(data: bytes, start: int, end: int):
    """``(fourcc, body offset, body size)`` of every chunk in ``data[start:end]``."""
    position = start
    while position < end:
        kind, size, _unk, skip = CHUNK.unpack_from(data, position)
        body = position + CHUNK.size + skip
        if body + size > end:
            raise ValueError(tr("Chunk {0!r} at {1:#x} runs past the end", kind, position))
        yield kind.decode("latin-1"), body, size
        position = body + size


class Pak:
    """A DKTF package: the directory, the names and the assets, read in place (``data`` is the whole file)."""

    def __init__(self, data: bytes):
        self.data = data        # bytes or a read-only mmap (the level packages are 400 MB)
        kind, _size, _zero, pack, _r, _w = FORM.unpack_from(self.data, 0)
        if kind != b"RFRM" or pack != b"PACK":
            raise ValueError(tr("Not a big-endian Retro package (RFRM PACK)"))
        toc_kind, toc_size, _zero2, tocc, _r2, _w2 = FORM.unpack_from(self.data, FORM.size)
        if toc_kind != b"RFRM" or tocc != b"TOCC":
            raise ValueError(tr("Package without a TOCC form"))
        self.toc_start = 2 * FORM.size
        self.toc_end = FORM.size + FORM.size + toc_size
        self.assets: List[Asset] = []
        self.meta: Dict[bytes, bytes] = {}
        names: Dict[bytes, List[str]] = {}
        self.adir_body = -1
        for kind_, body, size in _chunks(self.data, self.toc_start, self.toc_end):
            if kind_ == "ADIR":
                self.adir_body = body
                count = struct.unpack_from(">I", self.data, body)[0]
                if 4 + count * ENTRY != size:
                    raise ValueError(tr("ADIR size does not match its entries"))
                for i in range(count):
                    at = body + 4 + i * ENTRY
                    type_, guid, offset, length = struct.unpack_from(">4s16sQQ", self.data, at)
                    self.assets.append(Asset(i, type_.decode("latin-1"), guid, offset, length))
            elif kind_ == "META":
                count = struct.unpack_from(">I", self.data, body)[0]
                for i in range(count):
                    guid, offset = struct.unpack_from(">16sI", self.data, body + 4 + i * 20)
                    length = struct.unpack_from(">I", self.data, body + offset)[0]
                    self.meta[guid] = self.data[body + offset + 4:body + offset + 4 + length]
            elif kind_ == "STRG":
                count, at = struct.unpack_from(">I", self.data, body)[0], body + 4
                for _ in range(count):
                    guid, length = struct.unpack_from(">16sI", self.data, at + 4)
                    text = self.data[at + 24:at + 24 + length].decode("utf-8", "replace")
                    names.setdefault(guid, []).append(text)
                    at += 24 + length
        if self.adir_body < 0:
            raise ValueError(tr("Package without an ADIR chunk"))
        for asset in self.assets:
            asset.names = names.get(asset.guid, [])
        self.data_end = max((a.offset + a.size for a in self.assets), default=self.toc_end)

    def find(self, type_: str = "") -> List[Asset]:
        return [a for a in self.assets if not type_ or a.type == type_]

    def raw(self, asset: Asset) -> bytes:
        """The asset's ``RFRM`` form exactly as stored."""
        end = asset.offset + asset.size
        if end > len(self.data):
            raise ValueError(tr("asset {0} runs past the end of the package", asset.name))
        return self.data[asset.offset:end]

    def children(self, asset: Asset) -> List[Child]:
        return parse_children(self.raw(asset))


def parse_children(form: bytes) -> List[Child]:
    """Split a chunked ``RFRM`` asset form into its children; the sizes must add up to the form."""
    kind, size, _zero, _k, _r, _w = FORM.unpack_from(form, 0)
    if kind != b"RFRM" or size + FORM.size != len(form):
        raise ValueError(tr("Asset is not a complete RFRM form"))
    out: List[Child] = []
    at = FORM.size
    while at < len(form):
        if at + CHUNK.size > len(form):
            raise ValueError(tr("Truncated child header"))
        tag, length, _unk, skip = CHUNK.unpack_from(form, at)
        body = at + CHUNK.size + skip
        if body + length > len(form):
            raise ValueError(tr("Child {0!r} runs past the end of its asset", tag))
        out.append(Child(tag.decode("latin-1"), form[at:body], form[body:body + length]))
        at = body + length
    return out


def build_form(kind: bytes, children: List[Child], reader: int = 0, writer: int = 0) -> bytes:
    """An ``RFRM`` asset form from children; each child's header gets its new body size."""
    body = bytearray()
    for child in children:
        header = bytearray(child.header)
        struct.pack_into(">Q", header, 4, len(child.body))
        body += header + child.body
    return FORM.pack(b"RFRM", len(body), 0, kind, reader, writer) + bytes(body)


def write(pak: Pak, replacements: Dict[bytes, bytes]) -> bytes:
    """The package with the assets in ``replacements`` (GUID -> new ``RFRM`` form) replaced.

    With no replacements the result equals the input byte for byte.
    """
    if not replacements:
        return pak.data
    by_guid = {a.guid: a for a in pak.assets}
    for guid in replacements:
        if guid not in by_guid:
            raise KeyError(f"no asset with GUID {guid.hex()}")
    out = bytearray(pak.data)
    end = len(out)
    for guid, form in replacements.items():
        asset = by_guid[guid]
        end += -end % _ALIGN
        out += b"\0" * (end - len(out)) + form
        struct.pack_into(">QQ", out, pak.adir_body + 4 + asset.index * ENTRY + 20, end, len(form))
        end += len(form)
    struct.pack_into(">Q", out, 4, end - FORM.size)
    return bytes(out)
