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
    from core.font_formats import (bcfnt, bffnt, bfotf, eternal_darkness, fragile_dreams, fntg, cv_gba, cv_nds, ffta2, g1n, g1t, g4font, gba_tiles, gzf, lunar, m2, mgs,
                                   mgs1,
                                   mgs1_hd, n64, nftr, pgf, policenauts, qbf, retro_font, retro_font_gx, texture_grid,
                                   tmp_sdf, twewy,
                                   vagrant,
                                   xf, zelda3)
    return {"n64": n64, "g1t": g1t, "g1n": g1n, "bffnt": bffnt, "bcfnt": bcfnt, "qbf": qbf, "gzf": gzf,
            "bfotf": bfotf, "mgs": mgs, "bffnt_wiiu": bcfnt, "brfnt": bcfnt, "nftr": nftr, "xf": xf,
            "vagrant": vagrant, "gba_tiles": gba_tiles, "retro_font": retro_font,
            "retro_font_gx": retro_font_gx, "pgf": pgf, "twewy": twewy, "policenauts": policenauts,
            "texture_grid": texture_grid, "zelda3": zelda3, "mgs1": mgs1, "mgs1_hd": mgs1_hd, "m2": m2,
            "lunar": lunar, "g4font": g4font, "eternal_darkness": eternal_darkness, "fragile_dreams": fragile_dreams, "fntg": fntg, "cv_gba": cv_gba, "cv_nds": cv_nds, "ffta2": ffta2, "tmp_sdf": tmp_sdf}


def adds_glyphs(fmt: str) -> bool:
    """The format maps Unicode characters to glyphs and saves new mappings (``ADDS_GLYPHS``): a letter typed
    into an empty cell becomes that real character, not a translation-map slot (BFFNT, 3DS, Wii U and Wii fonts,
    G1N, NFTR)."""
    return bool(getattr(_backends().get(fmt), "ADDS_GLYPHS", False))


def is_supported(fmt: str) -> bool:
    """A format this package packs (``bfn`` is handled by the BFN engine)."""
    return fmt in _backends()


def detect(data: bytes) -> Optional[str]:
    """The format of a font file by its magic: ``bfn``, ``g1t``, ``g1n``, ``bffnt`` (Switch), ``bcfnt`` (3DS
    BCFNT or BFFNT), ``qbf``, ``gzf``, ``bfotf`` (Switch scalable font), ``bffnt_wiiu``
    (Wii U BFFNT, big endian), ``brfnt`` (Wii RFNT), ``nftr`` (DS NFTR), ``xf`` (Level-5 XPCK font),
    ``vagrant`` (Vagrant Story), ``retro_font`` (Metroid Prime 4 FONT bundle), ``pgf`` (PSP), ``fntg`` (EA FntG) or None."""
    from core.font_formats import bfotf
    head = bytes(data[:8])
    if head[4:8] == b"PGF0":
        return "pgf"
    if head[:4] == b"RFRM" and bytes(data[20:24]) == b"FONT":
        return "retro_font"
    if head[:4] in (b"QBF1", b"GZFX"):
        return head[:3].decode("ascii").lower()
    if head[:6] == b"RTFN\xff\xfe":
        return "nftr"
    if head[:6] == b"FFNT\xfe\xff":
        return "bffnt_wiiu"
    if head[:6] == b"RFNT\xfe\xff":
        return "brfnt"
    if head[:4] in (b"FFNT", b"CFNT") and head[4:6] in (b"\xff\xfe", b"\xfe\xff"):
        from core.font_formats.bcfnt import is_ctr_font
        return "bcfnt" if is_ctr_font(data) else "bffnt"
    if head[:4] in (b"FONT", b"FFNT"):
        return "bfn"
    if head[:4] == b"FntG":
        return "fntg"
    if head[:4] == b"GT1G":
        return "g1t"
    if head[:4] == b"VSFN":
        return "vagrant"
    if head[:4] == b"XPCK":
        from core.font_formats import xf
        return "xf" if xf.is_xf(bytes(data)) else None
    if head[:3] == b"PSB" and head[3:4] == bytes(1):
        from core.font_formats import m2
        return "m2" if m2.is_m2_font(bytes(data)) else None
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


# -- lining new letters up with the font's own ---------------------------------------
# A letter drawn or rendered into a font must stand where the font's Latin letters stand: its baseline row,
# cap height and x-height are read from their ink (the font header's ascent is not always that row).

INK_THRESHOLD = 100
DESCENDERS = set("руф")                  # letters whose tail goes below the baseline as p / y do
SHORT_TAILS = set("дцщДЦЩ")             # letters with a short tail: they line up by their top instead


def _ink_box(cell: Image.Image):
    return coverage(cell).point(lambda value: 255 if value > INK_THRESHOLD else 0).getbbox()


def latin_metrics(cell_of) -> Optional[Dict[str, int]]:
    """``{"baseline", "cap_top", "x_top", "descender"}`` rows measured on the font's Latin letters.

    ``cell_of(char)`` gives the RGBA cell of a character or None. The baseline is the ink bottom of H (else
    Н, I), the cap top H's top, the x-height top that of x (else х, o, о), the descender p's bottom (else y).
    None when the font has none of the capitals.
    """
    def box(chars):
        for char in chars:
            cell = cell_of(char)
            found = _ink_box(cell) if cell is not None else None
            if found:
                return found
        return None

    capital, small, tail = box("HНIE"), box("xхoо"), box("pрyу")
    if capital is None:
        return None
    baseline = capital[3]
    return {"baseline": baseline, "cap_top": capital[1], "x_top": small[1] if small else capital[1],
            "descender": tail[3] if tail else baseline}


def align_to_latin(cell: Image.Image, char: str, metrics: Dict[str, int]) -> Image.Image:
    """``cell`` moved up or down so ``char`` stands like the font's Latin letters (``latin_metrics``).

    A letter (punctuation is left as it is) rests its ink bottom on the baseline row; р у ф hang down to the descender row like p / y; the
    short tails of д ц щ (Д Ц Щ) hang below, so those line up by their top with the x-height (cap height).
    """
    found = _ink_box(cell)
    if not found or not metrics or not char.isalpha():      # punctuation (’ , .) keeps its own height
        return cell
    if char in SHORT_TAILS:
        shift = (metrics["cap_top"] if char.isupper() else metrics["x_top"]) - found[1]
    elif char in DESCENDERS:
        shift = metrics["descender"] - found[3]
    else:
        shift = metrics["baseline"] - found[3]
    if not shift:
        return cell
    moved = Image.new(cell.mode, cell.size)
    moved.paste(cell, (0, shift))
    return moved
