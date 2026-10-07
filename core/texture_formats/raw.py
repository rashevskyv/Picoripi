"""Headerless textures at known offsets of a file (N64 textures inside a ROM file, banners...).

Params: ``pixel_format`` (a ``pixels`` codec name, e.g. ``n64:IA8``), ``width``, ``height`` and
either ``offset`` or ``textures`` -- a list of ``{name, offset}`` (each may override
``pixel_format``, ``width`` and ``height``). Numbers may be strings such as ``"0x1230"``.

``n64:CI4`` / ``n64:CI8`` index a palette (TLUT) of 16 / 256 RGBA16 entries at ``tlut_offset`` of the
same file (``tlut_count`` entries when the TLUT is shorter). Writing keeps the palette when every colour
of the new image is in it; otherwise a palette for the new image is written over it (a TLUT that other
textures share changes for them too).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

_TLUT_BITS = {"n64:CI4": 4, "n64:CI8": 8}


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _palette(data: bytes, entry: Dict[str, Any]) -> List[tuple]:
    decode, _encode = pixels.n64_tlut()
    count = entry["tlut_count"]
    return [decode(v) for v in struct.unpack_from(f">{count}H", data, entry["tlut"])]


def _codec(data: bytes, entry: Dict[str, Any]) -> pixels.Codec:
    if entry["bits"]:
        return pixels.palette_codec(entry["format"], entry["bits"], _palette(data, entry))
    return pixels.codec(entry["format"])


def _entries(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    listed = params.get("textures") or [{"name": params.get("name", ""), "offset": params.get("offset", 0)}]
    out = []
    for entry in listed:
        merged = {**params, **entry}
        fmt = str(merged["pixel_format"])
        out.append({"name": str(merged.get("name") or ""), "offset": _int(merged.get("offset", 0)),
                    "format": fmt, "bits": _TLUT_BITS.get(fmt, 0), "tlut": _int(merged.get("tlut_offset") or 0),
                    "tlut_count": _int(merged.get("tlut_count") or 1 << _TLUT_BITS.get(fmt, 0)),
                    "width": _int(merged["width"]), "height": _int(merged["height"])})
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(e["name"], surface.read(data, e["offset"], _codec(data, e), e["width"], e["height"]),
                    e["format"].split(":")[-1]) for e in _entries(params)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    entries = _entries(params)
    for index, image in images.items():
        e = entries[index]
        if e["bits"]:
            colours = {tuple(c) for _n, c in image.convert("RGBA").getcolors(1 << 24)}
            if not colours <= set(_palette(out, e)):
                _decode, encode = pixels.n64_tlut()
                new = pixels.nearest_palette(image, e["tlut_count"])
                values = [encode(*c) for c in new] + [0] * (e["tlut_count"] - len(new))
                struct.pack_into(f">{len(values)}H", out, e["tlut"], *values)
        surface.write(out, e["offset"], _codec(out, e), e["width"], e["height"], image)
    return bytes(out)
