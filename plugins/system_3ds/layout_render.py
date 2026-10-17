"""In-place drawing of a 3DS system string: its text pane in the layout that holds it, drawn as the console draws it.

A string is linked to a text pane of a layout in the owner's romfs (``layout_links.json``, built by
scripts/build_system_3ds_layouts.py). Two kinds: ``label`` (a text pane whose user data names the MSBT label: the
pane's text is the label's text at run time) and ``spec`` (one line of a text pane baked in the layout, the lines of
src/layouts). The layout is read from the romfs of the repo_manual folder, the pane's text is set to the string's
text with the owner's bclyt tool, and the layout is drawn by console_render on a screen canvas.

Backdrop: the console's backdrop is not known. The canvas is filled with a placeholder dark colour; the panel says so.
Reads and draws run on the render worker, never on the UI thread.
"""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from plugins.manual_3ds import console_render as cr
from plugins.manual_3ds import repo_tools

LINKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layout_links.json")
PLACEHOLDER_BACKDROP = (40, 44, 52, 255)  # not the console's backdrop: the console's is in a layout not yet found
OUTLINE = (255, 140, 0, 255)
OUTLINE_WIDTH = 2
TAG = re.compile(r"\{/?t:[^}]*\}")  # MSBT tags draw nothing on the console; scale tags are dropped too (see box.py)
_LOCK = threading.Lock()
_LINKS: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None
_TEXTURES: Dict[str, cr.Textures] = {}


@dataclass(frozen=True)
class Link:
    kind: str                # "label" or "spec" (see the module docstring)
    tid: str                 # title id: the romfs folder under work/
    file: str                # the romfs file that holds the layout (a path under romfs/)
    chain: Tuple[str, ...]   # DARC member names from that file down to the layout
    pane: str                # the text pane's name
    line: int = -1           # spec only: index of the English line in the pane's lines


def load_links(path: str = LINKS_FILE) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """{part: {string key: link fields}} from the built file; {} when the file is missing or broken."""
    global _LINKS
    with _LOCK:
        if _LINKS is None:
            try:
                with open(path, encoding="utf-8") as handle:
                    _LINKS = json.load(handle).get("links", {})
            except (OSError, ValueError, AttributeError):
                _LINKS = {}
        return _LINKS


def link_of(part: str, key: Optional[str], table: Optional[Dict[str, Any]] = None) -> Optional[Link]:
    """The layout link of a string of ``part`` with string key ``key``, or None."""
    if not part or not key:
        return None
    fields = (table if table is not None else load_links()).get(part, {}).get(key)
    if not fields:
        return None
    return Link(fields["kind"], fields["tid"], fields["file"], tuple(fields["chain"]), fields["pane"],
                int(fields.get("line", -1)))


class ScreenRenderer(cr.PageRenderer):
    """PageRenderer on a screen canvas: the origin is the screen's centre, y grows upward."""

    def __init__(self, textures: cr.Textures, glyphs: cr.Glyphs, width: float, height: float):
        super().__init__(textures, glyphs)
        self._w = int(round(width))
        self._h = int(round(height))

    def to_column(self, page_x: float, page_y: float) -> Tuple[float, float]:
        return page_x + self._w / 2, self._h / 2 - page_y

    def _draw_line(self, canvas: Image.Image, line: str, x: float, top: float, scale_x: float, scale_y: float,
                   char_space: float, colour_top: Any, colour_bottom: Any, alpha: int) -> None:
        # The base class takes the pen x in column units (the manual's x is never negative): shift it onto the canvas.
        super()._draw_line(canvas, line, x + self._w / 2, top, scale_x, scale_y, char_space, colour_top,
                           colour_bottom, alpha)

    def draw(self, data: bytes, backdrop: Tuple[int, int, int, int]) -> Tuple[Image.Image, Any]:
        layout = cr.parse(data)
        canvas = Image.new("RGBA", (self._w, self._h), backdrop)
        for pane in layout.panes:
            if not pane.visible:
                continue
            if pane.kind == "wnd1":
                self._draw_window(canvas, layout, pane)
            elif pane.kind == "pic1":
                self._draw_picture(canvas, layout, pane)
            elif pane.kind == "txt1":
                self._draw_text(canvas, layout, pane)
        return canvas, layout

    def pane_box(self, pane: cr.Pane) -> Tuple[float, float, float, float]:
        """The pane's box on the canvas: (left, top, right, bottom)."""
        left, top = pane.top_left
        x, y = self.to_column(left, top)
        return x, y, x + pane.w, y + pane.h


def _decode(data: bytes, tools: Any) -> bytes:
    if data[:1] in (b"\x10", b"\x11"):
        return (tools.lz11 if data[0] == 0x11 else tools.lz10).decompress(data)
    return data


def layout_bytes(tools: Any, romfs: str, link: Link) -> bytes:
    """The layout's BCLYT bytes: the romfs file, decoded, then each DARC member of the chain.

    Raises FileNotFoundError when the romfs file is missing, KeyError when a member is not in its archive."""
    with open(os.path.join(romfs, *link.file.split("/")), "rb") as handle:
        data = handle.read()
    for name in link.chain:
        data = _decode(data, tools)
        members = dict((member, entry) for member, entry in tools.darc.parse(data).files())
        data = bytes(members[name].data)
    data = _decode(data, tools)
    if data[:4] != b"CLYT":
        raise ValueError(f"{link.file} is not a layout")
    return data


def _collect_bclim(tools: Any, data: bytes, name: str, out: Dict[str, bytes]) -> None:
    """Every BCLIM under ``data`` (a file or an archive, recursively) into ``out``; a member that does not decode is skipped."""
    if name.lower().endswith(".bclim"):
        out.setdefault(os.path.basename(name), data)
        out.setdefault(os.path.splitext(os.path.basename(name))[0], data)
        return
    try:
        blob = _decode(data, tools)
        members = tools.darc.parse(blob).files() if blob[:4] == b"darc" else []
    except Exception:
        return
    for member, entry in members:
        if not entry.is_dir and entry.data is not None:
            _collect_bclim(tools, bytes(entry.data), member, out)


def textures_of(tools: Any, romfs: str) -> cr.Textures:
    """Every BCLIM of a title's romfs, from every archive, read once per folder (a layout uses textures of other
    archives)."""
    with _LOCK:
        cached = _TEXTURES.get(romfs)
    if cached is not None:
        return cached
    found: Dict[str, bytes] = {}
    for root, _, files in os.walk(romfs):
        for fname in files:
            path = os.path.join(root, fname)
            with open(path, "rb") as handle:
                _collect_bclim(tools, handle.read(), fname, found)
    textures = cr.Textures(found)
    with _LOCK:
        _TEXTURES[romfs] = textures
    return textures


@dataclass
class LinkedDraw:
    """What a linked string draws: the picture (the pane outlined in it) and the numbers the status line states."""

    image: Image.Image
    pane: str
    kind: str
    wrapped: int
    missing_glyphs: List[str]
    missing_textures: List[str]


def draw_link(root: str, link: Link, text: str, should_stop: Any) -> Optional[LinkedDraw]:
    """Draw the layout of ``link`` with its pane set to ``text`` (None when stopped).

    Raises repo_tools.ToolsError when the folder has no tools or font, and the errors of a layout that does not read."""
    tools = repo_tools.load_tools(root)
    romfs = os.path.join(str(tools.root), "work", link.tid, "romfs")
    glyphs = cr.Glyphs(repo_tools.load_font(tools), tools.bcfnt)
    data = layout_bytes(tools, romfs, link)
    clean = TAG.sub("", text)
    if link.kind == "spec":
        pane_lines = next((p.text for p in cr.parse(data).panes if p.name == link.pane), "").split("\n")
        if not 0 <= link.line < len(pane_lines):
            raise ValueError(f"line {link.line} is not a line of {link.pane}")
        pane_lines[link.line] = clean
        new_text = "\n".join(pane_lines)
    else:
        new_text = clean
    data = tools.bclyt.rewrite(data, {link.pane: tools.bclyt.Edit(text=new_text)})
    if should_stop():
        return None
    textures = textures_of(tools, romfs)
    parsed = cr.parse(data)
    renderer = ScreenRenderer(textures, glyphs, parsed.width, parsed.height)
    canvas, layout = renderer.draw(data, PLACEHOLDER_BACKDROP)
    pane = next((p for p in layout.panes if p.name == link.pane), None)
    if pane is not None:
        draw = ImageDraw.Draw(canvas)
        draw.rectangle(renderer.pane_box(pane), outline=OUTLINE, width=OUTLINE_WIDTH)
    missing_tex = sorted({name for name in layout.textures if textures.get(name) is None})
    wrapped = sum(1 for run in renderer.runs if run.pane == link.pane and run.wrapped)
    return LinkedDraw(canvas, link.pane, link.kind, wrapped, sorted(renderer.missing), missing_tex)
