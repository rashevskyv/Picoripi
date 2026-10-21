"""Fonts and pictures of the Brilliant Diamond / Shining Pearl bundles, as the workspace source holds them.

Font bundles (``Dpr/font/<name>``): a TextMesh Pro font asset (a MonoBehaviour with a glyph table and an atlas) is written as
its type tree (``<asset>.json``, the same JSON as the message tables) and its atlas (the Alpha8 texture of the asset, as a grey
PNG); a Unity ``Font`` is written as its font file (``.otf`` when it starts with ``OTTO``, else ``.ttf``).

Every other picture bundle: each Texture2D is written as a PNG under ``texture/<bundle>/``. Texture formats decode through the
project's codecs (``core.texture_formats.pixels``): Alpha8, RGBA32, RGB24, BC1 (DXT1), BC3 (DXT5), ASTC 4x4 and 6x6.
Other formats raise ``UnsupportedTexture``; the caller reports them.
"""
from __future__ import annotations

import re
from typing import Dict, Iterator, Tuple

from core.unity.assets import (FONT, FORMATS, MONOBEHAVIOUR, TEXTURE2D, UnsupportedTexture,  # noqa: F401 (re-exports)
                               encode_texture, open_serialized, png, texture_image)
from core.unity.serialized import SerializedFile
from core.unity.unityfs import Bundle
from plugins.pokemon_bdsp import bundles

ASSETS = "/Data/StreamingAssets/AssetAssistant/"
# The bundles the workspace holds (zt's selection): message tables, font bundles, and the English picture bundles.
BUNDLES = re.compile(r"^" + ASSETS + r"(Message/(english|common_msbt)$|Dpr/font/[a-z_]+$"
                     r"|UIs/textures/field/firstboot$|(?!Audio/).*(\.en|_en|_en_op_pushbutton)$)")
FONT_FOLDER = "Dpr/font/"


def is_picture_bundle(romfs_path: str) -> bool:
    """True for a bundle the workspace keeps (zt's selection), given its path inside the romfs (``/Data/...``)."""
    return BUNDLES.search(romfs_path) is not None


def short_name(romfs_path: str) -> str:
    """The bundle path under ``AssetAssistant`` (``Dpr/font/efigs_font``), as the workspace folder names it."""
    return romfs_path[len(ASSETS):] if romfs_path.startswith(ASSETS) else romfs_path


def safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "unnamed"


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
