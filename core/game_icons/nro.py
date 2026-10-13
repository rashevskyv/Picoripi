"""Nintendo Switch NRO homebrew: the icon (JPEG) of its ``ASET`` asset section, appended after the NRO image."""
from __future__ import annotations

import io
import struct
from typing import Optional

from PIL import Image

from core.game_icons.common import FileSource

NRO_MAGIC_AT, NRO_SIZE_AT = 0x10, 0x18
ASSET_MAGIC, ASSET_HEADER = b"ASET", 0x38


def read(src: FileSource) -> Optional[Image.Image]:
    if src.size < 0x40 or src.take(NRO_MAGIC_AT, 4) != b"NRO0":
        return None
    (nro_size,) = struct.unpack("<I", src.take(NRO_SIZE_AT, 4))
    if nro_size + ASSET_HEADER > src.size or src.take(nro_size, 4) != ASSET_MAGIC:
        return None
    asset = src.take(nro_size, ASSET_HEADER)
    icon_at, icon_size = struct.unpack_from("<QQ", asset, 8)   # relative to the ASET header
    if icon_size == 0 or nro_size + icon_at + icon_size > src.size:
        return None
    data = src.take(nro_size + icon_at, icon_size)
    return Image.open(io.BytesIO(data))
