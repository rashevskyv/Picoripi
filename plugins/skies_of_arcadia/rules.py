"""Skies of Arcadia Legends (GameCube, USA GEAE8P): the disc, the unpack and the translated disc build."""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Optional, Tuple

from core.formats import DEFAULT_FORMATS, FileFormat
from core.i18n import tr
from core.project_library import images
from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning

from . import build, scripts, unpack
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS

GAME_ID = "GEAE8P"
TARGET_ID = "gc_iso"


class GameRules(BaseGameRules):
    """Skies of Arcadia Legends, USA GameCube disc. The EU disc is only context and is not identified."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._save_fixed = False
        self._last_loaded: Optional[bytes] = None

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

    def get_file_formats(self) -> list:
        return [FileFormat((".sct",), "bytes", "Skies of Arcadia script (SCT)"), *DEFAULT_FORMATS]

    def includes_source_file(self, rel_path: str) -> bool:
        return rel_path.lower().endswith(".sct")

    # -- load and save -----------------------------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            texts = scripts.read_strings(self._last_loaded)
        except (ValueError, IndexError, struct.error) as error:
            log_debug(f"skies_of_arcadia: not a field script ({error})")
            return [[]], {}
        return [texts], {}

    def prepare_save_context(self, context) -> None:
        """Every save starts from the source file (the last version offered), so offsets never drift."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None
        self._save_fixed = scripts.is_fixed(context.relative_path)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        strings = [str(t) for t in (data[0] if data else [])]
        out, refused, missing = scripts.write_strings(source, strings, self._save_fixed)
        if refused:
            log_warning(f"skies_of_arcadia: {len(refused)} text(s) are longer than their fixed-size page; "
                        "they keep the original text")
        if missing:
            log_warning("skies_of_arcadia: the game has no byte for these characters, they were written as '?': "
                        + "".join(sorted(missing)))
        return out

    def reset_runtime_state(self) -> None:
        self._save_source = self._last_loaded = None
        self._save_fixed = False
