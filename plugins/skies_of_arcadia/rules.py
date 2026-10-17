"""Skies of Arcadia Legends (GameCube, USA GEAE8P): the disc, the unpack and the translated disc build."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.i18n import tr
from core.project_library import images
from plugins.base_game_rules import BaseGameRules

from . import build, unpack
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS

GAME_ID = "GEAE8P"
TARGET_ID = "gc_iso"


class GameRules(BaseGameRules):
    """Skies of Arcadia Legends, USA GameCube disc. The EU disc is only context and is not identified."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS

    def get_display_name(self) -> str:
        return "Skies of Arcadia Legends (GameCube)"

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": images.KIND_GC, "label": tr("GameCube")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        return images.base_identity(path, (GAME_ID,))

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        done = unpack.extract(base, target_dir, progress, is_cancelled)
        if done is not None:
            build.write_source_mark(target_dir, base)
        return done

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": TARGET_ID, "label": tr("GameCube disc image (ISO)"), "platforms": [images.KIND_GC],
                 "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != TARGET_ID:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return build.build_gc_iso(source_dir, translation_dir, output_dir, progress, is_cancelled)
