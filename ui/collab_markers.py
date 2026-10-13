"""Room markers on the block tree: who works there (a colour disc with the initial), a claim (lock and the owner's
initial; grey when the owner is offline) and open comments (bubble and count).

The handler decides what a node shows; this module only draws and writes the marker text. The marker text is kept in
a role of its own, so the next text refresh of the item replaces it cleanly.
"""
from __future__ import annotations

from typing import Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QTreeWidgetItem

from core.i18n import tr

MARK_ROLE = Qt.ItemDataRole.UserRole + 30
PALETTE = ("#e6553f", "#3f8fe6", "#3fae6b", "#b07ae6", "#e6a23f", "#3fb8c4", "#d45c9a", "#7a8a3f")
OFFLINE_COLOUR = "#8a8a8a"
_icons: Dict[str, QIcon] = {}


def initial(name: str) -> str:
    return (name.strip()[:1] or "?").upper()


def colour_for(name: str) -> QColor:
    """The same name gets the same colour on every computer (no randomised hash)."""
    return QColor(PALETTE[sum(ord(ch) for ch in name) % len(PALETTE)])


def presence_icon(name: str) -> QIcon:
    """A small disc in the participant's colour with its initial; made once per name."""
    if name not in _icons:
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(colour_for(name))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 13, 13)
        painter.setPen(QColor("white"))
        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(max(6.0, font.pointSizeF() * 0.75))
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, initial(name))
        painter.end()
        _icons[name] = QIcon(pixmap)
    return _icons[name]


def apply_markers(item: QTreeWidgetItem, presence: Optional[str], presence_more: int, claim: Optional[str],
                  claim_offline: bool, comments: int, tooltip: str) -> None:
    """Write the markers of one node; with nothing to show, the node goes back to its plain text."""
    old_suffix = item.data(0, MARK_ROLE) or ""
    text = item.text(0)
    base = text[: -len(old_suffix)] if old_suffix and text.endswith(old_suffix) else text
    parts = []
    if presence:
        parts.append("● " + initial(presence) + (f"+{presence_more}" if presence_more else ""))
    if claim:
        parts.append("🔒 " + initial(claim))
    if comments:
        parts.append(f"💬 {comments}")
    suffix = ("  " + "  ".join(parts)) if parts else ""
    tree = item.treeWidget()
    was_blocked = tree.blockSignals(True) if tree is not None else False
    try:
        if base + suffix != text:
            item.setText(0, base + suffix)
        item.setData(0, MARK_ROLE, suffix)
        item.setIcon(0, presence_icon(presence) if presence else QIcon())
        item.setForeground(0, QBrush(QColor(OFFLINE_COLOUR)) if claim_offline else QBrush())
        item.setToolTip(0, tooltip)
    finally:
        if tree is not None:
            tree.blockSignals(was_blocked)


def presence_line(name: str, minutes: int) -> str:
    return tr('{name} works here, {minutes} min ago', name=name, minutes=minutes)
