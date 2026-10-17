"""Fonts and pictures of the Brilliant Diamond / Shining Pearl bundles, as the workspace source holds them.

Font bundles (``Dpr/font/<name>``): a TextMesh Pro font asset (a MonoBehaviour with a glyph table and an atlas) is written as
its type tree (``<asset>.json``, the same JSON as the message tables) and its atlas (the Alpha8 texture of the asset, as a grey
PNG); a Unity ``Font`` is written as its font file (``.otf`` when it starts with ``OTTO``, else ``.ttf``).

Every other picture bundle: each Texture2D is written as a PNG under ``texture/<bundle>/``. Texture formats decode through the
project's codecs (``core.texture_formats.pixels``): Alpha8, RGBA32, RGB24, BC1 (DXT1), BC3 (DXT5), ASTC 4x4 and 6x6.
Other formats raise ``UnsupportedTexture``; the caller reports them.
"""
from __future__ import annotations

import io
import re
from typing import Dict, Iterator, Tuple

from PIL import Image

from core.texture_formats import pixels
from core.unity.serialized import SerializedFile
from core.unity.unityfs import Bundle
from plugins.pokemon_bdsp import bundles

TEXTURE2D = 28
FONT = 128
MONOBEHAVIOUR = 114
ASSETS = "/Data/StreamingAssets/AssetAssistant/"
# The bundles the workspace holds (zt's selection): message tables, font bundles, and the English picture bundles.
BUNDLES = re.compile(r"^" + ASSETS + r"(Message/(english|common_msbt)$|Dpr/font/[a-z_]+$"
                     r"|UIs/textures/field/firstboot$|(?!Audio/).*(\.en|_en|_en_op_pushbutton)$)")
FONT_FOLDER = "Dpr/font/"
# Texture2D.m_TextureFormat -> (codec name, bytes per block, block width, block height); 1 and 4 are raw.
FORMATS = {
    1: ("A8", 1, 1, 1),
    3: ("RGB24", 3, 1, 1),
    4: ("RGBA32", 4, 1, 1),
    10: ("BC1", 8, 4, 4),
    12: ("BC3", 16, 4, 4),
    48: ("ASTC4x4", 16, 4, 4),
    50: ("ASTC6x6", 16, 6, 6),
}


class UnsupportedTexture(ValueError):
    """A Texture2D of a format this module does not decode."""


def is_picture_bundle(romfs_path: str) -> bool:
    """True for a bundle the workspace keeps (zt's selection), given its path inside the romfs (``/Data/...``)."""
    return BUNDLES.search(romfs_path) is not None


def short_name(romfs_path: str) -> str:
    """The bundle path under ``AssetAssistant`` (``Dpr/font/efigs_font``), as the workspace folder names it."""
    return romfs_path[len(ASSETS):] if romfs_path.startswith(ASSETS) else romfs_path


def safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "unnamed"


def png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def open_serialized(data: bytes) -> Tuple[Bundle, SerializedFile]:
    """The bundle and its serialized file (the one entry that is not a ``.resS`` stream)."""
    bundle = Bundle(data)
    names = [node.name for node in bundle.nodes if not node.name.endswith(".resS")]
    if len(names) != 1:
        raise ValueError("a picture bundle holds one serialized file")
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
        raise UnsupportedTexture(f"texture format {fmt} is not decoded")
    codec, block_bytes, bw, bh = FORMATS[fmt]
    inline = value.get("image data")
    raw = bytes(inline) if inline else _stream(bundle, value.get("m_StreamData") or {})
    if width == 0 or height == 0:
        raise UnsupportedTexture("texture has no size")
    if fmt in (1, 3, 4):
        size = width * height * block_bytes
        data = raw[:size]
        if len(data) != size:
            raise UnsupportedTexture("texture data is shorter than its size")
        if fmt == 1:
            return Image.frombytes("L", (width, height), data).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        mode = "RGB" if fmt == 3 else "RGBA"
        return Image.frombytes(mode, (width, height), data).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    blocks = ((width + bw - 1) // bw) * ((height + bh - 1) // bh)
    data = raw[:blocks * block_bytes]
    if len(data) != blocks * block_bytes:
        raise UnsupportedTexture("texture data is shorter than its blocks")
    return pixels.codec(codec).decode(data, width, height).transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def font_files(bundle: Bundle, serialized: SerializedFile, folder: str) -> Iterator[Tuple[str, bytes]]:
    """(workspace path, bytes) of the font assets and font files of one ``Dpr/font`` bundle."""
    for obj in serialized.objects:
        if obj.class_id == FONT:
            value = serialized.read(obj.path_id)
            data = bytes(value.get("m_FontData") or [])
            if not data:
                continue
            ext = ".otf" if data[:4] == b"OTTO" else ".ttf"
            yield f"{folder}/{safe(value.get('m_Name', ''))}{ext}", data
        elif obj.class_id == MONOBEHAVIOUR:
            value = serialized.read(obj.path_id)
            if not value.get("m_GlyphTable") or not value.get("m_AtlasTextures"):
                continue        # the dynamic fallback asset: its atlas is filled at run time
            stem = f"{folder}/{safe(value.get('m_Name', ''))}"
            atlas_id = value["m_AtlasTextures"][0]["m_PathID"]
            atlas = texture_image(bundle, serialized.read(atlas_id))
            yield f"{stem}.json", bundles.table_json(value)
            yield f"{stem}.png", png(atlas)


def texture_objects(serialized: SerializedFile, folder: str) -> Iterator[Tuple[str, int, dict]]:
    """(workspace path, path id, value) of each Texture2D of one picture bundle; names repeat with ``~n`` like zt's."""
    seen: Dict[str, int] = {}
    for obj in serialized.objects:
        if obj.class_id != TEXTURE2D:
            continue
        value = serialized.read(obj.path_id)
        if not value.get("m_Width"):
            continue
        stem = safe(value.get("m_Name", ""))
        name = f"{folder}/{stem}.png"
        if name in seen:
            seen[name] += 1
            name = f"{folder}/{stem}~{seen[name]}.png"
        else:
            seen[name] = 1
        yield name, obj.path_id, value


def texture_files(bundle: Bundle, serialized: SerializedFile, folder: str) -> Iterator[Tuple[str, bytes]]:
    """(workspace path, PNG bytes) of each Texture2D of one picture bundle."""
    for name, _path_id, value in texture_objects(serialized, folder):
        yield name, png(texture_image(bundle, value))


def encode_texture(value: dict, picture: Image.Image) -> bytes:
    """The data of a Texture2D value for the workspace PNG ``picture`` (the inverse of ``texture_image``).

    The picture keeps the size of the texture. Raw formats are stored as they are; block formats go through their codec.
    """
    width, height = int(value.get("m_Width", 0)), int(value.get("m_Height", 0))
    fmt = int(value.get("m_TextureFormat", -1))
    if fmt not in FORMATS:
        raise UnsupportedTexture(f"texture format {fmt} is not encoded")
    if picture.size != (width, height):
        raise UnsupportedTexture(f"picture is {picture.size[0]}x{picture.size[1]}, the texture is {width}x{height}")
    codec_name = FORMATS[fmt][0]
    flipped = picture.transpose(Image.Transpose.FLIP_TOP_BOTTOM)   # texture_image flips the decoded picture back
    if fmt in (1, 3, 4):
        mode = {1: "L", 3: "RGB", 4: "RGBA"}[fmt]
        return flipped.convert(mode).tobytes()
    return pixels.codec(codec_name).encode(flipped.convert("RGBA"))
