"""Game textures as editable RGBA images, with one backend per file format.

A backend module has ``read(data, params) -> [Texture]`` and ``write(data, images, params) -> bytes``
(``images``: texture index -> new RGBA image of the same size). Writing changes the pixel data in
place -- the file keeps its size, header and every texture that was not given -- and regenerates the
mip levels of a texture whose image changed. Writing the images ``read`` returned gives the original
bytes back. ``params`` are what the plugin's texture source says about the file (see ``sources``).

Pixel formats live in ``pixels`` (one ``Codec`` each), the element walk in ``surface``, the
console tilings in ``gx2`` (Wii U) and ``tegra`` (Switch).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from PIL import Image


@dataclass
class Texture:
    """One texture of a file: its name there ("" when the file has one), image, pixel format, mip count."""

    name: str
    image: Image.Image
    pixel_format: str
    mipmaps: int = 1


def _backends() -> Dict[str, Any]:
    from core.texture_formats import (bfres, bntx, bti, ctpk, ctxb, flim, g1t, g4tx, gba, gim, gtx, imgc, j3d, m2, pcx, png,
                                      policenauts_pak, raw, shpg, tiles, tim, tpl, txtr, txtr_gx, vagrant)
    return {"bti": bti, "bflim": flim, "ctpk": ctpk, "ctxb": ctxb, "tpl": tpl, "bntx": bntx, "g1t": g1t, "g4tx": g4tx,
            "imgc": imgc, "j3d": j3d, "gba": gba, "gtx": gtx, "txtr": txtr, "gim": gim, "raw": raw, "tiles": tiles,
            "txtr_gx": txtr_gx, "tim": tim, "policenauts_pak": policenauts_pak,
            "vs_gim": vagrant.gim, "vs_hf1": vagrant.hf1, "vs_rle": vagrant.rle, "pcx": pcx, "m2": m2,
            "bfres": bfres, "shpg": shpg, "png": png}


# File name extension -> format, for files opened directly.
EXTENSIONS = {".bti": "bti", ".bflim": "bflim", ".bclim": "bflim", ".bntx": "bntx", ".ctpk": "ctpk", ".ctxb": "ctxb", ".tpl": "tpl", ".g1t": "g1t",
              ".xi": "imgc", ".bmd": "j3d", ".bdl": "j3d", ".gtx": "gtx", ".ncgr": "tiles", ".txtr": "txtr", ".gim": "gim", ".fcha": "gim",
              ".tim": "tim", ".pcx": "pcx", ".psb": "m2", ".m2tex": "m2", ".g4tx": "g4tx", ".bfres": "bfres", ".gsh": "shpg"}


def formats() -> List[str]:
    return list(_backends())


def _backend(fmt: str):
    try:
        return _backends()[fmt]
    except KeyError:
        raise ValueError(f"Texture format {fmt!r} is not supported ({', '.join(_backends())} are)") from None


def read(fmt: str, data: bytes, params: Optional[Dict[str, Any]] = None) -> List[Texture]:
    """The textures of a file."""
    return _backend(fmt).read(bytes(data), dict(params or {}))


def write(fmt: str, data: bytes, images: Dict[int, Image.Image], params: Optional[Dict[str, Any]] = None) -> bytes:
    """The file with the given textures replaced (same sizes)."""
    return _backend(fmt).write(bytes(data), images, dict(params or {}))


def detect(data: bytes, name: str = "") -> Optional[str]:
    """The format of a texture file, by its magic or else its file name."""
    for fmt, backend in _backends().items():
        probe = getattr(backend, "detect", None)
        if probe is not None and probe(data):
            return fmt
    import os
    return EXTENSIONS.get(os.path.splitext(name)[1].lower())
