"""Skies of Arcadia (Dreamcast, USA MK-51052 V1.002): the field scripts of one USA disc, built into a new disc set.

The project's source folder holds the disc's field scripts (``FIELD/*.SCT``, plain, little-endian words) and
``.picoripi_disc.json``: the absolute path of the disc's cue sheet, so the build writes the new set from the original
tracks. The script codec, the editor strings and the byte budget are the GameCube plugin's, with the Dreamcast byte
order. The EU disc is only context and is not identified.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.i18n import tr
from core.project_library import images
from plugins.skies_of_arcadia.build import write_source_mark
from plugins.skies_of_arcadia.rules import GameRules as GameCubeRules

from . import build, unpack

GAME_ID = "MK-51052"
REGION = "U"   # the area symbol of the USA disc (the EU disc says E)
TARGET_ID = "disc_set"


class GameRules(GameCubeRules):
    """Skies of Arcadia, Dreamcast USA: the field scripts of the disc (both USA discs are accepted)."""

    big_endian = False
    fixed_scripts = ()   # no script is proven to freeze on growth yet; see the plugin notes

    def get_display_name(self) -> str:
        return "Skies of Arcadia (Dreamcast)"

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": images.KIND_GDROM, "label": tr("Dreamcast")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        found = images.identify(path)
        if found is None or found["kind"] != images.KIND_GDROM:
            return None
        if found["game_id"] != GAME_ID or found.get("region") != REGION:
            return None
        return {"role": "base", "platform": images.KIND_GDROM}

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        done = unpack.extract(base, target_dir, progress, is_cancelled)
        if done is not None:
            write_source_mark(target_dir, base)
        return done

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": TARGET_ID, "label": tr("Translated disc set (cue and tracks)"),
                 "platforms": [images.KIND_GDROM], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != TARGET_ID:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return build.build_gdrom_set(source_dir, translation_dir, output_dir, progress, is_cancelled)
