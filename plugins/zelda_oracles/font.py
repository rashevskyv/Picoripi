"""Oracle of Ages and Oracle of Seasons message font: 256 glyph cells, 8 x 16 pixels, 1 bit per pixel.

Layout (checked against the disassembly's gfx_font.png): cell n is 16 bytes at ``font_offset + 16 * n``.
Its first 8 bytes are the top 8x8 tile, the last 8 bytes the bottom tile; bit 7 is the left pixel,
and a set bit is ink. In the image, cell n sits at column ``n % 16`` and block row ``n // 16``
(16 rows of 16 pixels), with the top tile on the upper half.

The PNG uses palette index 0 for background and 3 for ink, so an image editor shows black letters
on white. Importing reads ink as palette index 3 or as a dark pixel.
"""
from __future__ import annotations

from typing import List

from .rom import GameLayout

CELLS = 256
CELL_BYTES = 16
COLUMNS = 16
IMAGE_WIDTH = 8 * COLUMNS          # 128 pixels
IMAGE_HEIGHT = 16 * (CELLS // COLUMNS)  # 256 pixels
FONT_BYTES = CELLS * CELL_BYTES

INK = 3
PAPER = 0


class FontError(ValueError):
    """Font data that cannot be read or written."""


def cell_origin(cell: int) -> tuple:
    """Image position (x, y) of the top-left pixel of a glyph cell."""
    return (8 * (cell % COLUMNS), 16 * (cell // COLUMNS))


def font_slice(rom: bytes, layout: GameLayout) -> bytes:
    return bytes(rom[layout.font_offset:layout.font_offset + FONT_BYTES])


def glyph_rows(glyph: bytes) -> List[List[int]]:
    """16 rows of 8 pixels (1 = ink) for one cell."""
    if len(glyph) != CELL_BYTES:
        raise FontError(f"a glyph is {CELL_BYTES} bytes, got {len(glyph)}")
    return [[(glyph[row] >> (7 - x)) & 1 for x in range(8)] for row in range(16)]


def rows_to_glyph(rows: List[List[int]]) -> bytes:
    if len(rows) != 16 or any(len(r) != 8 for r in rows):
        raise FontError("a glyph is 16 rows of 8 pixels")
    out = bytearray(CELL_BYTES)
    for row, pixels in enumerate(rows):
        value = 0
        for x, pixel in enumerate(pixels):
            value |= (1 if pixel else 0) << (7 - x)
        # Rows 0-7 are the top tile, rows 8-15 the bottom tile; each tile is 8 bytes.
        out[row] = value
    return bytes(out)


def cell_bytes_to_bits(font: bytes, cell: int) -> bytes:
    return font[cell * CELL_BYTES:(cell + 1) * CELL_BYTES]


def font_to_grid(font: bytes) -> List[List[int]]:
    """The whole font as a grid of 256 rows and 128 columns, 1 = ink, in image layout."""
    if len(font) != FONT_BYTES:
        raise FontError(f"the font is {FONT_BYTES} bytes, got {len(font)}")
    grid = [[0] * IMAGE_WIDTH for _ in range(IMAGE_HEIGHT)]
    for cell in range(CELLS):
        x0, y0 = cell_origin(cell)
        rows = glyph_rows(cell_bytes_to_bits(font, cell))
        for dy, pixels in enumerate(rows):
            y = y0 + dy
            for dx, pixel in enumerate(pixels):
                grid[y][x0 + dx] = pixel
    return grid


def grid_to_font(grid: List[List[int]]) -> bytes:
    """Inverse of ``font_to_grid``."""
    if len(grid) != IMAGE_HEIGHT or any(len(row) != IMAGE_WIDTH for row in grid):
        raise FontError(f"the font image must be {IMAGE_WIDTH} x {IMAGE_HEIGHT} pixels")
    out = bytearray(FONT_BYTES)
    for cell in range(CELLS):
        x0, y0 = cell_origin(cell)
        rows = [[grid[y0 + dy][x0 + dx] for dx in range(8)] for dy in range(16)]
        out[cell * CELL_BYTES:(cell + 1) * CELL_BYTES] = rows_to_glyph(rows)
    return bytes(out)


def write_font(rom: bytearray, layout: GameLayout, font: bytes) -> None:
    """Write 4096 bytes of font data over the message font of the ROM."""
    if len(font) != FONT_BYTES:
        raise FontError("font data must be 4096 bytes")
    rom[layout.font_offset:layout.font_offset + FONT_BYTES] = font


def export_png(font: bytes, path: str) -> None:
    from PIL import Image

    image = Image.new("P", (IMAGE_WIDTH, IMAGE_HEIGHT), PAPER)
    image.putpalette([255, 255, 255, 170, 170, 170, 85, 85, 85, 0, 0, 0] + [0] * (256 - 4) * 3)
    grid = font_to_grid(font)
    image.putdata([INK if value else PAPER for row in grid for value in row])
    image.save(path, "PNG", optimize=True)


def import_png(path: str) -> bytes:
    from PIL import Image

    with Image.open(path) as source:
        image = source.convert("RGB")
    if image.size != (IMAGE_WIDTH, IMAGE_HEIGHT):
        raise FontError(f"the font image must be {IMAGE_WIDTH} x {IMAGE_HEIGHT} pixels, got {image.size}")
    pixels = image.load()
    grid = [[1 if sum(pixels[x, y]) < 3 * 128 else 0 for x in range(IMAGE_WIDTH)] for y in range(IMAGE_HEIGHT)]
    return grid_to_font(grid)
