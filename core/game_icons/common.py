"""Shared helpers of the game icon readers: a read-only file window and the final icon size rule."""
from __future__ import annotations

import os
from typing import Optional

from PIL import Image

MIN_SIDE = 64    # a smaller icon is enlarged by a whole factor until its long side reaches this
MAX_SIDE = 256   # a larger icon is shrunk to this long side


class FileSource:
    """A file read in small windows, so a multi-gigabyte disc or ROM is never loaded whole."""

    def __init__(self, path: str) -> None:
        self.path = os.fspath(path)
        self.size = os.path.getsize(self.path)

    def take(self, offset: int, size: int) -> bytes:
        """``size`` bytes at ``offset``; ValueError when the file ends first."""
        if offset < 0 or size < 0 or offset + size > self.size:
            raise ValueError("read past the end of the file")
        with open(self.path, "rb") as handle:
            handle.seek(offset)
            return handle.read(size)


def finish(image: Image.Image) -> Optional[Image.Image]:
    """RGBA icon, long side 64..256 px; None when the picture is blank or has one colour only."""
    img = image.convert("RGBA")
    if len(set(img.getdata())) < 2:
        return None
    long_side = max(img.size)
    if long_side > MAX_SIDE:
        scale = MAX_SIDE / long_side
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                         Image.Resampling.LANCZOS)
    long_side = max(img.size)
    if long_side < MIN_SIDE:
        factor = min(-(-MIN_SIDE // long_side), MAX_SIDE // long_side)
        img = img.resize((img.width * factor, img.height * factor), Image.Resampling.NEAREST)
    return img
