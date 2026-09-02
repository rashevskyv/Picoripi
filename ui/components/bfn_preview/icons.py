"""BFN preview icon texture / vector draw helpers (module-level)."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

_icon_texture_cache: dict = {}

def _tinted_icon_texture(path: str, tint: str):
    """Load an icon PNG and multiply it by the game's TEV tint color.

    Mirrors COutFont_c::createPane's setBlackWhite(black=0, white=tint):
    output = texel_intensity × tint, alpha preserved.  Returns None when
    the file is missing/unreadable so the caller can fall back to vectors.
    """
    cache = _icon_texture_cache
    key = (path, tint)
    if key in cache:
        return cache[key]

    img = QImage(path)
    if img.isNull():
        cache[key] = None
        return None
    img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    if QColor(tint) != QColor("#ffffff"):
        tinted = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
        tinted.fill(Qt.GlobalColor.transparent)
        tp = QPainter(tinted)
        try:
            tp.drawImage(0, 0, img)
            tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            tp.fillRect(tinted.rect(), QColor(tint))
            tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            tp.drawImage(0, 0, img)
        finally:
            tp.end()
        img = tinted
    cache[key] = img
    return img

def _draw_icon_texture(p: QPainter, spec: dict, x: float, y: float,
                       size: float, shadow: bool) -> bool:
    """Draw the real game texture for an icon spec. Returns False to ask
    the caller for the vector fallback."""
    if shadow and spec.get("no_shadow"):
        return True  # game draws this icon without a shadow pass
    tint = "#000000" if shadow else spec.get("tint", "#ffffff")
    img = _tinted_icon_texture(spec["texture"], tint)
    if img is None:
        return False

    # Fit the texture into the 24px icon cell, preserving aspect ratio
    # (portal 40x40, rupee 40x64, Wii remote 24x30 all land in one cell).
    ratio = min(size / img.width(), size / img.height())
    w, h = img.width() * ratio, img.height() * ratio

    p.save()
    try:
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.translate(x + size / 2.0, y + size / 2.0)
        rot = int(spec.get("rot", 0))
        if rot:
            p.rotate(rot)
        if spec.get("flip_y"):
            p.scale(1.0, -1.0)
        p.drawImage(QRectF(-w / 2.0, -h / 2.0, w, h), img)
    finally:
        p.restore()

    # Direction arrows stay on top of the analog-stick texture: the game
    # animates the stick tilt, which a static preview cannot convey.  (The
    # Wii D-pad textures already carry their red direction marks.)  Drawn
    # as vectors — arrow glyphs are missing from many UI fonts.
    label = spec.get("label", "")
    if label and spec.get("kind") == "stick_direction" and not shadow:
        directions = {"↑": [(0, -1)], "↓": [(0, 1)], "←": [(-1, 0)], "→": [(1, 0)],
                      "↕": [(0, -1), (0, 1)], "↔": [(-1, 0), (1, 0)]}
        cx, cy = x + size / 2.0, y + size / 2.0
        for outline, color, width in ((True, "#000000", 0.16), (False, "#ffd24a", 0.08)):
            p.setPen(QPen(QColor(color), max(1.0, size * width),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for dx, dy in directions.get(label, []):
                tip_x, tip_y = cx + dx * size * 0.46, cy + dy * size * 0.46
                p.drawLine(QPoint(int(cx + dx * size * 0.1), int(cy + dy * size * 0.1)),
                           QPoint(int(tip_x), int(tip_y)))
                # arrowhead: two short strokes angled back from the tip
                px_, py_ = -dy, dx  # perpendicular
                back_x, back_y = tip_x - dx * size * 0.16, tip_y - dy * size * 0.16
                p.drawLine(QPoint(int(tip_x), int(tip_y)),
                           QPoint(int(back_x + px_ * size * 0.12), int(back_y + py_ * size * 0.12)))
                p.drawLine(QPoint(int(tip_x), int(tip_y)),
                           QPoint(int(back_x - px_ * size * 0.12), int(back_y - py_ * size * 0.12)))
    return True

def _draw_icon(p: QPainter, spec: dict, x: float, y: float, size: float, shadow: bool = False):
    """Draw an in-game inline icon.

    Specs come from the Zelda BMG tag catalogue.  When the spec carries a
    "texture" (a PNG decoded from the game's own BTI resources) it is drawn
    tinted exactly like COutFont_c does; the vector kind/label/color triple
    remains as a fallback when the texture file is unavailable.
    """
    kind = spec.get("kind", "char")
    if kind == "blank" or size <= 0:
        return

    if spec.get("texture") and _draw_icon_texture(
            p, spec, x, y, size, shadow):
        return

    body = QColor("#000000") if shadow else QColor(spec.get("color", "#c8c8c8"))
    fg = QColor("#000000") if shadow else QColor(spec.get("fg", "#ffffff"))
    rect = QRectF(x + size * 0.05, y + size * 0.05, size * 0.9, size * 0.9)

    def draw_label(label_rect: QRectF, ratio: float = 0.62):
        label = spec.get("label", "")
        if not label or shadow:
            return
        f = p.font()
        f.setBold(True)
        f.setPixelSize(max(4, int(size * ratio)))
        p.setFont(f)
        p.setPen(QPen(fg))
        p.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(body)

    if kind in ("circle", "rect", "wii_button", "nunchuk_button"):
        if kind == "circle":
            p.drawEllipse(rect)
        else:
            radius = size * (0.35 if kind in ("wii_button", "nunchuk_button") else 0.2)
            p.drawRoundedRect(rect, radius, radius)
        draw_label(rect)
    elif kind in ("trigger", "wii_trigger"):
        trigger = QRectF(x + size * 0.05, y + size * 0.22, size * 0.9, size * 0.58)
        p.drawRoundedRect(trigger, size * 0.16, size * 0.16)
        draw_label(trigger, 0.5)
    elif kind in ("dpad", "dpad_direction"):
        p.drawRoundedRect(QRectF(x + size * 0.36, y + size * 0.08,
                                 size * 0.28, size * 0.84), size * 0.05, size * 0.05)
        p.drawRoundedRect(QRectF(x + size * 0.08, y + size * 0.36,
                                 size * 0.84, size * 0.28), size * 0.05, size * 0.05)
        if kind == "dpad_direction" and not shadow:
            draw_label(QRectF(x, y, size, size), 0.46)
    elif kind in ("stick", "stick_direction"):
        p.drawEllipse(QRectF(x + size * 0.14, y + size * 0.14, size * 0.72, size * 0.72))
        if not shadow:
            p.setBrush(fg)
            p.drawEllipse(QRectF(x + size * 0.34, y + size * 0.34,
                                 size * 0.32, size * 0.32))
            draw_label(QRectF(x, y, size, size), 0.38)
    elif kind == "reticle":
        pen = QPen(body, max(1.0, size * 0.1))
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(x + size * 0.23, y + size * 0.23, size * 0.54, size * 0.54))
        p.drawLine(QPoint(int(x + size * 0.5), int(y + size * 0.02)),
                   QPoint(int(x + size * 0.5), int(y + size * 0.3)))
        p.drawLine(QPoint(int(x + size * 0.5), int(y + size * 0.7)),
                   QPoint(int(x + size * 0.5), int(y + size * 0.98)))
        p.drawLine(QPoint(int(x + size * 0.02), int(y + size * 0.5)),
                   QPoint(int(x + size * 0.3), int(y + size * 0.5)))
        p.drawLine(QPoint(int(x + size * 0.7), int(y + size * 0.5)),
                   QPoint(int(x + size * 0.98), int(y + size * 0.5)))
    elif kind == "wiimote":
        remote = QRectF(x + size * 0.28, y + size * 0.03, size * 0.44, size * 0.94)
        p.drawRoundedRect(remote, size * 0.16, size * 0.16)
        if not shadow:
            p.setBrush(fg)
            p.drawEllipse(QRectF(x + size * 0.43, y + size * 0.19,
                                 size * 0.14, size * 0.14))
            p.drawRect(QRectF(x + size * 0.39, y + size * 0.43,
                              size * 0.22, size * 0.06))
    elif kind == "nunchuk":
        path = QPainterPath()
        path.moveTo(x + size * 0.35, y + size * 0.05)
        path.cubicTo(x + size * 0.12, y + size * 0.2,
                     x + size * 0.18, y + size * 0.86,
                     x + size * 0.5, y + size * 0.96)
        path.cubicTo(x + size * 0.82, y + size * 0.86,
                     x + size * 0.88, y + size * 0.2,
                     x + size * 0.65, y + size * 0.05)
        path.closeSubpath()
        p.drawPath(path)
        if not shadow:
            p.setBrush(fg)
            p.drawEllipse(QRectF(x + size * 0.36, y + size * 0.18,
                                 size * 0.28, size * 0.2))
    elif kind == "button_star":
        p.drawEllipse(rect)
        draw_label(rect)
        if not shadow:
            p.setPen(QPen(QColor("#fff2a0")))
            f = p.font()
            f.setPixelSize(max(4, int(size * 0.32)))
            p.setFont(f)
            p.drawText(QRectF(x + size * 0.58, y, size * 0.4, size * 0.4),
                       Qt.AlignmentFlag.AlignCenter, "★")
    elif kind in ("diamond", "split_button", "bag"):
        # Compact symbolic forms for special game controls.
        if kind == "diamond":
            path = QPainterPath()
            path.moveTo(x + size * 0.5, y + size * 0.04)
            path.lineTo(x + size * 0.96, y + size * 0.5)
            path.lineTo(x + size * 0.5, y + size * 0.96)
            path.lineTo(x + size * 0.04, y + size * 0.5)
            path.closeSubpath()
            p.drawPath(path)
        elif kind == "bag":
            p.drawRoundedRect(QRectF(x + size * 0.16, y + size * 0.3,
                                     size * 0.68, size * 0.62), size * 0.18, size * 0.18)
            p.drawEllipse(QRectF(x + size * 0.32, y + size * 0.05,
                                 size * 0.36, size * 0.36))
        else:
            p.drawRoundedRect(rect, size * 0.2, size * 0.2)
            p.setPen(QPen(fg if not shadow else body, max(1.0, size * 0.06)))
            p.drawLine(QPoint(int(x + size * 0.5), int(y + size * 0.12)),
                       QPoint(int(x + size * 0.5), int(y + size * 0.88)))
            draw_label(rect, 0.42)
    else:  # "char": a single glyph drawn directly in the icon color
        label = spec.get("label", "")
        if not label:
            return
        f = p.font()
        f.setBold(True)
        f.setPixelSize(max(4, int(size * 0.9)))
        p.setFont(f)
        p.setPen(QPen(body))
        p.drawText(QRectF(x, y, size, size), Qt.AlignmentFlag.AlignCenter, label)
