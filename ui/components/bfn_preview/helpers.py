"""BFN preview helper predicates and icon painters."""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

def _looks_like_bfn_editor(editor) -> bool:
    """Structural check that 'editor' is a real BFN editor window.

    The real BfnEditorWindow and the test DummyBfnEditor both expose a `metadata` dict
    and a `sheet_images` list.
    """
    if editor is None:
        return False
    metadata = getattr(editor, 'metadata', None)
    sheets = getattr(editor, 'sheet_images', None)
    return isinstance(metadata, dict) and isinstance(sheets, list)
def _looks_like_bfn_core(bfn) -> bool:
    """Structural check that 'bfn' is a real BfnCore-like object with a callable layout_text."""
    if bfn is None:
        return False
    return (
        isinstance(getattr(bfn, 'gly1', None), list)
        and isinstance(getattr(bfn, 'map1', None), list)
        and isinstance(getattr(bfn, 'wid1', None), list)
    )
def _preview_icon(kind: str, size: int = 16, color: str = "#e0e0e0") -> QIcon:
    """Vector glyphs that do not depend on emoji fonts (those often render blank)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    c = QColor(color)
    pen = QPen(c, 1.4)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = 2.5
    if kind == "shadow":
        p.drawRoundedRect(QRectF(m + 2, m + 2, size - 7, size - 7), 2, 2)
        p.setPen(QPen(c, 1.6))
        p.drawRoundedRect(QRectF(m, m, size - 7, size - 7), 2, 2)
    elif kind == "glow":
        p.setBrush(QColor(c.red(), c.green(), c.blue(), 80))
        cx = cy = size / 2.0
        r = size * 0.38
        path = QPainterPath()
        for i in range(8):
            ang = i * 3.14159265 / 4.0 - 3.14159265 / 2.0
            rad = r if i % 2 == 0 else r * 0.45
            pt = QPointF(cx + rad * math.cos(ang), cy + rad * math.sin(ang))
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        path.closeSubpath()
        p.drawPath(path)
    elif kind == "image":
        p.drawRoundedRect(QRectF(m, m + 1, size - 2 * m, size - 2 * m - 1), 2, 2)
        p.setBrush(c)
        mountain = QPainterPath()
        mountain.moveTo(m + 1, size - m - 2)
        mountain.lineTo(size * 0.4, size * 0.45)
        mountain.lineTo(size * 0.62, size * 0.7)
        mountain.lineTo(size - m - 1, size - m - 2)
        mountain.closeSubpath()
        p.drawPath(mountain)
        p.drawEllipse(QRectF(size * 0.58, m + 3, 3.5, 3.5))
    elif kind == "eye":
        p.drawEllipse(QRectF(m, size * 0.32, size - 2 * m, size * 0.36))
        p.setBrush(c)
        p.drawEllipse(QRectF(size * 0.38, size * 0.38, size * 0.24, size * 0.24))
    elif kind == "spacing":
        for y in (m + 2, size / 2.0, size - m - 2):
            p.drawLine(QPointF(m + 1, y), QPointF(size - m - 1, y))
    elif kind == "prev":
        path = QPainterPath()
        path.moveTo(size * 0.68, m + 1)
        path.lineTo(size * 0.32, size / 2.0)
        path.lineTo(size * 0.68, size - m - 1)
        p.drawPath(path)
    elif kind == "next":
        path = QPainterPath()
        path.moveTo(size * 0.32, m + 1)
        path.lineTo(size * 0.68, size / 2.0)
        path.lineTo(size * 0.32, size - m - 1)
        p.drawPath(path)
    elif kind == "up":
        path = QPainterPath()
        path.moveTo(m + 1, size * 0.68)
        path.lineTo(size / 2.0, size * 0.32)
        path.lineTo(size - m - 1, size * 0.68)
        p.drawPath(path)
    elif kind == "down":
        path = QPainterPath()
        path.moveTo(m + 1, size * 0.32)
        path.lineTo(size / 2.0, size * 0.68)
        path.lineTo(size - m - 1, size * 0.32)
        p.drawPath(path)
    p.end()
    return QIcon(pm)
def _letter_icon(letter: str, color: str, size: int = 16) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    font = p.font()
    font.setBold(True)
    font.setPixelSize(size - 1)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, letter)
    p.end()
    return QIcon(pm)
