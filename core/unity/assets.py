"""Unity assets shared by the game plugins: a bundle's serialized file, its Texture2D pictures and their encoding.

``texture_image`` decodes a Texture2D value (its inline data or its bundle stream) to a PIL image: Alpha8 as ``L``, RGB,
RGBA, and the block formats BC1, BC3 and ASTC through ``core.texture_formats.pixels``. ``encode_texture`` writes a picture
back in the texture's own format and size. ``inline_texture`` gives a texture a new size, as Alpha8 inline data (a font
atlas that grows: its stream is dropped, as the SWUK mod's atlases are stored).
"""
from __future__ import annotations

import io
from typing import Dict, Tuple

from PIL import Image

from core.i18n import tr
from core.texture_formats import pixels
from core.unity.serialized import SerializedFile
from core.unity.unityfs import Bundle

TEXTURE2D = 28
FONT = 128
MONOBEHAVIOUR = 114
# Texture2D.m_TextureFormat -> (codec name, bytes per block, block width, block height); 1, 3 and 4 are raw.
FORMATS: Dict[int, Tuple[str, int, int, int]] = {
    1: ("A8", 1, 1, 1),
    3: ("RGB24", 3, 1, 1),
    4: ("RGBA32", 4, 1, 1),
    10: ("BC1", 8, 4, 4),
    12: ("BC3", 16, 4, 4),
    48: ("ASTC4x4", 16, 4, 4),
    50: ("ASTC6x6", 16, 6, 6),
}
_STREAM_SUFFIXES = (".resS", ".res", ".resource")


class UnsupportedTexture(ValueError):
    """A Texture2D of a format this module does not decode or encode."""


def png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def open_serialized(data: bytes) -> Tuple[Bundle, SerializedFile]:
    """The bundle and its serialized file (the one entry that is not a stream file)."""
    bundle = Bundle(data)
    names = [node.name for node in bundle.nodes if not node.name.endswith(_STREAM_SUFFIXES)]
    if len(names) != 1:
        raise ValueError(tr("a bundle holds one serialized file"))
    return bundle, SerializedFile(bundle.read(names[0]))


def _stream(bundle: Bundle, stream: dict) -> bytes:
    name = str(stream.get("path", "")).split("/")[-1]
    data = bundle.read(name)
    offset, size = int(stream.get("offset", 0)), int(stream.get("size", 0))
    return data[offset:offset + size]


def texture_image(bundle: Bundle, value: dict) -> Image.Image:
    """The picture of one Texture2D value (its data inline or in the bundle's stream file), as RGBA (Alpha8: L)."""
    width, height = int(value.get("m_Width", 0)), int(value.get("m_Height", 0))
    fmt = int(value.get("m_TextureFormat", -1))
    if fmt not in FORMATS:
        raise UnsupportedTexture(tr("texture format {0} is not decoded", fmt))
    codec, block_bytes, bw, bh = FORMATS[fmt]
    inline = value.get("image data")
    raw = bytes(inline) if inline else _stream(bundle, value.get("m_StreamData") or {})
    if width == 0 or height == 0:
        raise UnsupportedTexture(tr("texture has no size"))
    if fmt in (1, 3, 4):
        size = width * height * block_bytes
        data = raw[:size]
        if len(data) != size:
            raise UnsupportedTexture(tr("texture data is shorter than its size"))
        if fmt == 1:
            return Image.frombytes("L", (width, height), data).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        mode = "RGB" if fmt == 3 else "RGBA"
        return Image.frombytes(mode, (width, height), data).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    blocks = ((width + bw - 1) // bw) * ((height + bh - 1) // bh)
    data = raw[:blocks * block_bytes]
    if len(data) != blocks * block_bytes:
        raise UnsupportedTexture(tr("texture data is shorter than its blocks"))
    return pixels.codec(codec).decode(data, width, height).transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def encode_texture(value: dict, picture: Image.Image) -> bytes:
    """The data of a Texture2D value for ``picture`` (the inverse of ``texture_image``).

    The picture keeps the size of the texture. Raw formats are stored as they are; block formats go through their codec.
    """
    width, height = int(value.get("m_Width", 0)), int(value.get("m_Height", 0))
    fmt = int(value.get("m_TextureFormat", -1))
    if fmt not in FORMATS:
        raise UnsupportedTexture(tr("texture format {0} is not encoded", fmt))
    if picture.size != (width, height):
        raise UnsupportedTexture(tr("picture is {0}x{1}, the texture is {2}x{3}",
                                    picture.size[0], picture.size[1], width, height))
    codec_name = FORMATS[fmt][0]
    flipped = picture.transpose(Image.Transpose.FLIP_TOP_BOTTOM)   # texture_image flips the decoded picture back
    if fmt in (1, 3, 4):
        mode = {1: "L", 3: "RGB", 4: "RGBA"}[fmt]
        return flipped.convert(mode).tobytes()
    return pixels.codec(codec_name).encode(flipped.convert("RGBA"))


def inline_texture(value: dict, picture: Image.Image) -> dict:
    """The Texture2D value with ``picture`` as inline Alpha8 data, at the picture's size; its stream is dropped.

    Only an Alpha8 texture (format 1) can change size this way: the value keeps its name and format.
    """
    if int(value.get("m_TextureFormat", -1)) != 1:
        raise UnsupportedTexture(tr("only an Alpha8 texture can change its size"))
    width, height = picture.size
    changed = dict(value)
    changed["m_Width"], changed["m_Height"] = width, height
    changed["m_CompleteImageSize"] = width * height
    changed["image data"] = picture.convert("L").transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
    changed["m_StreamData"] = {"offset": 0, "size": 0, "path": ""}
    return changed
