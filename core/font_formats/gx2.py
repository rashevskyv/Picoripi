"""Wii U (GX2) texture tiling: where each element of a tiled surface lives in memory.

GX2 lays textures out with the R600 address library ("addrlib"): 8x8 micro tiles, and in the
2D tiled modes macro tiles spread over 4 banks and 2 pipes with 256-byte pipe interleave. A block
compressed format (BC1-BC5) tiles its 4x4 blocks as elements. ``element_offsets`` gives the byte
offset of every element, row by row, so a caller can gather the elements into linear order
(``linear = b"".join(raw[o:o + size] for o in offsets)``) or scatter them back.

Only what the Wii U fonts need is here: ``1D_TILED_THIN1`` (2) and ``2D_TILED_THIN1`` (4), one sample,
no depth. Source: AMD's addrlib (R600 ``ComputeSurfaceAddrFromCoordMacroTiled`` / ``MicroTiled``).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Tuple

TILE_1D_THIN1 = 2
TILE_2D_THIN1 = 4

_BANKS = 4
_PIPES = 2
_GROUP_BITS = 8          # 256-byte pipe interleave
_PIPE_BITS = 1
_BANK_BITS = 2


def _pixel_index(x: int, y: int, bpp: int) -> int:
    """Position of an element inside its 8x8 micro tile (thin, not depth)."""
    if bpp == 8:
        bits = ((x & 1), (x & 2) >> 1, (x & 4) >> 2, (y & 2) >> 1, y & 1, (y & 4) >> 2)
    elif bpp == 16:
        bits = ((x & 1), (x & 2) >> 1, (x & 4) >> 2, y & 1, (y & 2) >> 1, (y & 4) >> 2)
    elif bpp in (32, 96):
        bits = ((x & 1), (x & 2) >> 1, y & 1, (x & 4) >> 2, (y & 2) >> 1, (y & 4) >> 2)
    elif bpp == 64:
        bits = ((x & 1), y & 1, (x & 2) >> 1, (x & 4) >> 2, (y & 2) >> 1, (y & 4) >> 2)
    elif bpp == 128:
        bits = (y & 1, (x & 1), (x & 2) >> 1, (x & 4) >> 2, (y & 2) >> 1, (y & 4) >> 2)
    else:
        raise ValueError(f"GX2: {bpp} bits per element is not supported")
    return sum(bit << index for index, bit in enumerate(bits))


def _micro_tiled(x: int, y: int, bpp: int, pitch: int) -> int:
    micro_bytes = 64 * bpp // 8
    micro_per_row = pitch // 8
    tile = (x // 8 + (y // 8) * micro_per_row) * micro_bytes
    return tile + _pixel_index(x, y, bpp) * bpp // 8


def _macro_tiled(x: int, y: int, bpp: int, pitch: int, swizzle: int, slice_index: int) -> int:
    pixel_offset = bpp * _pixel_index(x, y, bpp) // 8
    pipe = ((y >> 3) ^ (x >> 3)) & 1
    bank = (((y // 32) ^ (x >> 3)) & 1) | 2 * (((y // 16) ^ (x >> 4)) & 1)
    bank_pipe = pipe + _PIPES * bank
    pipe_swizzle, bank_swizzle = (swizzle >> 8) & 1, (swizzle >> 9) & 3
    rotation = _PIPES * ((_BANKS >> 1) - 1)      # banks and pipes rotate from one array slice to the next
    bank_pipe ^= pipe_swizzle + _PIPES * bank_swizzle + slice_index * rotation
    bank_pipe %= _PIPES * _BANKS
    pipe, bank = bank_pipe % _PIPES, bank_pipe // _PIPES

    macro_pitch, macro_height = 8 * _BANKS, 8 * _PIPES
    macro_bytes = bpp * macro_height * macro_pitch // 8
    macro_offset = (x // macro_pitch + (pitch // macro_pitch) * (y // macro_height)) * macro_bytes
    total = pixel_offset + (macro_offset >> (_BANK_BITS + _PIPE_BITS))
    group_mask = (1 << _GROUP_BITS) - 1
    high = (total & ~group_mask) << (_BANK_BITS + _PIPE_BITS)
    return (bank << (_PIPE_BITS + _GROUP_BITS)) | (pipe << _GROUP_BITS) | (total & group_mask) | high


@lru_cache(maxsize=8)
def element_offsets(width: int, height: int, bpp: int, tile_mode: int = TILE_2D_THIN1,
                    swizzle: int = 0, slice_index: int = 0) -> Tuple[int, ...]:
    """Byte offset of every element (row by row) of a ``width`` x ``height`` element surface.

    ``bpp`` is bits per element (64 for BC1/BC4, 128 for BC2/BC3/BC5). The pitch is the width rounded
    up to the tile mode's alignment (8 for 1D, 32 for 2D). ``slice_index`` is the layer of a texture array
    (the offsets are relative to that layer's start)."""
    if tile_mode == TILE_2D_THIN1:
        pitch = -(-width // 32) * 32
        return tuple(_macro_tiled(x, y, bpp, pitch, swizzle, slice_index)
                     for y in range(height) for x in range(width))
    if tile_mode == TILE_1D_THIN1:
        pitch = -(-width // 8) * 8
        return tuple(_micro_tiled(x, y, bpp, pitch) for y in range(height) for x in range(width))
    raise ValueError(f"GX2 tile mode {tile_mode} is not supported")
