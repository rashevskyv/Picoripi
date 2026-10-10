"""A font drawn from a grid of cells in one texture image (no glyph table in the data; the game's code
maps a character to its cell and spaces the cells itself), e.g. the HUD and menu atlases of Twin Snakes.

The file is anything ``core.texture_formats`` reads (a TPL, a BTI, ...). The model's one sheet is the
texture image itself, in its colours, so an unedited font packs back to the same bytes and an edited
one is encoded again in the texture's own format. Widths are the cell width (the code's spacing) and
are not stored.

Params: ``texture`` (the texture format, default ``tpl``), ``image`` (index of the image in the file,
default 0), ``cell`` (``[width, height]``), ``chars`` (the characters of the cells, row by row, as a
string or a list; an entry that is not one character ("" for a free cell, a game token) or is "\\0" leaves
its cell without a character, as does a cell past the end) or ``first_code`` (cell i is character ``first_code + i``), optional ``columns`` (default: image width // cell width) and
``texture_params`` (passed to the texture format). Optional ``rows_at`` (``[[x, y], ...]``, one per row):
the rows of cells are at these places in the texture, not on one even grid (``columns`` is then required);
the sheet is the cells laid out as one grid, and packing puts each cell back where it came from.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from core.font_formats import Metadata, Sheets, char_code, map_entries


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _image(data: bytes, params: Dict[str, Any]):
    from core import texture_formats
    fmt = str(params.get("texture") or "tpl")
    return texture_formats.read(fmt, data, params.get("texture_params") or {})[_int(params.get("image", 0))].image


def _rows_at(params: Dict[str, Any]):
    """``rows_at``: where each row of cells starts in the texture, ``[[x, y], ...]`` (a game whose glyph rows
    are separate VRAM pages, not one even grid). None for a plain grid."""
    rows_at = params.get("rows_at")
    if not rows_at:
        return None
    return [(_int(x), _int(y)) for x, y in rows_at]


def _compose(texture, rows_at, width: int, height: int, columns: int):
    """The cells of the rows at ``rows_at`` laid out as one even grid (the editor's sheet)."""
    from PIL import Image
    sheet = Image.new("RGBA", (columns * width, len(rows_at) * height))
    for r, (x0, y0) in enumerate(rows_at):
        for c in range(columns):
            cell = texture.crop((x0 + c * width, y0, x0 + (c + 1) * width, y0 + height))
            sheet.paste(cell, (c * width, r * height))
    return sheet


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    width, height = (_int(v) for v in params["cell"])
    rows_at = _rows_at(params)
    if rows_at:
        texture = _image(data, params).convert("RGBA")
        columns = _int(params["columns"])
        sheet = _compose(texture, rows_at, width, height, columns)
        rows = len(rows_at)
    else:
        sheet = _image(data, params).convert("RGBA")
        columns = _int(params.get("columns") or sheet.width // width)
        rows = sheet.height // height
    count = columns * rows
    if "chars" in params:
        chars = params["chars"]
        chars = list(chars if isinstance(chars, list) else str(chars))[:count]
    else:
        chars = [chr(_int(params.get("first_code", 0x20)) + glyph) for glyph in range(count)]
    pairs = [(char_code(char), glyph) for glyph, char in enumerate(chars) if len(char) == 1 and char != "\0"]
    metadata = {
        "header": {"signature": "Texture grid font", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": height, "descent": 0, "width": width, "leading": height,
                  "fallback_code": pairs[0][0] if pairs else 0x20, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": width, "cell_height": height,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": rows, "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": count,
                  "packets": [{"kerning": 0, "width": width} for _ in range(count)]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    """``original`` with the sheet written back into its image (the same bytes when nothing changed)."""
    from core import texture_formats
    current = _image(original, params).convert("RGBA")
    sheet = sheets[0].convert("RGBA")
    width, height = (_int(v) for v in params["cell"])
    rows_at = _rows_at(params)
    if rows_at:
        columns = _int(params["columns"])
        expected = (columns * width, len(rows_at) * height)
        if sheet.size != expected:
            raise ValueError(f"The sheet is {sheet.width}x{sheet.height}, the cells need {expected[0]}x{expected[1]}")
        for r, (x0, y0) in enumerate(rows_at):
            for c in range(columns):
                cell = sheet.crop((c * width, r * height, (c + 1) * width, (r + 1) * height))
                current.paste(cell, (x0 + c * width, y0))
        sheet = current
    elif sheet.size != current.size:
        raise ValueError(f"The sheet is {sheet.width}x{sheet.height}, the texture {current.width}x{current.height}")
    fmt = str(params.get("texture") or "tpl")
    return texture_formats.write(fmt, original, {_int(params.get("image", 0)): sheet},
                                 params.get("texture_params") or {})
