"""Bitmap fonts of several games as one editable model, with one backend per file format.

The model is what the font editor works on (its extracted folder): ``metadata`` and one RGBA
sheet image (PIL) per texture page. ``metadata`` keeps the section names of the BFN format the
editor was built for, whatever the file is:

- ``header``: ``format`` (backend id) and ``signature``;
- ``INF1``: ``[{ascent, descent, width (default advance), leading, fallback_code, encoding}]``;
- ``GLY1``: ``[{start_glyph, end_glyph, cell_width, cell_height, glyph_horizontal_count,
  glyph_vertical_count, texture_width, texture_height, ...}]`` -- glyph ``i`` is cell ``i`` of the
  grid, row by row, sheet after sheet;
- ``MAP1``: ``[{mapping_type 3, entries: codes + glyph indices}]`` -- character code -> glyph; a code
  below 256 is a cp1252 byte, any other a Unicode code point (``char_code``/``code_char``);
- ``WID1``: ``[{first_code_included 0, packets: [{kerning, width}] per glyph}]`` -- the glyph is drawn
  at ``pen - kerning`` and the pen advances by ``width``.

A backend module has ``extract(data, params) -> (metadata, sheets)`` and
``pack(metadata, sheets, original, params) -> bytes``; ``params`` are the game's constants (the
plugin's font source, see ``core.font_formats.sources``). Packing an unedited model gives the
original bytes back. BFN itself stays with ``tools/bfn_editor/bfn_engine.py``.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

Metadata = Dict[str, Any]
Sheets = List[Image.Image]


def _backends() -> Dict[str, Any]:
    from core.font_formats import bcfnt, bffnt, bfotf, g1n, g1t, gzf, n64, qbf
    return {"n64": n64, "g1t": g1t, "g1n": g1n, "bffnt": bffnt, "bcfnt": bcfnt, "qbf": qbf, "gzf": gzf,
            "bfotf": bfotf}


def adds_glyphs(fmt: str) -> bool:
    """The format maps Unicode characters to glyphs and saves new mappings (``ADDS_GLYPHS``): a letter typed
    into an empty cell becomes that real character, not a translation-map slot (BFFNT, 3DS fonts, G1N)."""
    return bool(getattr(_backends().get(fmt), "ADDS_GLYPHS", False))


def is_supported(fmt: str) -> bool:
    """A format this package packs (``bfn`` is handled by the BFN engine)."""
    return fmt in _backends()


def detect(data: bytes) -> Optional[str]:
    """The format of a font file by its magic: ``bfn``, ``g1t``, ``g1n``, ``bffnt`` (Switch), ``bcfnt`` (3DS
    BCFNT or BFFNT), ``qbf``, ``gzf``, ``bfotf`` (Switch scalable font) or None."""
    from core.font_formats import bfotf
    head = bytes(data[:8])
    if head[:4] in (b"QBF1", b"GZFX"):
        return head[:3].decode("ascii").lower()
    if head[:4] in (b"FFNT", b"CFNT") and head[4:6] in (b"\xff\xfe", b"\xfe\xff"):
        from core.font_formats.bcfnt import is_ctr_font
        return "bcfnt" if is_ctr_font(data) else "bffnt"
    if head[:4] in (b"FONT", b"FFNT"):
        return "bfn"
    if head[:4] == b"GT1G":
        return "g1t"
    if head == b"_N1G0000":
        return "g1n"
    if bfotf.is_bfotf(bytes(data[:16])):
        return "bfotf"
    return None


def extract(fmt: str, data: bytes, params: Optional[Dict[str, Any]] = None) -> Tuple[Metadata, Sheets]:
    """The editable model of a font file."""
    metadata, sheets = _backends()[fmt].extract(bytes(data), dict(params or {}))
    metadata.setdefault("header", {})["format"] = fmt
    return metadata, sheets


def pack(fmt: str, metadata: Metadata, sheets: Sheets, original: bytes,
         params: Optional[Dict[str, Any]] = None) -> bytes:
    """``original`` with the model's glyphs and metrics written into it."""
    return _backends()[fmt].pack(metadata, sheets, bytes(original), dict(params or {}))


def carry_over(fmt: str, edited: bytes, rebuilt: bytes, params: Optional[Dict[str, Any]] = None) -> bytes:
    """``rebuilt`` with the font of ``edited``: for a file the text save rebuilds from its source.

    Returns ``rebuilt`` unchanged when both hold the same font.
    """
    metadata, sheets = extract(fmt, edited, params)
    current, current_sheets = extract(fmt, rebuilt, params)
    if (metadata.get("WID1") == current.get("WID1")
            and [s.tobytes() for s in sheets] == [s.tobytes() for s in current_sheets]):
        return rebuilt
    return pack(fmt, metadata, sheets, rebuilt, params)


def write_folder(folder: str, metadata: Metadata, sheets: Sheets) -> None:
    """The editor's extracted folder: ``data.json`` and ``sheet_<n>.png`` (a temporary folder)."""
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "data.json"), "w", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=1)
    for index, sheet in enumerate(sheets):
        sheet.save(os.path.join(folder, f"sheet_{index}.png"))


# -- characters ----------------------------------------------------------------------


def code_char(code: int) -> str:
    """The character of a model code: a cp1252 byte below 256, else a Unicode code point."""
    if code < 256:
        try:
            return bytes([code]).decode("cp1252")
        except UnicodeDecodeError:
            pass
    return chr(code)


def char_code(char: str) -> int:
    """The model code of a character (the inverse of ``code_char``)."""
    try:
        encoded = char.encode("cp1252")
        if len(encoded) == 1:
            return encoded[0]
    except UnicodeEncodeError:
        pass
    return ord(char)


def char_map(metadata: Metadata) -> Dict[str, int]:
    """``{character: glyph index}`` from MAP1 (types 0, 2 and 3)."""
    result: Dict[str, int] = {}
    for block in metadata.get("MAP1", []):
        kind, first = block.get("mapping_type", 0), block.get("first_char", 0)
        entries = block.get("entries", [])
        if kind == 0:
            for code in range(first, block.get("last_char", first) + 1):
                result.setdefault(code_char(code), code - first)
        elif kind == 2:
            for offset, glyph in enumerate(entries):
                if glyph != 0xFFFF:
                    result.setdefault(code_char(first + offset), glyph)
        elif kind == 3:
            half = len(entries) // 2
            for code, glyph in zip(entries[:half], entries[half:]):
                result.setdefault(code_char(code), glyph)
    return result


def map_entries(pairs: List[Tuple[int, int]]) -> Dict[str, Any]:
    """A MAP1 block of type 3 from ``(code, glyph)`` pairs."""
    pairs = sorted(pairs)
    codes = [code for code, _glyph in pairs]
    return {"mapping_type": 3, "first_char": codes[0] if codes else 0, "last_char": codes[-1] if codes else 0,
            "mapping_entry_count": len(pairs), "entries": codes + [glyph for _code, glyph in pairs]}


def font_map(metadata: Metadata, translation_map: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, int]]:
    """``{character: {"width": advance}}`` -- what the width checks read -- plus the translated
    characters of ``translation_map`` (``{"Ж": "Æ"}``: Ж is drawn with the glyph of Æ)."""
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    first = (metadata.get("WID1") or [{}])[0].get("first_code_included", 0)
    default = (metadata.get("INF1") or [{}])[0].get("width", 0)
    result: Dict[str, Dict[str, int]] = {}
    for char, glyph in char_map(metadata).items():
        index = glyph - first
        result[char] = {"width": int(packets[index]["width"]) if 0 <= index < len(packets) else int(default)}
    for target, slot in (translation_map or {}).items():
        if slot in result and not target.startswith("#g"):
            result[target] = dict(result[slot])
    return result


# -- pixels --------------------------------------------------------------------------


def coverage(sheet: Image.Image) -> Image.Image:
    """One channel of ink from an RGBA sheet: ``min(max(r, g, b), a)``.

    Decoded glyphs are grey with alpha equal to grey; rendered ones are white with alpha as
    coverage; imported ones may be white on black. All three give the ink here.
    """
    from PIL import ImageChops
    red, green, blue, alpha = sheet.convert("RGBA").split()
    return ImageChops.darker(ImageChops.lighter(ImageChops.lighter(red, green), blue), alpha)


def grey_sheet(ink: Image.Image) -> Image.Image:
    """An RGBA sheet from one channel of ink: grey equal to alpha, as the BFN I4 decoder draws it."""
    return Image.merge("RGBA", (ink, ink, ink, ink))
