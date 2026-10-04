"""BC7 encoding in mode 6: one colour line per 4x4 block, RGBA endpoints of 7 bits + a shared bit, 4-bit
weights. The line follows the block's main direction (power iteration on the covariance), then two rounds of
least-squares refinement; each endpoint takes the shared bit that suits it best, and a fully
transparent texel only has to get its alpha right. Mode 6 is the usual choice for smooth or two-colour
blocks such as lettering; decoding (all modes) is Pillow's.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

from PIL import Image

_WEIGHTS = (0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64)


def _axis(pixels: Sequence[Sequence[int]], mean: Sequence[float]) -> List[float]:
    cov = [[0.0] * 4 for _ in range(4)]
    for p in pixels:
        d = [p[c] - mean[c] for c in range(4)]
        for i in range(4):
            for j in range(4):
                cov[i][j] += d[i] * d[j]
    axis = [1.0, 1.0, 1.0, 1.0]
    for _ in range(8):
        axis = [sum(cov[i][j] * axis[j] for j in range(4)) for i in range(4)]
        norm = max(abs(a) for a in axis)
        if norm < 1e-9:
            return [0.0, 0.0, 0.0, 0.0]
        axis = [a / norm for a in axis]
    return axis


def _quantize(value: Sequence[float]) -> Tuple[List[int], int]:
    """7-bit channels + shared bit closest to an RGBA colour."""
    best = None
    for p in (0, 1):
        q = [min(127, max(0, round((v - p) / 2))) for v in value]
        error = sum(((c << 1 | p) - v) ** 2 for c, v in zip(q, value))
        if best is None or error < best[0]:
            best = (error, q, p)
    return best[1], best[2]


def _fit(pixels: Sequence[Sequence[int]], q0, p0, q1, p1) -> Tuple[int, List[int]]:
    """``(error, indices)`` of the texels against the line between two quantized endpoints.

    A fully transparent texel only needs its alpha right."""
    e0, e1 = [c << 1 | p0 for c in q0], [c << 1 | p1 for c in q1]
    palette = [[((64 - w) * a + w * b + 32) >> 6 for a, b in zip(e0, e1)] for w in _WEIGHTS]
    total, indices = 0, []
    for p in pixels:
        if p[3] == 0:
            costs = [colour[3] ** 2 for colour in palette]
        else:
            costs = [(p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2 + (p[3] - c[3]) ** 2
                     for c in palette]
        low = min(costs)
        total += low
        indices.append(costs.index(low))
    return total, indices


def _refine(pixels: Sequence[Sequence[int]], indices: Sequence[int]):
    """Least-squares endpoints for fixed weights (None when the weights do not span a line)."""
    a = b = c = 0.0
    sums0, sums1 = [0.0] * 4, [0.0] * 4
    for p, index in zip(pixels, indices):
        w = _WEIGHTS[index] / 64
        a += (1 - w) ** 2
        b += (1 - w) * w
        c += w * w
        for ch in range(4):
            sums0[ch] += (1 - w) * p[ch]
            sums1[ch] += w * p[ch]
    det = a * c - b * b
    if abs(det) < 1e-9:
        return None
    return ([(c * s0 - b * s1) / det for s0, s1 in zip(sums0, sums1)],
            [(a * s1 - b * s0) / det for s0, s1 in zip(sums0, sums1)])


def encode_block(pixels: Sequence[Sequence[int]]) -> bytes:
    """16 RGBA texels (row by row) -> one 16-byte BC7 block."""
    opaque = [p for p in pixels if p[3]] or pixels
    mean = [sum(p[c] for p in opaque) / len(opaque) for c in range(4)]
    axis = _axis(opaque, mean)
    projections = [sum((p[c] - mean[c]) * axis[c] for c in range(4)) for p in opaque]
    norm = sum(a * a for a in axis) or 1.0
    ends = [[mean[c] + t * axis[c] / norm for c in range(4)] for t in (min(projections), max(projections))]
    if any(p[3] == 0 for p in pixels):
        ends[0][3] = 0
    (q0, p0), (q1, p1) = _quantize(ends[0]), _quantize(ends[1])
    error, indices = _fit(pixels, q0, p0, q1, p1)
    for _round in range(2):
        refined = _refine(pixels, indices)
        if refined is None:
            break
        r0, s0 = _quantize([min(255.0, max(0.0, v)) for v in refined[0]])
        r1, s1 = _quantize([min(255.0, max(0.0, v)) for v in refined[1]])
        new_error, new_indices = _fit(pixels, r0, s0, r1, s1)
        if new_error >= error:
            break
        error, indices, q0, p0, q1, p1 = new_error, new_indices, r0, s0, r1, s1
    if indices[0] >= 8:            # the first index has an implied top bit of 0: swap the line
        q0, q1, p0, p1 = q1, q0, p1, p0
        indices = [15 - i for i in indices]
    bits, at = 1 << 6, 7
    for channel in range(4):
        for q in (q0, q1):
            bits |= q[channel] << at
            at += 7
    bits |= p0 << at | p1 << (at + 1)
    at += 2
    for n, index in enumerate(indices):
        bits |= index << at
        at += 3 if n == 0 else 4
    return bits.to_bytes(16, "little")


def encode(image: Image.Image) -> bytes:
    """BC7 blocks of an RGBA image (size a multiple of 4), row by row."""
    width, height = image.size
    px = image.convert("RGBA").tobytes()
    out = bytearray()
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            block = [px[((by + y) * width + bx + x) * 4:((by + y) * width + bx + x) * 4 + 4]
                     for y in range(4) for x in range(4)]
            out += encode_block(block)
    return bytes(out)
