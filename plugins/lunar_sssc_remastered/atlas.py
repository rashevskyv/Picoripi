"""The Remastered text font (``FIL/CUSTOM/Font/0`` of data.cpk) as 16x16 glyphs and widths for the PS1 message-window preview.

``test.fnt`` is an AngelCode BMFont text file: ``size=64``, one ``char`` line per glyph (``id`` is the Unicode code
point; ``x y width height`` its rectangle on page ``page``; ``xoffset yoffset`` where the rectangle sits in the
64-pixel cell; ``xadvance`` the pen step) and one ``page`` line per DDS texture (``test_NN.dds``, the glyph is in the
alpha channel). The PS1 program font has only the 91 ASCII glyphs; the Japanese text takes its glyphs from here.

Font 0 (FOT-DotGothic16) is a 16-dot font drawn 4 times larger: every dot is a 4-pixel step of the rectangle (a dot
is 5 pixels wide, one pixel overlaps the next). A glyph is read back to 16x16 at the centre of each dot, so the
preview shows the font's own dots; widths are ``xadvance`` divided by the same step.

A font edited in the font editor is in the translation folder with only its changed pages; every file is taken from
the first folder that has it.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from PIL import Image

FONT_FILE = "test.fnt"
CELL = 16                       # the PS1 glyph: 16 rows of 16 bits, high bit left (dialogue_preview._blit)
INK = 128                       # alpha from which a dot is drawn
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


def _first(folders: Iterable[Path], name: str) -> Optional[Path]:
    return next((Path(f) / name for f in folders if (Path(f) / name).is_file()), None)


@lru_cache(maxsize=8)
def _font(path: str, stamp: int) -> Dict[str, object]:
    return parse(Path(path).read_text(encoding="utf-8", errors="replace"))


def _read(folders: Iterable[Path]) -> Optional[Dict[str, object]]:
    path = _first(folders, FONT_FILE)
    return _font(str(path), path.stat().st_mtime_ns) if path else None


def _step(font: Dict[str, object]) -> int:
    return max(1, (font["size"] or 64) // CELL)


def widths(*folders: Path) -> Dict[str, int]:
    """Character -> pen advance in PS1 pixels (``xadvance`` / step) of every glyph; {} without the font.

    Cached until the font file changes: the width check asks for every string."""
    path = _first(folders, FONT_FILE)
    return _widths(str(path), path.stat().st_mtime_ns) if path else {}


@lru_cache(maxsize=8)
def _widths(path: str, stamp: int) -> Dict[str, int]:
    font = _font(path, stamp)
    step = _step(font)
    return {chr(code): round(info["xadvance"] / step) for code, info in font["chars"].items()}


def glyphs(*folders: Path, skip: Iterable[str] = ()) -> Dict[str, List[int]]:
    """Character -> 16 row words of every glyph of the font except ``skip`` (the ones another font draws).

    A missing font gives {}.
    """
    font = _read(folders)
    if font is None:
        return {}
    step = _step(font)
    half = step // 2
    skipped = set(skip)
    by_page: Dict[int, List[str]] = {}
    for code, info in font["chars"].items():
        ch = chr(code)
        if ch not in skipped and info["width"] > 1 and info["height"] > 1:
            by_page.setdefault(info["page"], []).append(ch)
    out: Dict[str, List[int]] = {}
    for page, chars in sorted(by_page.items()):
        path = _first(folders, font["pages"][page])
        if path is None:
            continue
        sheet = Image.open(path).getchannel("A").load()
        for ch in chars:
            info = font["chars"][ord(ch)]
            rows = [0] * CELL
            left, top = (info["xoffset"] + half) // step, (info["yoffset"] + half) // step
            for j in range(info["height"] // step):    # the extra pixel of the last dot is not a dot
                y = info["y"] + j * step + half
                for i in range(info["width"] // step):
                    x = info["x"] + i * step + half
                    col, row = left + i, top + j
                    if 0 <= col < CELL and 0 <= row < CELL and sheet[x, y] >= INK:
                        rows[row] |= 1 << (CELL - 1 - col)
            out[ch] = rows
    return out
