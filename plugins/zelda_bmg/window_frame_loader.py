"""Load TP message-window frames from a local retail dump (res/Layout)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter

from core.containers.rarc_container import RarcContainer

from .bti_image import bti_to_qimage
from .j2d_blo import parse_blo, J2DPane
from .window_kinds import EXPLAIN_PRESET_KEY


_SCREEN_RES = {
    "talk": ("msgres01.arc", "scrn/zelda_message_window_new.blo"),
    "wood": ("msgres02.arc", "scrn/zelda_kanban_wood_a.blo"),
    "stone": ("msgres02.arc", "scrn/zelda_kanban_stone_a.blo"),
    "item": ("msgres03.arc", "scrn/zelda_item_get_window.blo"),
    "place": ("msgres04F.arc", "scrn/zelda_stage_title_foreign.blo"),
    "boss": ("msgres04F.arc", "scrn/zelda_boss_name.blo"),
    "howl": ("msgres05.arc", "scrn/zelda_wolf_howl.blo"),
    "staff": ("msgres06.arc", "scrn/zelda_staff_roll.blo"),
    "explain": ("msgres01.arc", "scrn/zelda_message_window_new.blo"),
}

_KIND_CLASS = {
    0: "talk", 3: "talk", 4: "talk", 8: "talk", 10: "talk", 11: "talk",
    13: "talk", 14: "talk", 15: "talk", 16: "talk", 18: "talk",
    2: "wood", 6: "stone", 9: "item", 12: "place", 19: "boss",
    17: "howl", 7: "staff",
}
_NO_FRAME = {"jimaku"}
_CLASS_ALIAS = {"tree": "wood", "kanban": "stone"}

_HIO = {
    "talk": (1.2, 1.0),
    "item": (1.05, 0.97),
    "wood": (1.0, 1.0),
    "stone": (1.0, 1.0),
    "howl": (1.05, 1.1),
    "place": (1.0, 1.0),
    "boss": (1.0, 1.0),
    "staff": (1.0, 1.0),
    "explain": (1.2, 1.0),
}

_KNOWN_DUMP = Path(r"E:\Emulators\RomHacking\ZELDA\TP_UA\ISO\ENG\root")

# dItem_data::item_resource[i].mTexture — itemicon.arc file_id
_ITEM_TEXTURE = (
    45,45,45,45,45,45,45,45,45,45,12,12,12,12,83,83,83,83,92,45,45,45,13,13,13,13,11,11,11,11,45,45,
    110,80,81,113,111,40,33,38,112,66,116,64,60,34,107,107,65,77,46,45,40,71,72,73,80,80,80,80,114,45,42,89,
    36,98,43,32,105,106,37,22,44,108,66,24,91,22,45,45,86,85,85,86,45,74,75,76,45,78,12,89,25,27,26,28,
    29,17,17,17,17,17,18,17,17,17,17,17,17,17,17,108,108,12,13,11,17,17,17,17,17,17,17,17,17,17,19,19,
    19,90,84,88,93,93,45,45,45,45,45,45,45,45,45,45,45,34,34,45,45,45,45,45,45,45,45,45,45,108,17,17,
    17,45,82,82,82,82,45,45,45,45,45,45,45,45,45,45,45,45,45,45,45,45,45,45,45,45,45,45,45,45,45,45,
    17,48,47,8,7,56,55,6,5,59,58,10,9,52,51,95,94,54,53,97,96,4,3,50,49,45,45,45,45,45,45,45,45,62,45,45,
    45,45,45,45,45,45,79,79,79,38,45,110,17,17,17,17,110,41,21,63,60,108,67,69,70,110,23,110,
)


@dataclass
class WindowFrame:
    image: QImage
    screen: Tuple[int, int]
    box: Tuple[float, float, float, float]
    text: Tuple[float, float, float, float]
    icon_slot: Optional[Tuple[float, float, float, float]] = None


_CACHE: Dict[str, Optional[WindowFrame]] = {}
_LAYOUT_ROOT: Optional[Path] = None


def screen_class_for_kind(kind, style=None) -> Optional[str]:
    if kind == EXPLAIN_PRESET_KEY:
        return "explain"
    cls = (style or {}).get("screen_class")
    if cls in _NO_FRAME:
        return None
    if cls in _CLASS_ALIAS:
        return _CLASS_ALIAS[cls]
    if cls in _SCREEN_RES:
        return cls
    try:
        k = int(kind or 0)
    except (TypeError, ValueError):
        return "talk"
    if k in (1, 5):
        return None
    return _KIND_CLASS.get(k, "talk")


def find_layout_root(mw=None) -> Optional[Path]:
    global _LAYOUT_ROOT
    if _LAYOUT_ROOT and (_LAYOUT_ROOT / "msgres01.arc").is_file():
        return _LAYOUT_ROOT
    candidates = []
    if mw is not None:
        explicit = getattr(mw, "zelda_game_root", None) or getattr(mw, "game_dump_root", None)
        if explicit:
            candidates.append(Path(str(explicit)))
        ds = getattr(mw, "data_store", None)
        for attr in ("json_path", "edited_json_path"):
            p = getattr(ds, attr, None) if ds is not None else None
            if p:
                candidates.append(Path(str(p)))
        pm = getattr(mw, "project_manager", None)
        proj = getattr(pm, "project", None) if pm else None
        if proj is not None:
            for block in getattr(proj, "blocks", []) or []:
                src = getattr(block, "source_file", None)
                if src:
                    candidates.append(Path(str(src)))
                    break
    # The user's retail dump is used by the app, not by unit tests.
    if not os.environ.get("PYTEST_CURRENT_TEST") and _KNOWN_DUMP.is_dir():
        candidates.append(_KNOWN_DUMP)
    seen = set()
    for start in candidates:
        cur = start if start.is_dir() else start.parent
        for _ in range(12):
            key = str(cur)
            if key in seen:
                break
            seen.add(key)
            for layout in (cur / "res" / "Layout", cur / "Layout", cur):
                if (layout / "msgres01.arc").is_file():
                    _LAYOUT_ROOT = layout
                    return layout
            if cur.parent == cur:
                break
            cur = cur.parent
    return None


def load_item_icon(item_no: int, mw=None) -> Optional[QImage]:
    """BTI from itemicon.arc using d_item_data mTexture as the RARC file_id."""
    try:
        idx = int(item_no)
    except (TypeError, ValueError):
        return None
    if idx < 0:
        return None
    tex_id = _ITEM_TEXTURE[idx] if idx < len(_ITEM_TEXTURE) else idx
    layout = find_layout_root(mw)
    if layout is None:
        return None
    path = layout / "itemicon.arc"
    if not path.is_file():
        return None
    try:
        arc = RarcContainer(path.read_bytes())
        for file_path, entry_idx in arc._file_paths.items():
            if arc._entries[entry_idx]["file_id"] == int(tex_id):
                img = bti_to_qimage(arc.read_file(file_path))
                return img if img is not None and not img.isNull() else None
    except Exception:
        return None
    return None


def load_window_frame(screen_class: str, mw=None) -> Optional[WindowFrame]:
    if screen_class not in _SCREEN_RES:
        return None
    if screen_class in _CACHE:
        return _CACHE[screen_class]
    layout = find_layout_root(mw)
    if layout is None:
        _CACHE[screen_class] = None
        return None
    arc_name, blo_path = _SCREEN_RES[screen_class]
    arc_path = layout / arc_name
    if not arc_path.is_file() and screen_class in ("place", "boss"):
        arc_path = layout / "msgres04.arc"
        blo_path = ("scrn/zelda_stage_title.blo" if screen_class == "place"
                    else "scrn/zelda_boss_name.blo")
    if not arc_path.is_file():
        _CACHE[screen_class] = None
        return None
    try:
        arc = RarcContainer(arc_path.read_bytes())
        textures = {}
        for path in arc.list_files():
            if path.lower().endswith(".bti"):
                textures[Path(path).stem] = bti_to_qimage(arc.read_file(path))
        root, _names, size = parse_blo(arc.read_file(blo_path))
        box = _root_child_rect(root, "n_all") or (24.0, 280.0, 560.0, 140.0)
        icon_slot = _nested_rect(root, "n_all", "set_it_n")
        text = _text_pane_rect(screen_class, box, icon_slot)
        image = _compose(screen_class, size, box, textures)
        frame = WindowFrame(image=image, screen=size, box=box, text=text, icon_slot=icon_slot)
    except Exception:
        frame = None
    _CACHE[screen_class] = frame
    return frame


def frame_to_geometry(frame: WindowFrame) -> dict:
    geom = {
        "screen": list(frame.screen),
        "box": list(frame.box),
        "text": list(frame.text),
        "hio_scale": [1.0, 1.0],
        "asset_frame": True,
        "item_text_already_inset": frame.icon_slot is not None,
    }
    if frame.icon_slot:
        geom["icon_slot"] = list(frame.icon_slot)
    return geom


def _scale_rect(rect, hx, hy, cx, cy):
    x, y, w, h = rect
    w, h = w * hx, h * hy
    return (cx - w / 2.0, cy - h / 2.0, w, h)


def _root_child_rect(root: J2DPane, name: str) -> Optional[Tuple[float, float, float, float]]:
    for child in root.children:
        if child.name == name:
            w, h = child.width, child.height
            return (child.x - w / 2.0, child.y - h / 2.0, w, h)
    return None


# Non-JP J2DTextBox `mg_e4lin` in the companion *text.blo (msgcom / item text).
# Height is exactly 4 lines (talk/item) or 7 (signs).
_TEXT_PANE = {
    "talk": (443.0, 114.0),
    "explain": (443.0, 114.0),
    "item": (400.0, 95.0),
    "wood": (427.0, 187.0),
    "stone": (427.0, 187.0),
}


def _text_pane_rect(screen_class, box, icon_slot):
    tw, th = _TEXT_PANE.get(screen_class, (max(40.0, box[2] - 44.0), max(24.0, box[3] - 16.0)))
    bx, by, bw, bh = box
    if icon_slot and screen_class == "item":
        ix, iy, iw, ih = icon_slot
        tx = ix + iw + 10.0
        # Keep the 400px BLO width; sit it vertically in the window.
        ty = by + (bh - th) / 2.0
        return (tx, ty, tw, th)
    tx = bx + (bw - tw) / 2.0
    ty = by + (bh - th) / 2.0
    return (tx, ty, tw, th)


def _nested_rect(root: J2DPane, parent_name: str, child_name: str):
    parent = next((c for c in root.children if c.name == parent_name), None)
    if parent is None:
        return None
    px, py, pw, ph = parent.x - parent.width / 2.0, parent.y - parent.height / 2.0, parent.width, parent.height
    pcx, pcy = px + pw / 2.0, py + ph / 2.0
    for child in parent.children:
        if child.name == child_name:
            w, h = child.width, child.height
            return (pcx + child.x - w / 2.0, pcy + child.y - h / 2.0, w, h)
    return None


def _alpha_tint(src: QImage, color: QColor) -> QImage:
    out = QImage(src.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.drawImage(0, 0, src)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(out.rect(), color)
    p.end()
    return out


def _find_tex(textures: Dict[str, QImage], *parts: str) -> Optional[QImage]:
    for name, img in textures.items():
        nl = name.lower()
        if all(p in nl for p in parts) and not img.isNull():
            return img
    return None


def _compose(screen_class: str, size, box, textures: Dict[str, QImage]) -> QImage:
    canvas = QImage(int(size[0]), int(size[1]), QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(Qt.GlobalColor.transparent)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    try:
        if screen_class in ("talk", "explain", "item"):
            _paint_talk_like(p, box, textures, item=(screen_class == "item"))
        elif screen_class in ("wood", "stone"):
            _paint_sign(p, box, textures, stone=(screen_class == "stone"))
        else:
            _paint_plate(p, box, textures)
    finally:
        p.end()
    return canvas


def _paint_talk_like(p: QPainter, box, textures, item=False):
    x, y, w, h = box
    dark = QColor(8, 10, 16, 252)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(dark)
    p.drawRoundedRect(QRectF(x, y, w, h), 6.0, 6.0)
    if item:
        gold = _find_tex(textures, "gold_uzu") or _find_tex(textures, "kazari")
        if gold is not None:
            ornament = _alpha_tint(gold, QColor(210, 190, 120, 230))
            side = min(48.0, w * 0.1)
            p.drawImage(QRectF(x, y, side, h), ornament)
            p.drawImage(QRectF(x + w - side, y, side, h), ornament.mirrored(True, False))
        return
    # Talk filigree: one left-side kado texture, mirrored for the right.
    kado = _find_tex(textures, "kado")
    if kado is None:
        return
    ornament = _alpha_tint(kado, QColor(232, 216, 168, 255))
    ow, oh = float(kado.width()), float(kado.height())
    p.drawImage(QRectF(x - 8.0, y + (h - oh) / 2.0, ow, oh), ornament)
    p.drawImage(QRectF(x + w - ow + 8.0, y + (h - oh) / 2.0, ow, oh),
                ornament.mirrored(True, False))


def _paint_sign(p: QPainter, box, textures, stone=False):
    x, y, w, h = box
    color = QColor(120, 120, 118, 255) if stone else QColor(118, 82, 48, 255)
    p.fillRect(QRectF(x, y, w, h), color)
    grain = _find_tex(textures, "block128") or _find_tex(textures, "yakushima")
    if grain is not None:
        p.save()
        p.setOpacity(0.45)
        p.drawImage(QRectF(x, y, w, h), grain)
        p.restore()
    rail = (_find_tex(textures, "kanban_metal") or _find_tex(textures, "horiwaku")
            or _find_tex(textures, "gakubuchi"))
    if rail is not None:
        rw = min(36.0, w * 0.08)
        p.drawImage(QRectF(x, y, rw, h), rail)
        p.drawImage(QRectF(x + w - rw, y, rw, h), rail.mirrored(True, False))


def _paint_plate(p: QPainter, box, textures):
    x, y, w, h = box
    fill = _find_tex(textures, "black") or _find_tex(textures, "i4_gra")
    dark = QColor(0, 0, 0, 160)
    if fill is not None:
        p.drawImage(QRectF(x, y, w, h), _alpha_tint(fill, dark))
    else:
        p.fillRect(QRectF(x, y, w, h), dark)
    gold = _find_tex(textures, "gold_uzu") or _find_tex(textures, "kazari")
    if gold is not None:
        tinted = _alpha_tint(gold, QColor(228, 214, 170, 220))
        p.drawImage(QRectF(x, y, min(80.0, w * 0.2), h), tinted)
        p.drawImage(QRectF(x + w - min(80.0, w * 0.2), y, min(80.0, w * 0.2), h),
                    tinted.mirrored(True, False))
