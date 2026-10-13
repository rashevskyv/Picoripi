"""Project icons: read an image, scale it, and write a PNG atomically. Runs on a worker or in the scan process.

``QImage`` needs no application object, so the scan child and the window's worker both use it without a window.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

ICON_SIZE = 128  # the largest size the list and grid show
USER_ICON_MAX = 256  # a user's image is scaled to this before it is stored as icon.png


def _scaled(image: QImage, size: int) -> QImage:
    return image.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def _write_png(image: QImage, target: Path) -> bool:
    """Save a PNG beside ``target`` and rename it into place. False when the write fails."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        if not image.save(str(temporary), "PNG"):
            return False
        os.replace(temporary, target)
        return True
    except OSError:
        return False
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def scale_image_file(source: Path, target: Path, size: int) -> bool:
    """Scale the image file ``source`` to fit ``size`` and write it to ``target`` as PNG. False when unreadable."""
    image = QImage(str(source))
    if image.isNull():
        return False
    return _write_png(_scaled(image, size), target)


def scale_image_bytes(data: bytes, target: Path, size: int) -> bool:
    """The same for an image held in memory (a plugin's icon)."""
    image = QImage.fromData(data)
    if image.isNull():
        return False
    return _write_png(_scaled(image, size), target)


def save_user_icon(source: Path, target: Path) -> Optional[QImage]:
    """Store a user's picture as the project's icon.png (at most USER_ICON_MAX px). The scaled image, or None."""
    image = QImage(str(source))
    if image.isNull():
        return None
    scaled = _scaled(image, USER_ICON_MAX)
    return scaled if _write_png(scaled, target) else None


IMAGE_FILTER = "*.png *.jpg *.jpeg *.bmp *.gif *.webp"  # the file types the icon dialogs offer


def load_image(source: Path) -> Optional[QImage]:
    """The picture at ``source`` as a QImage (decoded here, on the caller's worker). None when it cannot be read."""
    image = QImage(str(source))
    return None if image.isNull() else image
