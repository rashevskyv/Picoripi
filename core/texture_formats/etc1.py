"""ETC1 blocks (Ericsson Texture Compression, as the 3DS uses it): a 64-bit number per 4x4 texels.

Bits 63..32: two base colours (individual mode: 4+4 bits per channel; differential mode: 5 bits and a
3-bit signed delta), a 3-bit modifier table per half, the ``diff`` bit (33) and the ``flip`` bit (32:
halves are top/bottom instead of left/right). Bits 31..0: per texel (``x * 4 + y``) a 2-bit index, high
bits in 31..16, low bits in 15..0; the index picks ``+a, +b, -a, -b`` of the half's table.

The encoder tries both flips and both modes with every table per half and keeps the smallest error.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

RGB = Tuple[int, int, int]

TABLES = ((2, 8), (5, 17), (9, 29), (13, 42), (18, 60), (24, 80), (33, 106), (47, 183))
_MODIFIERS = tuple((a, b, -a, -b) for a, b in TABLES)


def _clamp(value: int) -> int:
    return 0 if value < 0 else 255 if value > 255 else value


def _x5(v: int) -> int:
    return (v << 3) | (v >> 2)


def _signed3(v: int) -> int:
    return v - 8 if v & 4 else v


def _second_half(x: int, y: int, flip: int) -> bool:
    return y >= 2 if flip else x >= 2


def decode_block(value: int) -> List[RGB]:
    """The 16 texels of a block, in ``x * 4 + y`` order."""
    flip, diff = value >> 32 & 1, value >> 33 & 1
    tables = (value >> 37 & 7, value >> 34 & 7)
    if diff:
        first = [value >> shift & 31 for shift in (59, 51, 43)]
        deltas = [_signed3(value >> shift & 7) for shift in (56, 48, 40)]
        bases = ([_x5(c) for c in first], [_x5((c + d) & 31) for c, d in zip(first, deltas)])
    else:
        bases = ([(value >> shift & 15) * 17 for shift in (60, 52, 44)],
                 [(value >> shift & 15) * 17 for shift in (56, 48, 40)])
    out: List[RGB] = []
    for x in range(4):
        for y in range(4):
            i = x * 4 + y
            half = 1 if _second_half(x, y, flip) else 0
            modifier = _MODIFIERS[tables[half]][(value >> (16 + i) & 1) << 1 | (value >> i & 1)]
            r, g, b = bases[half]
            out.append((_clamp(r + modifier), _clamp(g + modifier), _clamp(b + modifier)))
    return out


def _fit(texels: Sequence[RGB], base: Sequence[int]) -> Tuple[int, int, List[int]]:
    """``(error, table, indices)`` of the best table for ``texels`` around ``base``."""
    best = None
    r0, g0, b0 = base
    for table, modifiers in enumerate(_MODIFIERS):
        candidates = [(_clamp(r0 + m), _clamp(g0 + m), _clamp(b0 + m)) for m in modifiers]
        error, indices = 0, []
        for r, g, b in texels:
            costs = [(r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2 for cr, cg, cb in candidates]
            low = min(costs)
            error += low
            indices.append(costs.index(low))
            if best is not None and error >= best[0]:
                break
        else:
            if best is None or error < best[0]:
                best = (error, table, indices)
    return best


def _average(texels: Sequence[RGB]) -> List[float]:
    return [sum(t[c] for t in texels) / len(texels) for c in range(3)]


def encode_block(texels: Sequence[RGB]) -> int:
    """The block for 16 texels in ``x * 4 + y`` order."""
    positions = [(x, y) for x in range(4) for y in range(4)]
    best = None
    for flip in (0, 1):
        halves = ([i for i, (x, y) in enumerate(positions) if not _second_half(x, y, flip)],
                  [i for i, (x, y) in enumerate(positions) if _second_half(x, y, flip)])
        averages = [_average([texels[i] for i in half]) for half in halves]
        # differential: 5-bit bases, the second within -4..3 of the first
        first5 = [min(31, max(0, round(c * 31 / 255))) for c in averages[0]]
        second5 = [min(31, max(0, round(c * 31 / 255))) for c in averages[1]]
        second5 = [f + max(-4, min(3, s - f)) for f, s in zip(first5, second5)]
        individual = [[min(15, max(0, round(c * 15 / 255))) for c in avg] for avg in averages]
        for diff, bases in ((1, ([_x5(c) for c in first5], [_x5(c) for c in second5])),
                            (0, ([c * 17 for c in individual[0]], [c * 17 for c in individual[1]]))):
            fits = [_fit([texels[i] for i in half], base) for half, base in zip(halves, bases)]
            error = fits[0][0] + fits[1][0]
            if best is None or error < best[0]:
                best = (error, flip, diff, fits, halves, first5, second5, individual)
    _error, flip, diff, fits, halves, first5, second5, individual = best
    if diff:
        value = 0
        for shift, f, s in zip((59, 51, 43), first5, second5):
            value |= f << shift | ((s - f) & 7) << (shift - 3)
    else:
        value = 0
        for shift, f, s in zip((60, 52, 44), *individual):
            value |= f << shift | s << (shift - 4)
    value |= fits[0][1] << 37 | fits[1][1] << 34 | diff << 33 | flip << 32
    for half, (_e, _t, indices) in zip(halves, fits):
        for i, index in zip(half, indices):
            value |= (index >> 1) << (16 + i) | (index & 1) << i
    return value
