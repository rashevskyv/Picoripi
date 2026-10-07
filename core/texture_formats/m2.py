"""M2 (emote) PSB pictures: the textures of a PSB (motion, image or font file of Metal Gear Solid Master
Collection).

Every ``{type, width, height, pixel}`` object in the PSB tree is a texture; ``pixel`` is a resource of raw
pixels in rows: ``RGBA8`` (bytes B, G, R, A on PC), ``A8L8`` (bytes L, A), ``A8``, ``L8``. A texture is named
by its place in the tree (``source/tex/texture``). Writing changes the resource's bytes in place: the file
keeps its size and every other byte.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from PIL import Image

from core import m2_psb
from core.texture_formats import Texture, pixels, surface

CODECS = {"RGBA8": "BGRA8", "A8L8": "LA8", "A8": "A8", "L8": "L8"}


def detect(data: bytes) -> bool:
    return bytes(data[:3]) == b"PSB" and len(data) > 4 and data[3] == 0 and bool(_textures(data))


def _textures(data: bytes) -> List[Tuple[str, Dict[str, Any], int]]:
    """``[(name, texture object, resource offset in the file)]``"""
    try:
        root, psb = m2_psb.load(bytes(data))
    except (ValueError, IndexError, KeyError, UnicodeDecodeError):
        return []
    found: List[Tuple[str, Dict[str, Any], int]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("pixel"), m2_psb.Res) and "type" in value and "width" in value:
                found.append((path.strip("/"), value, psb.chunk_spans[int(value["pixel"])][0]))
                return
            for key, item in value.items():
                walk(item, f"{path}/{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}/{index}")

    walk(root, "")
    return found


def _codec(kind: str):
    if kind not in CODECS:
        raise ValueError(f"M2 picture format {kind} is not supported ({', '.join(CODECS)} are)")
    return pixels.codec(CODECS[kind])


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(name, surface.read(data, offset, _codec(t["type"]), int(t["width"]), int(t["height"])), t["type"])
            for name, t, offset in _textures(data)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    found = _textures(data)
    for index, image in images.items():
        _name, t, offset = found[index]
        surface.write(out, offset, _codec(t["type"]), int(t["width"]), int(t["height"]), image)
    return bytes(out)
