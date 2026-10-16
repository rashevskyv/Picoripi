"""Unity AssetBundles (``UnityFS``): the directory of files inside a bundle, and a bundle written again with new files.

Layout (big-endian): the signature ``UnityFS\\0``, u32 format version, the Unity version and revision (C strings),
i64 bundle size, u32 compressed and u32 uncompressed size of the block info, u32 flags. Flags: bits 0-5 the compression of
the block info and the data blocks (0 none, 2 and 3 LZ4 or LZ4HC), bit 0x40 directory combined with the blocks (not
written here), bit 0x80 block info at the end of the bundle (read only when it is at the start), bit 0x200 the block
info is padded to 16 bytes at the start and the data starts on a 16-byte boundary.

The block info, once decompressed, holds a 16-byte hash, u32 block count, the blocks (u32 uncompressed size, u32
compressed size, u16 flags) and the directory (u32 count, then per file: i64 offset, i64 size, u32 flags, C string
name). The files are the byte ranges of the concatenated decompressed blocks.

``Bundle.build`` writes a bundle whose data blocks and block info are stored, not compressed: the game reads it the
same way. It keeps the header of the bundle it came from.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Dict, List, Optional

from core.containers.retro_pak import lz4_block

SIGNATURE = b"UnityFS\x00"
FLAG_COMPRESSION = 0x3F
FLAG_DIRECTORY_COMBINED = 0x40
FLAG_INFO_AT_END = 0x80
FLAG_INFO_PADDED = 0x200
_ALIGN = 16


class UnityFsError(ValueError):
    """The bytes are not a UnityFS bundle this reader supports."""


@dataclass
class Node:
    """One file of a bundle: its name, the range of the decompressed stream, and its flags."""

    name: str
    offset: int
    size: int
    flags: int


def _align(value: int) -> int:
    return (value + _ALIGN - 1) & ~(_ALIGN - 1)


def _unpack_block(raw: bytes, compression: int, size: int) -> bytes:
    if compression == 0:
        return raw
    if compression in (2, 3):   # LZ4 and LZ4HC share one block format
        return lz4_block(raw, size)
    raise UnityFsError(f"compression {compression} is not supported")


class Bundle:
    """A parsed UnityFS bundle: ``nodes`` and ``read(name)`` give each file's bytes."""

    def __init__(self, data: bytes):
        if not data.startswith(SIGNATURE):
            raise UnityFsError("not a UnityFS bundle")
        self.data = data
        at = len(SIGNATURE)
        self.format_version = struct.unpack_from(">I", data, at)[0]
        at += 4
        self.unity_version_end = data.index(b"\x00", at) + 1
        self.unity_version = data[at:self.unity_version_end - 1]
        at = self.unity_version_end
        self.unity_revision_end = data.index(b"\x00", at) + 1
        self.unity_revision = data[at:self.unity_revision_end - 1]
        at = self.unity_revision_end
        self.size = struct.unpack_from(">q", data, at)[0]
        compressed, uncompressed, self.flags = struct.unpack_from(">III", data, at + 8)
        header_end = at + 20
        if self.flags & FLAG_INFO_AT_END:
            raise UnityFsError("block info at the end of the bundle is not supported")
        # format 7 and later pad the header to 16 bytes before the block info (bundles of Unity 2019 have flag 0x40 and
        # no 0x200 bit; the block info is at 64 there)
        self.info_at = _align(header_end) if self.format_version >= 7 else header_end
        info = _unpack_block(data[self.info_at:self.info_at + compressed], self.flags & FLAG_COMPRESSION, uncompressed)
        self.info_hash = info[:16]
        count = struct.unpack_from(">i", info, 16)[0]
        self.blocks = []   # (uncompressed size, compressed size, flags)
        for index in range(count):
            self.blocks.append(struct.unpack_from(">IIH", info, 20 + 10 * index))
        at = 20 + 10 * count
        nodes = struct.unpack_from(">i", info, at)[0]
        at += 4
        self.nodes: List[Node] = []
        for _ in range(nodes):
            offset, size, flags = struct.unpack_from(">qqI", info, at)
            end = info.index(b"\x00", at + 20)
            self.nodes.append(Node(info[at + 20:end].decode("utf-8", "replace"), offset, size, flags))
            at = end + 1
        self.data_at = _align(self.info_at + compressed) if self.flags & FLAG_INFO_PADDED else self.info_at + compressed
        self._stream: Optional[bytes] = None

    def stream(self) -> bytes:
        """The decompressed data of all blocks: the files' byte ranges index into it."""
        if self._stream is None:
            out = bytearray()
            pos = self.data_at
            for usize, csize, bflags in self.blocks:
                out += _unpack_block(self.data[pos:pos + csize], bflags & FLAG_COMPRESSION, usize)
                pos += csize
            self._stream = bytes(out)
        return self._stream

    def names(self) -> List[str]:
        return [node.name for node in self.nodes]

    def read(self, name: str) -> bytes:
        for node in self.nodes:
            if node.name == name:
                return self.stream()[node.offset:node.offset + node.size]
        raise KeyError(name)

    def build(self, replaced: Dict[str, bytes]) -> bytes:
        """The bundle with the files ``replaced`` (name -> new bytes); the other files and the header are kept.

        A replaced name must exist in the bundle. The result stores its blocks uncompressed.
        """
        unknown = set(replaced) - set(self.names())
        if unknown:
            raise UnityFsError(f"no file {sorted(unknown)[0]} in the bundle")
        stream = bytearray()
        nodes = []
        for node in self.nodes:
            raw = replaced[node.name] if node.name in replaced else self.stream()[node.offset:node.offset + node.size]
            nodes.append(Node(node.name, len(stream), len(raw), node.flags))
            stream += raw
        info = bytearray(self.info_hash)
        info += struct.pack(">i", 1)
        info += struct.pack(">IIH", len(stream), len(stream), 0)
        info += struct.pack(">i", len(nodes))
        for node in nodes:
            info += struct.pack(">qqI", node.offset, node.size, node.flags) + node.name.encode("utf-8") + b"\x00"
        flags = (self.flags & ~(FLAG_COMPRESSION | FLAG_DIRECTORY_COMBINED | FLAG_INFO_AT_END))
        head = bytearray(SIGNATURE)
        head += struct.pack(">I", self.format_version) + self.unity_version + b"\x00"
        head += self.unity_revision + b"\x00"
        head += struct.pack(">q", 0) + struct.pack(">III", len(info), len(info), flags)
        info_at = _align(len(head)) if self.format_version >= 7 else len(head)
        head += b"\x00" * (info_at - len(head))
        data_at = _align(info_at + len(info)) if flags & FLAG_INFO_PADDED else info_at + len(info)
        out = head + info + b"\x00" * (data_at - info_at - len(info)) + stream
        struct.pack_into(">q", out, len(SIGNATURE) + 4 + len(self.unity_version) + 1 + len(self.unity_revision) + 1,
                         len(out))
        return bytes(out)
