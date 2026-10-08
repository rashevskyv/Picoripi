"""A font drawn from a grid of cells in one texture image (no glyph table in the data; the game's code
maps a character to its cell and spaces the cells itself), e.g. the HUD and menu atlases of Twin Snakes.

The file is anything ``core.texture_formats`` reads (a TPL, a BTI, ...). The model's one sheet is the
texture image itself, in its colours, so an unedited font packs back to the same bytes and an edited
one is encoded again in the texture's own format. Widths are the cell width (the code's spacing) and
are not stored.

Params: ``texture`` (the texture format, default ``tpl``), ``image`` (index of the image in the file,
default 0), ``cell`` (``[width, height]``), ``chars`` (the characters of the cells, row by row, as a
string or a list whose empty entries are cells without a character; a cell past the end has no character) or ``first_code`` (cell i is character ``first_code + i``), optional ``columns`` (default: image width // cell width) and
``texture_params`` (passed to the texture format).
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


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    sheet = _image(data, params).convert("RGBA")
    width, height = (_int(v) for v in params["cell"])
    columns = _int(params.get("columns") or sheet.width // width)
    rows = sheet.height // height
    count = columns * rows
    if "chars" in params:
        chars = params["chars"]
        chars = list(chars if isinstance(chars, list) else str(chars))[:count]
    else:
        chars = [chr(_int(params.get("first_code", 0x20)) + glyph) for glyph in range(count)]
    pairs = [(char_code(char), glyph) for glyph, char in enumerate(chars) if len(char) == 1]
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
    current = _image(original, params)
    sheet = sheets[0].convert("RGBA")
    if sheet.size != current.size:
        raise ValueError(f"The sheet is {sheet.width}x{sheet.height}, the texture {current.width}x{current.height}")
    fmt = str(params.get("texture") or "tpl")
    return texture_formats.write(fmt, original, {_int(params.get("image", 0)): sheet},
                                 params.get("texture_params") or {})
