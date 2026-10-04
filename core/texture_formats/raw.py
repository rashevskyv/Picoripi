"""Headerless textures at known offsets of a file (N64 textures inside a ROM file, banners...).

Params: ``pixel_format`` (a ``pixels`` codec name, e.g. ``n64:IA8``), ``width``, ``height`` and
either ``offset`` or ``textures`` -- a list of ``{name, offset}`` (each may override
``pixel_format``, ``width`` and ``height``). Numbers may be strings such as ``"0x1230"``.
"""
from __future__ import annotations

from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _entries(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    listed = params.get("textures") or [{"name": params.get("name", ""), "offset": params.get("offset", 0)}]
    out = []
    for entry in listed:
        merged = {**params, **entry}
        out.append({"name": str(merged.get("name") or ""), "offset": _int(merged.get("offset", 0)),
                    "codec": pixels.codec(str(merged["pixel_format"])), "format": str(merged["pixel_format"]),
                    "width": _int(merged["width"]), "height": _int(merged["height"])})
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(e["name"], surface.read(data, e["offset"], e["codec"], e["width"], e["height"]),
                    e["format"].split(":")[-1]) for e in _entries(params)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    entries = _entries(params)
    for index, image in images.items():
        e = entries[index]
        surface.write(out, e["offset"], e["codec"], e["width"], e["height"], image)
    return bytes(out)
