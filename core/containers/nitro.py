"""Nintendo DS file formats shared by DS / DSi games: LZ11 and backward LZ ("BLZ") compression, NARC archives.

LZ11 (type 0x11): byte 0x11, u24 size (0 = a u32 size follows), then flag bytes (MSB first) over 8 tokens;
a reference is ``(L-1)<<4 | D>>8, D&0xFF`` for lengths 3..16 (first nibble >= 2), ``0L LD DD`` for 17..272
and ``1L LL LD DD`` for 273..65808; ``D + 1`` is the distance.

BLZ (the SDK's ``MI_UncompressBackward``, used for overlays and ``*.blz`` files) is read from the end:
the last u32 is the size the file grows by, the u32 before it holds the compressed length (from the end,
footer included, bits 0-23) and the footer length (bits 24-31). Flags and tokens are read backwards; a
reference is u16 ``LLLL DDDD DDDD DDDD`` (low byte first in memory): length ``L + 3``, distance ``D + 3``.
The bytes before the compressed part are stored plain. The game decompresses in place, so the compressor
keeps a plain head long enough that writing never overtakes reading.

NARC: header, BTAF (file spans), BTNF (names, as the NitroFS FNT), GMIF (data). Writing a member lays the
data out again (4-byte aligned, 0xFF filler as the game's own archives have it).
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from core.containers import lz10
from core.containers.base_container import BaseArchiveContainer


# -- LZ11 -------------------------------------------------------------------------------------------------

def lz11_decompress(data: bytes, offset: int = 0) -> Tuple[bytes, int]:
    """``(decompressed bytes, end offset of the stream)``; ValueError on a broken stream."""
    if len(data) < offset + 4 or data[offset] != 0x11:
        raise ValueError("not an LZ11 stream")
    size = int.from_bytes(data[offset + 1:offset + 4], "little")
    pos = offset + 4
    if size == 0:
        size = int.from_bytes(data[pos:pos + 4], "little")
        pos += 4
    out = bytearray()
    try:
        while len(out) < size:
            flags = data[pos]
            pos += 1
            for bit in range(8):
                if len(out) >= size:
                    break
                if not flags & (0x80 >> bit):
                    out.append(data[pos])
                    pos += 1
                    continue
                kind = data[pos] >> 4
                if kind == 0:
                    length = ((data[pos] & 15) << 4 | data[pos + 1] >> 4) + 0x11
                    distance = ((data[pos + 1] & 15) << 8 | data[pos + 2]) + 1
                    pos += 3
                elif kind == 1:
                    length = ((data[pos] & 15) << 12 | data[pos + 1] << 4 | data[pos + 2] >> 4) + 0x111
                    distance = ((data[pos + 2] & 15) << 8 | data[pos + 3]) + 1
                    pos += 4
                else:
                    length = kind + 1
                    distance = ((data[pos] & 15) << 8 | data[pos + 1]) + 1
                    pos += 2
                if distance > len(out):
                    raise ValueError("back reference before the start of the data")
                for _ in range(length):
                    out.append(out[-distance])
    except IndexError:
        raise ValueError("LZ11 stream ends early") from None
    return bytes(out[:size]), pos


def _parse(data: bytes, min_distance: int, max_len: int) -> Tuple[List[int], List[int]]:
    """Optimal parse over the longest matches: ``(step, distance)`` per position (step 1 = literal)."""
    lengths, distances = lz10._longest_matches(data, min_distance)
    size = len(data)
    cost, step = [0] * (size + 1), [1] * (size + 1)
    for i in range(size - 1, -1, -1):
        best, best_step = cost[i + 1] + 9, 1
        for length in range(3, min(lengths[i], max_len) + 1):
            value = cost[i + length] + 17
            if value <= best:
                best, best_step = value, length
        cost[i], step[i] = best, best_step
    return step, distances


def lz11_compress(data: bytes) -> bytes:
    """An LZ11 stream of ``data`` (references of 3..16 bytes), padded to 4 bytes."""
    data = bytes(data)
    size = len(data)
    out = bytearray(b"\x11" + size.to_bytes(3, "little") if 0 < size < 1 << 24
                    else b"\x11\0\0\0" + size.to_bytes(4, "little"))
    step, distances = _parse(data, 1, 16)
    i = 0
    while i < size:
        flag_at = len(out)
        out.append(0)
        for bit in range(8):
            if i >= size:
                break
            if step[i] == 1:
                out.append(data[i])
            else:
                out += ((step[i] - 1) << 12 | (distances[i] - 1)).to_bytes(2, "big")
                out[flag_at] |= 0x80 >> bit
            i += step[i]
    out += bytes(-len(out) % 4)
    return bytes(out)


# -- BLZ --------------------------------------------------------------------------------------------------

def blz_footer(data: bytes) -> Tuple[int, int, int]:
    """``(compressed length, footer length, growth)``; growth 0 = stored plain."""
    if len(data) < 8:
        raise ValueError("too short for a BLZ footer")
    packed, growth = struct.unpack_from("<II", data, len(data) - 8)
    return packed & 0xFFFFFF, packed >> 24, growth


def blz_decompress(data: bytes) -> bytes:
    data = bytes(data)
    compressed, footer, growth = blz_footer(data)
    if growth == 0:
        return data
    if not 8 <= footer <= 11 or footer > compressed or compressed > len(data):
        raise ValueError("not a BLZ file")
    out = bytearray(data) + bytes(growth)
    src, dst, stop = len(data) - footer, len(out), len(data) - compressed
    try:
        while src > stop:
            src -= 1
            flags = data[src]
            for bit in range(8):
                if src <= stop:
                    break
                if flags & (0x80 >> bit):
                    src -= 2
                    value = data[src] | data[src + 1] << 8
                    for _ in range((value >> 12) + 3):
                        dst -= 1
                        out[dst] = out[dst + (value & 0xFFF) + 3]
                else:
                    src -= 1
                    dst -= 1
                    out[dst] = data[src]
    except IndexError:
        raise ValueError("broken BLZ stream") from None
    if dst != stop:
        raise ValueError("BLZ stream does not fill the file")
    return bytes(out)


def _blz_tokens(tail: bytes) -> bytes:
    """The backward stream of ``tail`` (as it lies in memory, before the footer)."""
    rev = tail[::-1]
    step, distances = _parse(rev, 3, 18)
    out = bytearray()
    i = 0
    while i < len(rev):
        flag_at = len(out)
        out.append(0)
        for bit in range(8):
            if i >= len(rev):
                break
            if step[i] == 1:
                out.append(rev[i])
            else:
                value = (step[i] - 3) << 12 | (distances[i] - 3)
                out += bytes((value >> 8, value & 0xFF))
                out[flag_at] |= 0x80 >> bit
            i += step[i]
    return bytes(out[::-1])


def _blz_safe(stream: bytes, head: int, plain_size: int) -> bool:
    """Decompressing in place never writes over a byte not read yet."""
    src, dst, at = head + len(stream), plain_size, len(stream)
    while at > 0:
        at -= 1
        src -= 1
        flags = stream[at]
        for bit in range(8):
            if at <= 0:
                break
            if flags & (0x80 >> bit):
                at -= 2
                src -= 2
                dst -= (((stream[at] | stream[at + 1] << 8) >> 12) + 3)
            else:
                at -= 1
                src -= 1
                dst -= 1
            if dst < src:
                return False
    return True


def blz_compress(data: bytes) -> bytes:
    """A BLZ file of ``data``: the tail compressed, a plain head as long as in-place decompression needs."""
    data = bytes(data)
    head = 0
    while True:
        stream = _blz_tokens(data[head:])
        if _blz_safe(stream, head, len(data)):
            break
        head = min(len(data), head + max(0x200, (len(data) - head) // 16))
    body = data[:head] + stream
    footer = 8 + (-len(body) % 4)
    packed = len(stream) + footer
    growth = len(data) - (len(body) + footer)
    if growth <= 0:
        raise ValueError("The data does not compress; BLZ cannot hold it")
    return body + b"\xff" * (footer - 8) + struct.pack("<II", packed | footer << 24, growth)


# -- NARC -------------------------------------------------------------------------------------------------

class NarcContainer(BaseArchiveContainer):
    """A NARC archive; members by their path in the archive's name table (``#<id>`` when it has none)."""

    MAGIC = b"NARC"

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return data[:4] == cls.MAGIC and len(data) >= 16 and struct.unpack_from("<I", data, 8)[0] == len(data)

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        blocks: Dict[bytes, Tuple[int, int]] = {}
        at = struct.unpack_from("<H", data, 12)[0]
        while at + 8 <= len(data):
            magic, size = data[at:at + 4], struct.unpack_from("<I", data, at + 4)[0]
            blocks[magic] = (at, size)
            at += max(size, 8)
        self._fat, _ = blocks[b"BTAF"]
        self._gmif, _ = blocks[b"GMIF"]
        count = struct.unpack_from("<H", data, self._fat + 8)[0]
        spans = [struct.unpack_from("<II", data, self._fat + 12 + 8 * i) for i in range(count)]
        base = self._gmif + 8
        self._files: List[bytes] = [self._data[base + a:base + b] for a, b in spans]
        self._names: Dict[str, int] = {}
        fnt = blocks[b"BTNF"][0] + 8

        def walk(dir_id: int, prefix: str) -> None:
            sub, first, _ = struct.unpack_from("<IHH", data, fnt + (dir_id & 0xFFF) * 8)
            pos, file_id = fnt + sub, first
            while data[pos]:
                length = data[pos] & 0x7F
                name = data[pos + 1:pos + 1 + length].decode("ascii", "replace")
                if data[pos] & 0x80:
                    walk(struct.unpack_from("<H", data, pos + 1 + length)[0], prefix + name + "/")
                    pos += 3 + length
                else:
                    self._names[prefix + name] = file_id
                    file_id += 1
                    pos += 1 + length

        if struct.unpack_from("<I", data, fnt)[0] > 8 or data[fnt + struct.unpack_from("<I", data, fnt)[0]]:
            walk(0xF000, "")
        named = set(self._names.values())
        for file_id in range(count):
            if file_id not in named:
                self._names[f"#{file_id}"] = file_id
        self._changed: Dict[int, bytes] = {}

    def list_files(self) -> list[str]:
        return list(self._names)

    def _id(self, path: str) -> int:
        try:
            return self._names[path]
        except KeyError:
            raise KeyError(f"No {path} in the NARC") from None

    def read_file(self, path: str) -> bytes:
        file_id = self._id(path)
        return self._changed.get(file_id, self._files[file_id])

    def write_file(self, path: str, data: bytes) -> None:
        self._changed[self._id(path)] = bytes(data)

    def has_pending_changes(self) -> bool:
        return any(self._files[i] != data for i, data in self._changed.items())

    def pack(self) -> bytes:
        if not self.has_pending_changes():
            return self._data
        body, spans = bytearray(), []
        for file_id, old in enumerate(self._files):
            body += b"\xff" * (-len(body) % 4)
            data = self._changed.get(file_id, old)
            spans.append((len(body), len(body) + len(data)))
            body += data
        body += b"\xff" * (-len(body) % 4)
        out = bytearray(self._data[:self._gmif])
        for file_id, (a, b) in enumerate(spans):
            struct.pack_into("<II", out, self._fat + 12 + 8 * file_id, a, b)
        out += b"GMIF" + struct.pack("<I", 8 + len(body)) + body
        struct.pack_into("<I", out, 8, len(out))
        return bytes(out)
