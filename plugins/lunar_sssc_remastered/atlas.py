"""The Remastered text font (``FIL/CUSTOM/Font/0`` of data.cpk) as 16x16 glyphs for the PS1 message-window preview.

``test.fnt`` is an AngelCode BMFont text file: ``size=64``, one ``char`` line per glyph (``id`` is the Unicode code
point; ``x y width height`` its rectangle on page ``page``; ``xoffset yoffset`` where the rectangle sits in the
64-pixel cell) and one ``page`` line per DDS texture (``test_NN.dds``, the glyph is in the alpha channel). The PS1
program font has only the 91 ASCII glyphs; the Japanese text takes its glyphs from here, scaled to the PS1 cell.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List

from PIL import Image

FONT_FILE = "test.fnt"
CELL = 16                       # the PS1 glyph: 16 rows of 16 bits, high bit left (dialogue_preview._blit)
INK = 96                        # alpha from which a scaled pixel is drawn
_PAIR = re.compile(r'(\w+)=("[^"]*"|\S+)')


def _fields(line: str) -> Dict[str, str]:
    return {key: value.strip('"') for key, value in _PAIR.findall(line)}


def parse(text: str) -> Dict[str, object]:
    """``{"size", "pages": {id: file}, "chars": {code: fields}}`` of a BMFont text file."""
    size, pages, chars = 0, {}, {}
    for line in text.splitlines():
        kind, _, rest = line.partition(" ")
        fields = _fields(rest)
        if kind == "info":
            size = int(fields.get("size", 0))
        elif kind == "page":
            pages[int(fields["id"])] = fields["file"]
        elif kind == "char":
            chars[int(fields["id"])] = {key: int(value) for key, value in fields.items()}
    return {"size": size, "pages": pages, "chars": chars}


def glyphs(folder: Path, skip: Iterable[str] = ()) -> Dict[str, List[int]]:
    """Character -> 16 row words of every glyph of the font except ``skip`` (the ones another font draws).

    A missing font folder gives {}.
    """
    path = Path(folder) / FONT_FILE
    if not path.is_file():
        return {}
    font = parse(path.read_text(encoding="utf-8", errors="replace"))
    size = font["size"] or 64
    skipped = set(skip)
    by_page: Dict[int, List[str]] = {}
    for code, info in font["chars"].items():
        ch = chr(code)
        if ch not in skipped and info["width"] > 1 and info["height"] > 1:
            by_page.setdefault(info["page"], []).append(ch)
    out: Dict[str, List[int]] = {}
    for page, chars in sorted(by_page.items()):
        sheet = Image.open(Path(folder) / font["pages"][page]).getchannel("A")
        for ch in chars:
            info = font["chars"][ord(ch)]
            cell = Image.new("L", (size, size), 0)
            rect = sheet.crop((info["x"], info["y"], info["x"] + info["width"], info["y"] + info["height"]))
            cell.paste(rect, (info["xoffset"], info["yoffset"]))
            small = cell.resize((CELL, CELL), Image.Resampling.BOX).load()
            out[ch] = [sum(1 << (CELL - 1 - x) for x in range(CELL) if small[x, y] >= INK) for y in range(CELL)]
    return out
