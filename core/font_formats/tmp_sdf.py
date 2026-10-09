"""TextMesh Pro SDF font assets (Unity), as Pokémon Brilliant Diamond / Shining Pearl keeps them.

The font is two files (a font source with ``companion``): the font asset's type tree in JSON (``m_GlyphTable``:
each glyph's metrics and its rectangle in the atlas, ``m_CharacterTable``: Unicode -> glyph, ``m_AtlasPadding``)
and the atlas as a grey PNG (the signed distance field; Unity's Alpha8 texture, rows top-down as the PNG has
them, while TMP counts the rectangle's ``y`` from the bottom).

Model: one cell per glyph, 32 to a row, holding the glyph's rectangle grown by the padding (the distance field
around the letter). A grey value is shown as grey (``grey_sheet``); the game draws the edge of a letter where the
field crosses 128, so ink painted at full white is a solid shape in the game. Widths are the horizontal advances
rounded to whole units. Packing an unedited model gives both files back unchanged; a redrawn cell is written into
its atlas rectangle, a changed width becomes ``m_HorizontalAdvance``. New characters are not added: that needs a
new rectangle in ``m_FreeGlyphRects`` and new glyph and character entries, rendered by an SDF generator.
"""
from __future__ import annotations

import io
import json
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries
from core.font_formats.sources import join_pair, split_pair

_COLUMNS = 32


def dump(tree: Dict[str, Any]) -> bytes:
    """The JSON file as the workspace scripts write it."""
    return (json.dumps(tree, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def _read(data: bytes) -> Tuple[Dict[str, Any], Image.Image]:
    tree_bytes, atlas_bytes = split_pair(data)
    return json.loads(tree_bytes.decode("utf-8")), Image.open(io.BytesIO(atlas_bytes)).convert("L")


def _boxes(tree: Dict[str, Any], atlas: Image.Image) -> List[Tuple[int, int, int, int]]:
    """Atlas box (left, top, right, bottom; top-down rows) of every glyph, padding included."""
    pad = int(tree.get("m_AtlasPadding") or 0)
    out = []
    for glyph in tree["m_GlyphTable"]:
        rect = glyph["m_GlyphRect"]
        top = atlas.height - rect["m_Y"] - rect["m_Height"]
        out.append((max(0, rect["m_X"] - pad), max(0, top - pad),
                    min(atlas.width, rect["m_X"] + rect["m_Width"] + pad),
                    min(atlas.height, top + rect["m_Height"] + pad)))
    return out


def _grid(boxes):
    cell_w = max([right - left for left, _t, right, _b in boxes] or [1])
    cell_h = max([bottom - top for _l, top, _r, bottom in boxes] or [1])
    rows = max(1, -(-len(boxes) // _COLUMNS))
    return cell_w, cell_h, rows


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    tree, atlas = _read(data)
    boxes = _boxes(tree, atlas)
    cell_w, cell_h, rows = _grid(boxes)
    ink = Image.new("L", (_COLUMNS * cell_w, rows * cell_h), 0)
    for index, box in enumerate(boxes):
        row, column = divmod(index, _COLUMNS)
        ink.paste(atlas.crop(box), (column * cell_w, row * cell_h))
    cell_of = {glyph["m_Index"]: index for index, glyph in enumerate(tree["m_GlyphTable"])}
    pairs = [(char_code(chr(char["m_Unicode"])), cell_of[char["m_GlyphIndex"]])
             for char in tree["m_CharacterTable"] if char["m_GlyphIndex"] in cell_of]
    face = tree.get("m_FaceInfo") or {}
    packets = [{"kerning": 0, "width": round(glyph["m_Metrics"]["m_HorizontalAdvance"])}
               for glyph in tree["m_GlyphTable"]]
    metadata = {
        "header": {"signature": "TextMesh Pro SDF font", "textures_editable": True,
                   "name": tree.get("m_Name", ""), "point_size": face.get("m_PointSize", 0)},
        "INF1": [{"encoding": 1, "ascent": round(face.get("m_AscentLine", cell_h)),
                  "descent": round(-face.get("m_DescentLine", 0)), "width": cell_w,
                  "leading": round(face.get("m_LineHeight", cell_h)), "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": len(boxes) - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "glyph_horizontal_count": _COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": _COLUMNS * cell_w, "texture_height": rows * cell_h}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": len(boxes), "packets": packets}],
    }
    return metadata, [grey_sheet(ink)]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    """``original`` when nothing changed; else the redrawn cells in the atlas and the changed advances."""
    tree, atlas = _read(original)
    again, again_sheets = extract(original, params)
    boxes = _boxes(tree, atlas)
    cell_w, cell_h, _rows = _grid(boxes)
    drawn = sheets[0].convert("RGBA") if sheets else again_sheets[0]
    old = again_sheets[0]
    atlas_changed = False
    for index, (left, top, right, bottom) in enumerate(boxes):
        row, column = divmod(index, _COLUMNS)
        cell = (column * cell_w, row * cell_h, column * cell_w + right - left, row * cell_h + bottom - top)
        if drawn.crop(cell).tobytes() != old.crop(cell).tobytes():
            atlas.paste(coverage(drawn.crop(cell)), (left, top))
            atlas_changed = True
    old_widths = [p["width"] for p in again["WID1"][0]["packets"]]
    new_widths = [p["width"] for p in metadata["WID1"][0]["packets"]]
    tree_changed = False
    for glyph, old_width, new_width in zip(tree["m_GlyphTable"], old_widths, new_widths):
        if old_width != new_width:
            glyph["m_Metrics"]["m_HorizontalAdvance"] = float(new_width)
            tree_changed = True
    if not atlas_changed and not tree_changed:
        return bytes(original)
    tree_bytes, atlas_bytes = split_pair(original)
    if atlas_changed:
        out = io.BytesIO()
        atlas.save(out, "PNG")
        atlas_bytes = out.getvalue()
    return join_pair(dump(tree) if tree_changed else tree_bytes, atlas_bytes)
