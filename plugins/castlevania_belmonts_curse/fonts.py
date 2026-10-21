"""The TextMesh Pro font assets of ``fonts-latin`` (Castlevania: Belmont's Curse, Switch) as project files.

The bundle holds two TextMesh Pro SDF font assets, NotoSans_Latin and LatinFont. Each is one pair of project files in
``font\\fonts-latin\\``: ``<asset>.json`` (the whole MonoBehaviour, written as the ``tmp_sdf`` format writes it) and
``<asset>.png`` (the atlas: the grey distance field). Font Editor opens a pair as a ``tmp_sdf`` source (font_sources.json).

A build writes a changed pair back: the MonoBehaviour from the JSON, and the atlas as Alpha8 data inside the object (the
atlas may change size: its stream is then dropped, as the SWUK mod stores its atlases).
"""
from __future__ import annotations

import io
import json
import re
from typing import Dict, Optional, Tuple

from PIL import Image

from core.font_formats import tmp_sdf
from core.i18n import tr
from core.unity.assets import MONOBEHAVIOUR, inline_texture, open_serialized, png, texture_image

FONT_BUNDLE = re.compile(r"^Data/StreamingAssets/aa/Switch/fonts-latin_assets_all_[0-9a-f]+\.bundle$")
FOLDER = "font/fonts-latin"        # the project's folder for the pairs, relative to the source (or translation) folder
# The font's JSON file has this suffix, not .json: the project scans every .json under the source folder as a text block.
SUFFIX = ".tmpfont"
Pair = Tuple[bytes, bytes]         # (JSON, PNG) of one font asset


def _is_font(value: dict) -> bool:
    return bool(value.get("m_GlyphTable")) and bool(value.get("m_AtlasTextures"))


def font_pairs(data: bytes) -> Dict[str, Pair]:
    """asset name -> (JSON, PNG) for each TextMesh Pro font asset of the bundle."""
    bundle, serialized = open_serialized(data)
    pairs: Dict[str, Pair] = {}
    for obj in serialized.objects:
        if obj.class_id != MONOBEHAVIOUR:
            continue
        value = serialized.read(obj.path_id)
        if not _is_font(value):
            continue
        atlas = serialized.read(value["m_AtlasTextures"][0]["m_PathID"])
        pairs[str(value.get("m_Name"))] = (tmp_sdf.dump(value), png(texture_image(bundle, atlas)))
    return pairs


def build_font_bundle(data: bytes, pairs: Dict[str, Pair]) -> Optional[bytes]:
    """The font bundle with each named asset replaced by its pair; None when no asset changes.

    The MonoBehaviour is written whole from the JSON: its keys must be the asset's own. Its atlas reference must name the
    atlas of the bundle. The atlas becomes inline Alpha8 data at the picture's size.
    """
    bundle, serialized = open_serialized(data)
    current = font_pairs(data)
    edits: Dict[int, bytes] = {}
    for obj in serialized.objects:
        if obj.class_id != MONOBEHAVIOUR:
            continue
        value = serialized.read(obj.path_id)
        name = str(value.get("m_Name"))
        if not _is_font(value) or name not in pairs or pairs[name] == current.get(name):
            continue
        font_json, atlas_png = pairs[name]
        edited = json.loads(font_json.decode("utf-8"))
        if set(edited) != set(value):
            raise ValueError(tr("the font {0} has other fields than the bundle's font", name))
        atlas_id = value["m_AtlasTextures"][0]["m_PathID"]
        if edited["m_AtlasTextures"][0]["m_PathID"] != atlas_id:
            raise ValueError(tr("the font {0} names another atlas than its bundle", name))
        picture = Image.open(io.BytesIO(atlas_png))
        edits[atlas_id] = serialized.write(atlas_id, inline_texture(serialized.read(atlas_id), picture))
        edits[obj.path_id] = serialized.write(obj.path_id, edited)
    if not edits:
        return None
    cab = next(node.name for node in bundle.nodes if not node.name.endswith((".resS", ".res", ".resource")))
    return bundle.build({cab: serialized.replace(edits)})
