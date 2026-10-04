"""GBA BIOS LZ77 ("LZ10", type 0x10) compression, as the BIOS calls LZ77UnCompWram / LZ77UnCompVram read it.

Stream: byte 0x10, u24 little-endian decompressed size, then groups of a flag byte (MSB first; a set
bit is a back reference) and 8 tokens: a literal byte, or two bytes ``LD DD`` -- length ``(L >> 4) + 3``
(3..18), distance ``((L & 0xF) << 8 | DD) + 1`` (1..4096). The Vram variant writes halfwords, so a
reference must not reach the byte just written (distance >= 2): ``compress(..., vram=True)``.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

MAX_LEN = 18
WINDOW = 4096
_CHAIN = 256                  # candidates tried per position (most recent first)


def decompress(data: bytes, offset: int = 0) -> Tuple[bytes, int]:
    """``(decompressed bytes, end offset of the stream in data)``; ValueError on a broken stream."""
    if len(data) < offset + 4 or data[offset] != 0x10:
        raise ValueError("not a GBA LZ77 (0x10) stream")
    size = int.from_bytes(data[offset + 1:offset + 4], "little")
    out = bytearray()
    pos = offset + 4
    try:
        while len(out) < size:
            flags = data[pos]
            pos += 1
            for bit in range(8):
                if len(out) >= size:
                    break
                if flags & (0x80 >> bit):
                    token = data[pos] << 8 | data[pos + 1]
                    pos += 2
                    length, distance = (token >> 12) + 3, (token & 0xFFF) + 1
                    if distance > len(out):
                        raise ValueError("back reference before the start of the data")
                    for _ in range(length):
                        out.append(out[-distance])
                else:
                    out.append(data[pos])
                    pos += 1
    except IndexError:
        raise ValueError("LZ77 stream ends early") from None
    return bytes(out[:size]), pos


def _longest_matches(data: bytes, min_distance: int) -> Tuple[List[int], List[int]]:
    """Longest back reference (length, distance) at every position, from hash chains of 3-byte prefixes."""
    size = len(data)
    lengths, distances = [0] * size, [0] * size
    chains: Dict[bytes, List[int]] = {}
    for i in range(size - 2):
        key = data[i:i + 3]
        candidates = chains.get(key)
        if candidates:
            limit = min(MAX_LEN, size - i)
            best, best_distance = 0, 0
            for j in reversed(candidates[-_CHAIN:]):
                distance = i - j
                if distance > WINDOW:
                    break
                if distance < min_distance:
                    continue
                length = 3
                while length < limit and data[j + length] == data[i + length]:
                    length += 1
                if length > best:
                    best, best_distance = length, distance
                    if length == limit:
                        break
            lengths[i], distances[i] = best, best_distance
            candidates.append(i)
        else:
            chains[key] = [i]
    return lengths, distances


def compress(data: bytes, vram: bool = False) -> bytes:
    """An LZ77 stream of ``data`` (optimal parse over the longest matches), padded to 4 bytes."""
    data = bytes(data)
    size = len(data)
    if size >= 1 << 24:
        raise ValueError("LZ77 holds at most 16 MiB")
    lengths, distances = _longest_matches(data, 2 if vram else 1)
    # cost[i]: bits to code data[i:]; a literal costs 9 bits, a reference 17.
    cost = [0] * (size + 1)
    step = [1] * (size + 1)
    for i in range(size - 1, -1, -1):
        best, best_step = cost[i + 1] + 9, 1
        for length in range(3, lengths[i] + 1):
            value = cost[i + length] + 17
            if value <= best:
                best, best_step = value, length
        cost[i], step[i] = best, best_step

    out = bytearray(b"\x10" + size.to_bytes(3, "little"))
    i = 0
    while i < size:
        flag_at = len(out)
        out.append(0)
        for bit in range(8):
            if i >= size:
                break
            length = step[i]
            if length == 1:
                out.append(data[i])
            else:
                token = (length - 3) << 12 | (distances[i] - 1)
                out += token.to_bytes(2, "big")
                out[flag_at] |= 0x80 >> bit
            i += length
    out += bytes(-len(out) % 4)
    return bytes(out)
