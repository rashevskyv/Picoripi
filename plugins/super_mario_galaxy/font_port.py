"""Super Mario Galaxy fonts: read the Switch release's fonts and copy existing Cyrillic glyphs into the Wii fonts.

The Switch ``Font.arc`` members are the Wii NW4R font format little-endian (``TNFR``; blocks ``FNIF``, ``PLGT``,
``HDWC``, ``PAMC``), with the same GX sheets (I4 / IA4, tiled as on the Wii) at a larger size. ``as_rfnt`` turns one
into the big-endian ``RFNT`` that ``core.font_formats.bcfnt`` reads.

``port_glyphs`` copies glyphs that a Switch font has and a Wii font lacks (the Ukrainian translation's Cyrillic) into
new cells of the Wii font: each glyph is scaled by the ratio of the two fonts' Latin advances and put on the Wii
baseline; its left offset and advance are scaled the same way. Nothing is drawn: the pixels are the Switch font's.
``ALIASES`` gives a Ukrainian letter the glyph of another character in the same font (і is the Latin i), so it needs
no new cell. The text keeps proper Unicode; ``encode_for_font`` writes a fallback only for a font that lacks a letter
(``FALLBACK``: the Ukrainian Switch mod's own font has no і, ї, є, ґ and draws them at i, ï, э, г).
"""
from __future__ import annotations

import re
import statistics
import struct
from typing import Dict, Iterable, List, Optional, Set, Tuple

from PIL import Image

from core.containers.rarc_container import RarcContainer
from core.font_formats import bcfnt, char_map, code_char, map_entries

FALLBACK = {"і": "i", "І": "I", "ї": "ï", "Ї": "Ï", "є": "э", "Є": "Э", "ґ": "г", "Ґ": "Г"}
ALIASES = {"і": "i", "І": "I", "ї": "ï", "Ї": "Ï"}
# The Ukrainian mod's font draws є at э and Є at Э: those glyphs serve both codes in a ported font.
FROM_MOD = {"є": "э", "Є": "Э"}
CYRILLIC = "".join(chr(code) for code in range(0x401, 0x460))
FONTS = ("messagefont26.brfnt", "menufont64.brfnt", "cinemafont26.brfnt")


# -- the Switch font as an RFNT ---------------------------------------------------------------------------------------

def _swap_fields(out: bytearray, data: bytes, at: int, layout: str) -> None:
    """Rewrite the little-endian fields of ``layout`` at ``at`` as big-endian."""
    struct.pack_into(">" + layout, out, at, *struct.unpack_from("<" + layout, data, at))


def as_rfnt(data: bytes) -> bytes:
    """A Switch ``TNFR`` font as the big-endian ``RFNT`` the Wii reader reads (an ``RFNT`` is returned as it is)."""
    if data[:4] == b"RFNT":
        return bytes(data)
    if data[:4] != b"TNFR" or data[4:6] != b"\xff\xfe":
        raise ValueError("not a little-endian NW4R font (TNFR)")
    out = bytearray(data)
    out[0:4], out[4:6] = b"RFNT", b"\xfe\xff"
    _swap_fields(out, data, 6, "HIHH")
    at, count = struct.unpack_from("<H", data, 0x0C)[0], struct.unpack_from("<H", data, 0x0E)[0]
    for _ in range(count):
        if at + 8 > len(data):
            break
        magic = data[at:at + 4][::-1]
        size = struct.unpack_from("<I", data, at + 4)[0]
        out[at:at + 4] = magic
        _swap_fields(out, data, at + 4, "I")
        body = at + 8
        if magic == b"FINF":
            _swap_fields(out, data, body, "BbHbBBBIIIBBBB")
        elif magic == b"TGLP":
            _swap_fields(out, data, body, "BBbBIHHHHHHI")
        elif magic == b"CWDH":
            _swap_fields(out, data, body, "HHI")
        elif magic == b"CMAP":
            begin, end, method = struct.unpack_from("<HHH", data, body)
            _swap_fields(out, data, body, "HHHHI")
            table = body + 12
            words = {0: 1, 1: end - begin + 1}.get(method)
            if words is None:   # scan list: a count, then (code, glyph) pairs
                words = 1 + 2 * struct.unpack_from("<H", data, table)[0]
            _swap_fields(out, data, table, "H" * words)
        if size < 8:
            break
        at += size
    return bytes(out)


def font_chars(data: bytes) -> Set[str]:
    """The characters a font (TNFR or RFNT) maps."""
    plain = as_rfnt(data)
    info = bcfnt._info(plain)
    return {code_char(code) for code in bcfnt._codes(bcfnt._cmap_blocks(plain, info))}


def archive_font_chars(font_arc: bytes, member: str = FONTS[0]) -> Set[str]:
    return font_chars(RarcContainer(font_arc).read_file(member))


def encode_for_font(text: str, chars: Set[str]) -> str:
    """``text`` with each Ukrainian letter the font lacks written as its ``FALLBACK``."""
    return "".join(FALLBACK[ch] if ch in FALLBACK and ch not in chars else ch for ch in text)


_WORD = re.compile(r"[^\W\d_]+")
_LATIN_UA = {"i": "і", "I": "І", "ï": "ї", "Ï": "Ї"}
_RUSSIAN_UA = {"э": "є", "Э": "Є"}


def _is_cyrillic(ch: str) -> bool:
    return "Ѐ" <= ch <= "ӿ"


def normalize_ukrainian(text: str, tag_re: re.Pattern) -> str:
    """Proper Ukrainian letters in a message written for a font without them: in a word with Cyrillic letters (or a
    lone i / I, the conjunction) Latin i, I, ï, Ï become і, І, ї, Ї, and Russian э, Э become є, Є. A message with no
    Cyrillic and the tags are left as they are."""
    if not any(_is_cyrillic(ch) for ch in text):
        return text

    def word(match: re.Match) -> str:
        found = match.group(0)
        if any(_is_cyrillic(ch) for ch in found) or found in ("i", "I"):
            found = "".join(_LATIN_UA.get(ch, ch) for ch in found)
            found = "".join(_RUSSIAN_UA.get(ch, ch) for ch in found)
        return found
    out, pos = [], 0
    for tag in tag_re.finditer(text):
        out.append(_WORD.sub(word, text[pos:tag.start()]))
        out.append(tag.group(0))
        pos = tag.end()
    out.append(_WORD.sub(word, text[pos:]))
    return "".join(out)


# -- copying glyphs ---------------------------------------------------------------------------------------------------

def _cells(meta: dict, sheets: List[Image.Image]) -> Tuple[int, int, int, int]:
    gly = meta["GLY1"][0]
    return gly["cell_width"], gly["cell_height"], gly["glyph_horizontal_count"], gly["glyph_vertical_count"]


def _cell(sheets: List[Image.Image], meta: dict, glyph: int) -> Image.Image:
    width, height, columns, rows = _cells(meta, sheets)
    sheet, index = divmod(glyph, columns * rows)
    x, y = index % columns * width, index // columns * height
    return sheets[sheet].crop((x, y, x + width, y + height))


def _scale(wii: dict, switch: dict) -> float:
    """The size ratio of two fonts: the median ratio of their Latin letters' advances."""
    wii_map, sw_map = char_map(wii), char_map(switch)
    wii_packets, sw_packets = wii["WID1"][0]["packets"], switch["WID1"][0]["packets"]
    ratios = [wii_packets[wii_map[ch]]["width"] / sw_packets[sw_map[ch]]["width"]
              for ch in "ABCDEFGHKLMNOPRSTUVWXYZabcdeghknopqrsuvwxyz"
              if ch in wii_map and ch in sw_map and sw_packets[sw_map[ch]]["width"]]
    if not ratios:
        raise ValueError("the two fonts share no Latin letters to measure their sizes")
    return statistics.median(ratios)


def port_glyphs(wii_font: bytes, switch_font: bytes, chars: Iterable[str] = CYRILLIC,
                redrawn: Optional[Dict[str, str]] = None) -> Tuple[bytes, Dict[str, str]]:
    """The Wii font with every character of ``chars`` that the Switch font has and the Wii font lacks, plus the
    ``ALIASES`` codes. ``redrawn`` (default ``FROM_MOD``) names the Switch glyphs that show another letter than their
    code: that glyph is copied to the letter it shows, not to its code. Returns ``(font, {character: how})``."""
    redrawn = FROM_MOD if redrawn is None else redrawn
    switch_meta, switch_sheets = bcfnt.extract(as_rfnt(switch_font), {})
    wii_meta, _sheets = bcfnt.extract(wii_font, {})
    sw_map, wii_map = char_map(switch_meta), char_map(wii_meta)
    shown_elsewhere = set(redrawn.values())
    copies = [(ch, ch) for ch in chars if ch not in shown_elsewhere] + list(redrawn.items())
    # a letter whose alias the Wii font lacks (menu font: no ï) takes the Switch font's glyph of that alias
    copies += [(ch, other) for ch, other in ALIASES.items() if other not in wii_map]
    copies = [(target, source) for target, source in copies if source in sw_map and target not in wii_map]
    wanted = [target for target, _source in copies]
    width, height, columns, rows = _cells(wii_meta, _sheets)
    per_sheet = columns * rows
    count = len(_sheets) * per_sheet
    sheets_needed = -(-(count + len(wanted)) // per_sheet)
    params = {"min_sheets": sheets_needed} if wanted else {}
    wii_meta, sheets = bcfnt.extract(wii_font, params)
    ratio = _scale(wii_meta, switch_meta)
    wii_base = wii_meta["INF1"][0]["ascent"]
    sw_base = switch_meta["INF1"][0]["ascent"]
    packets = wii_meta["WID1"][0]["packets"]
    sw_packets = switch_meta["WID1"][0]["packets"]
    pairs, report = [], {}
    for number, (ch, original) in enumerate(copies):
        glyph = count + number
        source = _cell(switch_sheets, switch_meta, sw_map[original])
        scaled = source.resize((max(1, round(source.width * ratio)), max(1, round(source.height * ratio))),
                               Image.LANCZOS)
        cell = Image.new("RGBA", (width, height))
        cell.paste(scaled, (0, round(wii_base - sw_base * ratio)))
        sheet, index = divmod(glyph, per_sheet)
        sheets[sheet].paste(cell, (index % columns * width, index // columns * height))
        packet = sw_packets[sw_map[original]]
        packets[glyph] = {"kerning": round(packet["kerning"] * ratio), "width": round(packet["width"] * ratio)}
        pairs.append((ord(ch), glyph))
        report[ch] = "copied" if ch == original else f"copied from {original}"
    added = dict(pairs)
    for ch, other in ALIASES.items():
        target = wii_map.get(other, added.get(ord(other)))
        if ch not in wii_map and ord(ch) not in added and target is not None:
            pairs.append((ord(ch), target))
            report[ch] = f"glyph of {other}"
    if not pairs:
        return bytes(wii_font), report
    wii_meta["MAP1"].append(map_entries(pairs))
    return bcfnt.pack(wii_meta, sheets, wii_font, params), report


def port_font_arc(wii_arc: bytes, switch_arc: bytes, members: Iterable[str] = FONTS) -> Tuple[bytes, Dict[str, dict]]:
    """The Wii ``Font.arc`` with the glyphs of each member copied from the Switch ``Font.arc``'s same member."""
    wii, switch = RarcContainer(wii_arc), RarcContainer(switch_arc)
    report: Dict[str, dict] = {}
    for member in members:
        if member not in wii.list_files() or member not in switch.list_files():
            continue
        font, done = port_glyphs(wii.read_file(member), switch.read_file(member))
        if done:
            wii.write_file(member, font)
        report[member] = done
    return wii.pack(), report
