"""Switch (Tegra X1) block-linear surfaces: where each element of a texture lives in memory.

A surface is cut into GOBs (64 bytes x 8 rows, 512 bytes); ``block_height`` GOBs stack into a block,
blocks run left to right, then down. An element is a pixel or a 4x4 block of a compressed format.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Tuple


@lru_cache(maxsize=16)
def block_addresses(elements_wide: int, elements_high: int, bpp: int, block_height: int) -> Tuple[int, ...]:
    """Byte offset of every element (row by row); ``bpp`` is bytes per element."""
    gobs_wide = (elements_wide * bpp + 63) // 64
    rows_per_block = 8 * block_height
    out = []
    for y in range(elements_high):
        row_base = (y // rows_per_block) * 512 * block_height * gobs_wide + (y % rows_per_block // 8) * 512
        row_in_gob = ((y % 8) // 2) * 64 + (y % 2) * 16
        for x in range(elements_wide):
            xb = x * bpp
            out.append(row_base + (xb // 64) * 512 * block_height + ((xb % 64) // 32) * 256
                       + ((xb % 32) // 16) * 32 + row_in_gob + (xb % 16))
    return tuple(out)
