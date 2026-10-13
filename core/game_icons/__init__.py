"""Game icons read from a game's own files: ``extract_icon(path)`` names the format and returns an RGBA picture.

Pure readers, one module per container format: ``smdh`` (3DS), ``nds`` (DS ROM), ``bnr`` and ``gc_disc``
(GameCube), ``wii`` (Wii channel banner), ``nro`` (Switch homebrew), ``pe`` (Windows exe), ``pbp`` and ``iso9660``
(PSP). No file is written and no key is read here; a caller that needs a decrypted input passes that file.
"""
from __future__ import annotations

import io
import os
import struct
from dataclasses import dataclass
from typing import Optional

from PIL import Image

from core.game_icons import bnr, gc_disc, iso9660, nds, nro, pbp, pe, smdh, wii
from core.game_icons.common import FileSource, finish

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tga", ".bmp")


@dataclass(frozen=True)
class Icon:
    """The format name (e.g. ``3ds-smdh``), the picture as RGBA, and the source file."""

    format: str
    image: Image.Image
    source: str


def _wrap(fmt: str, picture: Optional[Image.Image], path: str) -> Optional[Icon]:
    if picture is None:
        return None
    done = finish(picture)
    return None if done is None else Icon(fmt, done, path)


def _read_gc_disc(src: FileSource) -> Optional[Image.Image]:
    where = gc_disc.find_banner(src)
    return None if where is None else bnr.read(src.take(*where))


def _read_psp_iso(src: FileSource) -> Optional[Image.Image]:
    data = iso9660.find(src, ["PSP_GAME", "ICON0.PNG"])
    return None if data is None else Image.open(io.BytesIO(data))


def extract_icon(path: str) -> Optional[Icon]:
    """The icon of a game file, or None when the format is not supported or the file has no icon."""
    path = os.fspath(path)
    name = os.path.basename(path).lower()
    ext = os.path.splitext(name)[1]
    try:
        if ext in IMAGE_EXTENSIONS:
            with Image.open(path) as opened:
                fmt = "wiiu-icontex" if name == "icontex.tga" else "image-file"
                return _wrap(fmt, opened.copy(), path)
        src = FileSource(path)
        if src.size < 0x40:
            return None
        head = src.take(0, 4)
        if head == smdh.MAGIC:
            return _wrap("3ds-smdh", smdh.read(src), path)
        if head in bnr.MAGICS:
            return _wrap("gc-bnr", bnr.read(src.take(0, min(src.size, bnr.SIZE))), path)
        if src.take(0x10, 4) == b"NRO0":
            return _wrap("switch-nro-asset", nro.read(src), path)
        if head[:2] == b"MZ":
            return _wrap("pc-exe-icon", pe.read(src), path)
        if head == pbp.MAGIC:
            return _wrap("psp-pbp-icon0", pbp.read(src), path)
        if gc_disc.is_gamecube(src):
            return _wrap("gc-disc-bnr", _read_gc_disc(src), path)
        if src.take(0x40, 4) == b"IMET":
            return _wrap("wii-banner-icon", wii.read(src.take(0, min(src.size, 8 << 20))), path)
        if ext == ".nds":
            return _wrap("nds-banner", nds.read(src), path)
        if src.size > 0x8800 and src.take(0x8001, 5) == b"CD001":
            return _wrap("psp-iso-icon0", _read_psp_iso(src), path)
    except (ValueError, OSError, struct.error):
        return None
    return None
