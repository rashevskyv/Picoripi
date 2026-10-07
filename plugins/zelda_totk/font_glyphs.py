"""Add the Ukrainian letters a TotK font lacks (І і Ї ї Є є Ґ ґ), drawn from the font's own glyphs. Offline tool.

    python -m plugins.zelda_totk.font_glyphs <romfs>/Font/Font.Nin_NX_NVN.bfarc.zs <translation>/Font/Font.Nin_NX_NVN.bfarc.zs

TotK's fonts are scrambled OpenType/CFF (``core.font_formats.bfotf``). For every font in the archive that
has Latin and Russian Cyrillic but misses a Ukrainian letter:

- І і Ї ї map to the font's own I i Ï ï glyphs (a character map entry, no new outline);
- Є є are the font's Э э mirrored left to right (the same strokes, opening the other way);
- Ґ ґ are Г г with an upturn: a stroke as thick as the letter's stem, standing on the right end of the bar.

New outlines are appended as glyphs (``core.font_formats.cff`` rebuilds the CFF: CharStrings, charset, FDSelect, strings; the
other tables get their glyph count, metrics and character map). The result is a first draft to touch
up by hand in a font editor; untouched fonts keep their bytes.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import List, Tuple

from core.containers import sarc
from core.font_formats import bfotf
from core.font_formats.cff import Cff, Contour, Point, charstring, outline, rebuild_font
from utils.atomic_io import atomic_write_bytes

# letter -> (how, source letter)
UKRAINIAN = {"І": ("map", "I"), "і": ("map", "i"), "Ї": ("map", "Ï"), "ї": ("map", "ï"),
             "Є": ("mirror", "Э"), "є": ("mirror", "э"), "Ґ": ("upturn", "Г"), "ґ": ("upturn", "г")}
UPTURN_HEIGHT = 0.2      # of the letter's height


# ---------------------------------------------------------------- shapes

def _points(contour: Contour) -> List[Point]:
    """A contour flattened to points (curves in 12 steps), for measuring."""
    pts: List[Point] = []
    for segment in contour:
        if segment[0] in ("M", "L"):
            pts.append(segment[1])
        else:
            p0 = pts[-1]
            p1, p2, p3 = segment[1:]
            for step in range(1, 13):
                t = step / 12
                u = 1 - t
                pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return pts


def _area(points: List[Point]) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1])) / 2


def mirrored(width: float, contours: List[Contour]) -> List[Contour]:
    """The contours flipped left to right inside the advance width."""
    def flip(p):
        return (width - p[0], p[1])
    return [[(segment[0], *[flip(p) for p in segment[1:]]) for segment in contour] for contour in contours]


def with_upturn(contours: List[Contour]) -> List[Contour]:
    """Г / г with Ґ's upturn: a stem-thick stroke rising from the right end of the top bar.

    The stem is measured where a horizontal line through the middle of the letter crosses it; the stroke
    winds the same way as the outer contour, so the two merge (non-zero fill).
    """
    flat = [_points(contour) for contour in contours]
    xs = [p[0] for pts in flat for p in pts]
    ys = [p[1] for pts in flat for p in pts]
    top, bottom, right = max(ys), min(ys), max(xs)
    middle = (top + bottom) / 2
    crossings = []
    for pts in flat:
        for a, b in zip(pts, pts[1:] + pts[:1]):
            if (a[1] - middle) * (b[1] - middle) < 0:
                crossings.append(a[0] + (middle - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
    crossings.sort()
    stem = crossings[1] - crossings[0] if len(crossings) >= 2 else (right - min(xs)) * 0.15
    rise = math.ceil((top - bottom) * UPTURN_HEIGHT)
    left, base = round(right - stem), round(top - stem / 2)
    corners = [(left, base), (right, base), (right, top + rise), (left, top + rise)]
    outer = max(flat, key=lambda pts: abs(_area(pts)))
    if (_area(outer) > 0) != (_area(corners) > 0):
        corners.reverse()
    stroke: Contour = [("M", corners[0])] + [("L", p) for p in corners[1:]]
    return contours + [stroke]


def add_ukrainian(font: bytes) -> Tuple[bytes, List[str]]:
    """``(font, letters added)``; the font unchanged when it lacks Cyrillic or has every letter."""
    ot = bfotf.OpenType(font)
    mapping = ot.cmap()
    cff = Cff(font[ot.table("CFF "):ot.table("CFF ") + ot.tables["CFF "][1]])
    # A letter mapped to an empty glyph counts as missing (Nin-ZeldaGlyphs-v2-Deco maps Є to a blank).
    missing = [ch for ch in UKRAINIAN if ord(ch) not in mapping or not outline(cff, mapping[ord(ch)])[1]]
    if not missing or any(ord(UKRAINIAN[ch][1]) not in mapping for ch in missing):
        return font, []
    metrics: List[Tuple[int, int]] = []
    for letter in missing:
        how, source = UKRAINIAN[letter]
        glyph = mapping[ord(source)]
        if how == "map":
            mapping[ord(letter)] = glyph
            continue
        width, contours = outline(cff, glyph)
        contours = mirrored(width, contours) if how == "mirror" else with_upturn(contours)
        new = cff.add_glyph(charstring(width, cff.widths_x(glyph), contours), f"uni{ord(letter):04X}", glyph)
        mapping[ord(letter)] = new
        xs = [p[0] for contour in contours for p in _points(contour)]
        metrics.append((round(width), round(min(xs)) if xs else 0))
    return rebuild_font(font, cff, mapping, metrics), missing


def patch_archive(archive: bytes, log=print) -> bytes:
    """A font archive (``.bfarc`` / ``.bfarc.zs``) with the Ukrainian letters added to every font that lacks them."""
    container = sarc.SarcContainer(archive)
    for name in container.list_files():
        data = container.read_file(name)
        if not bfotf.is_bfotf(data):
            continue
        plain, key = bfotf.decrypt(data)
        patched, added = add_ukrainian(plain)
        if added:
            container.write_file(name, bfotf.encrypt(patched, key))
            log(f"{name}: added {''.join(added)}")
    return container.pack()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("archive", type=Path, help="romfs/Font/Font.Nin_NX_NVN.bfarc.zs")
    parser.add_argument("output", type=Path, help="where to write the patched archive")
    parser.add_argument("--dictionaries", type=Path, help="folder with Pack/ZsDic.pack.zs (default: near the font)")
    args = parser.parse_args(argv)
    sarc.dictionary_dirs = lambda: [args.dictionaries or args.archive.parent]
    atomic_write_bytes(args.output, patch_archive(args.archive.read_bytes()))
    print(f"{args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
