"""The game's own picture, read from its image when a project is created: the 3DS SMDH icon or the GameCube banner.

``icon_png(path)`` returns PNG bytes, or None for an image without a picture this module reads (Switch, Wii, Nintendo
DS and loose folders are not read yet). It runs on a worker thread: it reads the image and builds a ``QImage``, never a
widget. The new project stores the picture as ``icon.png``; the Project Manager's Change icon replaces it.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import QImage

from core.containers.image_files import ImageError
from core.project_library import images
from utils.logging_utils import log_warning

SMDH_MAGIC = b"SMDH"
SMDH_LARGE_ICON_AT, SMDH_LARGE_ICON_SIDE = 0x24C0, 48       # 48x48 RGB565 in 8x8 tiles, Morton order inside a tile
BANNER_MAGIC = b"BNR"                                        # BNR1 (one language) or BNR2 (six)
BANNER_PICTURE_AT, BANNER_WIDTH, BANNER_HEIGHT = 0x20, 96, 32   # RGB5A3 in 4x4 tiles
ICON_ENTRIES = {images.KIND_3DS: "exefs/icon.bin", images.KIND_GC: "files/opening.bnr"}


def _image(width: int, height: int, pixel: Callable[[int, int], int]) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    for y in range(height):
        for x in range(width):
            image.setPixel(x, y, pixel(x, y))
    return image


def _morton(index: int) -> tuple:
    """The (x, y) of the ``index``-th pixel of an 8x8 tile stored in Morton (Z) order."""
    x = (index & 1) | ((index >> 1) & 2) | ((index >> 2) & 4)
    y = ((index >> 1) & 1) | ((index >> 2) & 2) | ((index >> 3) & 4)
    return x, y


def smdh_icon(data: bytes) -> Optional[QImage]:
    """The 48x48 icon of a 3DS SMDH block, or None when ``data`` is not one."""
    side = SMDH_LARGE_ICON_SIDE
    if data[:4] != SMDH_MAGIC or len(data) < SMDH_LARGE_ICON_AT + side * side * 2:
        return None
    colors = {}
    tiles_per_row = side // 8
    for tile in range(tiles_per_row * tiles_per_row):
        for index in range(64):
            value = struct.unpack_from("<H", data, SMDH_LARGE_ICON_AT + (tile * 64 + index) * 2)[0]
            dx, dy = _morton(index)
            red, green, blue = (value >> 11) & 0x1F, (value >> 5) & 0x3F, value & 0x1F
            colors[((tile % tiles_per_row) * 8 + dx, (tile // tiles_per_row) * 8 + dy)] = (
                0xFF000000 | (red * 255 // 31) << 16 | (green * 255 // 63) << 8 | blue * 255 // 31)
    return _image(side, side, lambda x, y: colors[(x, y)])


def _rgb5a3(value: int) -> int:
    if value & 0x8000:
        red, green, blue = (value >> 10) & 0x1F, (value >> 5) & 0x1F, value & 0x1F
        return 0xFF000000 | (red * 255 // 31) << 16 | (green * 255 // 31) << 8 | blue * 255 // 31
    alpha = ((value >> 12) & 7) * 255 // 7
    return alpha << 24 | ((value >> 8) & 0xF) * 17 << 16 | ((value >> 4) & 0xF) * 17 << 8 | (value & 0xF) * 17


def banner_picture(data: bytes) -> Optional[QImage]:
    """The 96x32 picture of a GameCube ``opening.bnr``, or None when ``data`` is not a banner."""
    if data[:3] != BANNER_MAGIC or len(data) < BANNER_PICTURE_AT + BANNER_WIDTH * BANNER_HEIGHT * 2:
        return None
    colors = {}
    tiles_per_row = BANNER_WIDTH // 4
    for tile in range(tiles_per_row * (BANNER_HEIGHT // 4)):
        for index in range(16):
            value = struct.unpack_from(">H", data, BANNER_PICTURE_AT + (tile * 16 + index) * 2)[0]
            colors[((tile % tiles_per_row) * 4 + index % 4, (tile // tiles_per_row) * 4 + index // 4)] = _rgb5a3(value)
    return _image(BANNER_WIDTH, BANNER_HEIGHT, lambda x, y: colors[(x, y)])


def _png(image: QImage) -> Optional[bytes]:
    buffer_bytes = QByteArray()
    buffer = QBuffer(buffer_bytes)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    saved = image.save(buffer, "PNG")
    buffer.close()
    return bytes(buffer_bytes.data()) if saved else None


def icon_png(path: str) -> Optional[bytes]:
    """PNG bytes of the game's picture in the image ``path``, or None. A broken or unread image gives None."""
    if not path or Path(path).is_dir():
        return None
    kind = (images.identify(path) or {}).get("kind")
    entry_path = ICON_ENTRIES.get(kind)
    if entry_path is None:
        return None
    try:
        with images.open_image(path) as reader:
            entry = next((item for item in reader.entries() if item.path == entry_path), None)
            data = reader.read(entry) if entry is not None else b""
    except (ImageError, OSError, ValueError, struct.error) as exc:
        log_warning(f"The game's icon could not be read from {path}: {exc}")
        return None
    picture = smdh_icon(data) if kind == images.KIND_3DS else banner_picture(data)
    return _png(picture) if picture is not None else None
