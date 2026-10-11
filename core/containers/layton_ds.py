"""Professor Layton on Nintendo DS: BIOS compression with the games' prefix and the three pack formats.

Compression: the DS BIOS streams ``0x10`` (LZ10), ``0x24`` / ``0x28`` (Huffman, 4 / 8 bit) and ``0x30`` (RLE).
Curious Village (``LAYTON1``) puts a 4-byte type in front of a stream (1 RLE, 2 LZ10, 3 Huffman 4, 4 Huffman 8),
the later games store the bare stream. ``decompress`` reads both; ``recompress`` writes LZ10 in the style of the
original (prefix or none).

Packs (what ``.pcm``, ``.plz`` and ``.cpck`` hold after decompression), all 4-aligned:

- ``LPCK`` (Curious Village): u32 header offset (0x10), u32 length, u32 file count, ``LPCK``;
- ``PCK2`` (Pandora's Box): u32 0x10, u32 length, ``PCK2``, u32 0;
- ``LPC2`` (Lost Future): ``LPC2``, u32 count, offset of the data, length, offset of the 12-byte records
  (name offset, data offset, size), offset of the NUL-terminated names.

In LPCK and PCK2 every file has a 16-byte record -- u32 name field + 16, u32 record length, u32 0, u32 size --
then the name (NUL-padded to the length the record says) and the data padded to 4.

The pack codec is ported from bullbin's ``madhatter`` (MIT licence, https://github.com/bullbin/madhatter).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from core.containers import level5, lz10

LPCK, PCK2, LPC2 = b"LPCK", b"PCK2", b"LPC2"
PREFIX_TYPES = {1: 0x30, 2: 0x10, 3: 0x24, 4: 0x28}   # Curious Village prefix -> BIOS type


# -- compression ------------------------------------------------------------------------------------------

def _huffman(data: bytes, pos: int, size: int, bits: int) -> bytes:
    tree_len = (data[pos] + 1) * 2
    tree = data[pos:pos + tree_len]
    pos += tree_len
    wanted = size * 8 // bits
    symbols = bytearray()
    node = 1
    while len(symbols) < wanted:
        word = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        for shift in range(31, -1, -1):
            bit = (word >> shift) & 1
            current = tree[node]
            nxt = (node & ~1) + ((current & 0x3F) + 1) * 2 + bit
            if current >> (7 if bit == 0 else 6) & 1:
                symbols.append(tree[nxt])
                node = 1
                if len(symbols) >= wanted:
                    break
            else:
                node = nxt
    if bits == 8:
        return bytes(symbols)
    return bytes(symbols[2 * i] | symbols[2 * i + 1] << 4 for i in range(size))


def bios_decompress(data: bytes, offset: int = 0) -> bytes:
    """A BIOS stream at ``offset`` (LZ10, Huffman 4/8, RLE); ValueError when it is none of them."""
    kind = data[offset]
    size = int.from_bytes(data[offset + 1:offset + 4], "little")
    try:
        if kind == 0x10:
            return lz10.decompress(data, offset)[0]
        if kind == 0x00 and size and offset + 4 + size <= len(data):      # stored, with the size header
            return bytes(data[offset + 4:offset + 4 + size])
        if kind == 0x30:
            return level5.rle_body(data, offset + 4, size)
        if kind in (0x24, 0x28):
            return _huffman(data, offset + 4, size, kind & 0xF)
    except (IndexError, struct.error) as error:
        raise ValueError(f"broken BIOS stream: {error}") from None
    raise ValueError(f"not a BIOS compressed stream (type {kind:#04x})")


def prefix_of(data: bytes) -> int:
    """The Curious Village type prefix (1..4) of ``data``, or 0 for a bare stream."""
    if len(data) >= 8 and int.from_bytes(data[:4], "little") in PREFIX_TYPES and data[4] == PREFIX_TYPES[data[0]]:
        return data[0]
    return 0


def decompress(data: bytes) -> Tuple[bytes, int]:
    """``(plain, prefix)`` of a compressed Layton file (prefix 0: bare stream)."""
    prefix = prefix_of(data)
    return bios_decompress(data, 4 if prefix else 0), prefix


def recompress(original: bytes, plain: bytes) -> bytes:
    """``plain`` compressed in the style of ``original``; unchanged data gives the original bytes back."""
    old, prefix = decompress(original)
    if old == plain:
        return bytes(original)
    lead = b"\x02\x00\x00\x00" if prefix else b""
    if original[4 if prefix else 0] == 0x00:                   # a stored file (type 0, size) stays stored
        return lead + b"\x00" + len(plain).to_bytes(3, "little") + plain
    return lead + lz10.compress(plain)


# -- packs ----------------------------------------------------------------------------------------------

@dataclass
class Member:
    name: str
    data: bytes
    field: int = 0          # LPCK / PCK2: the name field length of the record (0: as short as it goes)


@dataclass
class Pack:
    kind: bytes                                     # LPCK, PCK2 or LPC2
    members: List[Member] = field(default_factory=list)
    tail: bytes = b""
    align: int = 4          # LPCK / PCK2: the unit a record (header + name + data) is padded to

    @classmethod
    def detect(cls, plain: bytes) -> Optional[bytes]:
        if plain[:4] == LPC2:
            return LPC2
        if len(plain) >= 16 and plain[:4] == b"\x10\x00\x00\x00":
            if plain[12:16] == LPCK:
                return LPCK
            if plain[8:12] == PCK2:
                return PCK2
        return None

    @classmethod
    def parse(cls, plain: bytes) -> "Pack":
        kind = cls.detect(plain)
        if kind == LPC2:
            return cls._parse_lpc2(plain)
        if kind is None:
            raise ValueError("not a Layton pack")
        return cls._parse_lpck(plain, kind)

    @classmethod
    def _parse_lpck(cls, plain: bytes, kind: bytes) -> "Pack":
        start, length = struct.unpack_from("<II", plain, 0)
        members, pos, spans = [], start, []
        while pos < length:
            name_end, step, _zero, size = struct.unpack_from("<IIII", plain, pos)
            name = plain[pos + 16:pos + name_end].split(b"\0")[0].decode("shift-jis")
            members.append(Member(name, plain[pos + name_end:pos + name_end + size], name_end - 16))
            if step < name_end + size:
                raise ValueError("broken pack record")
            spans.append((name_end + size, step))
            pos += step
        # the unit the records are padded to: 16 or 4, with 1..unit filler bytes (never none)
        unit = next((u for u in (16, 4) if all((used // u + 1) * u == step for used, step in spans)), 4)
        return cls(kind, members, plain[length:], unit)

    @classmethod
    def _parse_lpc2(cls, plain: bytes) -> "Pack":
        count, data_at, _length, meta_at, name_at = struct.unpack_from("<5I", plain, 4)
        members = []
        for i in range(count):
            name_off, data_off, size = struct.unpack_from("<III", plain, meta_at + 12 * i)
            at = name_at + name_off
            name = plain[at:plain.index(b"\0", at)].decode("shift-jis")
            members.append(Member(name, plain[data_at + data_off:data_at + data_off + size]))
        return cls(LPC2, members, b"")

    def build(self) -> bytes:
        if self.kind == LPC2:
            return self._build_lpc2()
        body = bytearray()
        for member in self.members:
            name = member.name.encode("shift-jis") + b"\0"
            width = max(member.field, len(name))
            width += -width % 4
            used = width + 16 + len(member.data)
            padded = len(member.data) + (self.align - used % self.align)
            body += struct.pack("<IIII", width + 16, width + 16 + padded, 0, len(member.data))
            body += name + bytes(width - len(name)) + member.data + bytes(padded - len(member.data))
        head = struct.pack("<II", 0x10, 0x10 + len(body))
        if self.kind == LPCK:
            head += struct.pack("<I", len(self.members)) + LPCK
        else:
            head += PCK2 + bytes(4)
        return head + bytes(body) + self.tail

    def _build_lpc2(self) -> bytes:
        names, data, meta = bytearray(), bytearray(), bytearray()
        for member in self.members:
            meta += struct.pack("<III", len(names), len(data), len(member.data))
            names += member.name.encode("shift-jis") + b"\0"
            data += member.data + bytes(4 - len(member.data) % 4)      # 1..4 filler bytes
        names += bytes(-len(names) % 4)
        name_at = 0x20 + len(meta)
        data_at = name_at + len(names)
        head = LPC2 + struct.pack("<7I", len(self.members), data_at, data_at + len(data), 0x20, name_at, data_at, 0)
        return head + bytes(meta) + bytes(names) + bytes(data)

    def get(self, name: str) -> Optional[Member]:
        return next((m for m in self.members if m.name == name), None)
