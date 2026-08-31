"""Minimal blo2 (J2DScreen) parser for TP message windows."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter

from core.containers.yaz0 import decompress


def _maybe_yaz0(data: bytes) -> bytes:
    if data[:4] == b"Yaz0":
        return decompress(data)
    return data


def _name8(raw: bytes) -> str:
    return raw.replace(b"\x00", b"").decode("latin1", "replace")


@dataclass
class J2DPane:
    tag: str
    name: str
    width: float
    height: float
    x: float
    y: float
    scale_x: float = 1.0
    scale_y: float = 1.0
    visible: bool = True
    tex_index: Optional[int] = None
    colors: Tuple[int, int, int, int] = (255, 255, 255, 255)
    children: List["J2DPane"] = field(default_factory=list)


def parse_blo(data: bytes) -> Tuple[J2DPane, List[str], Tuple[int, int]]:
    blo = _maybe_yaz0(data)
    if blo[:8] != b"SCRNblo2":
        raise ValueError("Not a blo2 screen")
    inf = blo[0x20:0x40]
    screen_w, screen_h = struct.unpack_from(">HH", inf, 8)
    textures = _parse_tex1(blo)
    panes: List[J2DPane] = []
    stack: List[J2DPane] = []
    i = 0x20
    while i + 8 <= len(blo):
        tag = blo[i:i + 4].decode("latin1", "replace")
        size = struct.unpack_from(">I", blo, i + 4)[0]
        if tag == "EXT1" or not (8 <= size <= len(blo) - i):
            break
        if tag in ("PAN2", "PIC2"):
            pane = _parse_pane(tag, blo[i:i + size])
            parent = stack[-1] if stack else None
            if parent:
                parent.children.append(pane)
            else:
                panes.append(pane)
        elif tag == "BGN1":
            if panes or stack:
                current = stack[-1].children[-1] if stack else panes[-1]
                stack.append(current)
        elif tag == "END1":
            if stack:
                stack.pop()
        i += size
    root = panes[0] if panes else J2DPane("PAN2", "ROOT", screen_w, screen_h, 0, 0)
    return root, textures, (screen_w, screen_h)


def _parse_tex1(blo: bytes) -> List[str]:
    i = 0x20
    while i + 8 <= len(blo):
        tag = blo[i:i + 4]
        size = struct.unpack_from(">I", blo, i + 4)[0]
        if tag == b"TEX1":
            chunk = blo[i:i + size]
            names = []
            p = 8
            while p + 2 < len(chunk):
                if chunk[p] == 2 and 3 <= chunk[p + 1] <= 80:
                    n = chunk[p + 2:p + 2 + chunk[p + 1]]
                    if n.endswith(b".bti"):
                        names.append(n[:-4].decode("latin1", "replace"))
                        p += 2 + chunk[p + 1]
                        continue
                p += 1
            return names
        if not (8 <= size <= len(blo) - i):
            break
        i += size
    return []


def _parse_pane(tag: str, section: bytes) -> J2DPane:
    if tag == "PIC2":
        data = section[16:]  # skip PIC2 hdr + nested pan2 hdr
    else:
        data = section[8:]
    flags = struct.unpack_from(">H", data, 4)[0]
    name = _name8(data[8:16])
    width, height = struct.unpack_from(">ff", data, 0x18)
    scale_x, scale_y = struct.unpack_from(">ff", data, 0x20)
    x, y = struct.unpack_from(">ff", data, 0x34)
    visible = True
    _ = flags
    tex_index = None
    colors = (255, 255, 255, 255)
    if tag == "PIC2" and len(section) >= 128:
        extra = section[8 + 72:]
        if len(extra) >= 16:
            c = struct.unpack_from(">I", extra, len(extra) - 16)[0]
            colors = ((c >> 24) & 0xFF, (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF)
    return J2DPane(tag, name, width, height, x, y, scale_x, scale_y, visible, tex_index, colors)


def pick_texture_name(pane_name: str, tex_names: List[str]) -> Optional[str]:
    n = pane_name.lower()

    def find(*parts: str) -> Optional[str]:
        for t in tex_names:
            tl = t.lower()
            if all(p in tl for p in parts):
                return t
        return None

    if "line" in n:
        return find("line") or find("i4_gra")
    if "garde" in n or "grade" in n or "kado" in n:
        return find("kado") or find("gakubuchi") or find("horiwaku") or find("kazari")
    if "base_02" in n or n.endswith("02"):
        return find("base_8") or find("8_01") or find("block8") or find("black")
    if "base" in n:
        return find("112") or find("base") or (tex_names[0] if tex_names else None)
    if tex_names:
        return tex_names[0]
    return None


def render_screen(root: J2DPane, textures: Dict[str, QImage], tex_names: List[str],
                  size: Tuple[int, int]) -> QImage:
    canvas = QImage(int(size[0]), int(size[1]), QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    try:
        _draw_pane(painter, root, 0.0, 0.0, size[0], size[1], textures, tex_names, is_root=True)
    finally:
        painter.end()
    return canvas


def _draw_pane(painter: QPainter, pane: J2DPane, parent_x: float, parent_y: float,
               parent_w: float, parent_h: float, textures: Dict[str, QImage],
               tex_names: List[str], is_root: bool = False) -> None:
    w, h = pane.width * pane.scale_x, pane.height * pane.scale_y
    if is_root:
        x, y = 0.0, 0.0
    elif parent_x == 0 and parent_y == 0 and parent_w >= 600:
        # Direct child of ROOT: x/y is the pane centre in screen space.
        x, y = pane.x - w / 2.0, pane.y - h / 2.0
    else:
        pcx, pcy = parent_x + parent_w / 2.0, parent_y + parent_h / 2.0
        x, y = pcx + pane.x - w / 2.0, pcy + pane.y - h / 2.0
    if pane.tag == "PIC2":
        tex_name = pick_texture_name(pane.name, tex_names) or ""
        img = textures.get(tex_name)
        if img is not None and not img.isNull():
            tinted = img
            r, g, b, a = pane.colors
            if (r, g, b, a) != (255, 255, 255, 255):
                tinted = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
                tinted.fill(Qt.GlobalColor.transparent)
                tp = QPainter(tinted)
                tp.drawImage(0, 0, img)
                tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                tp.fillRect(tinted.rect(), QColor(r, g, b, a))
                tp.end()
            painter.drawImage(QRectF(x, y, w, h), tinted)
    for child in pane.children:
        _draw_pane(painter, child, x, y, w, h, textures, tex_names, is_root=False)
