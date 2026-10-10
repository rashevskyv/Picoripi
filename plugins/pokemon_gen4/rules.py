"""Pokémon Diamond / Pearl, Platinum, HeartGold / SoulSilver (Nintendo DS) through the pret decompilations
pokediamond, pokeplatinum and pokeheartgold: the English messages of their text sources.

A project block is one source file: ``files/msgdata/msg/*.gmm`` (pokediamond, pokeheartgold; XML) or
``res/text/*.json`` (pokeplatinum). ``ds_text`` finds the English messages and writes them back in place, so
the decompilation's own build (which needs Nintendo's SDK and the Metrowerks compiler, neither of which is
shipped) picks up the translated files unchanged. A save is always built from the source file.
"""
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import ds_text
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

LINES_PER_BOX = 2


class GameRules(BaseGameRules):
    """Pokémon generation IV, pret decompilation text."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._loaded: Optional[str] = None
        self._source: Optional[str] = None

    def get_display_name(self) -> str:
        return "Pokémon Diamond, Pearl, Platinum, HeartGold and SoulSilver (pret)"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".gmm", ".json"), "text", "Pokémon (pret) message files")]

    # -- loading and saving ---------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if isinstance(json_obj, (bytes, bytearray)):
            json_obj = bytes(json_obj).decode("utf-8")
        if not isinstance(json_obj, str):
            return super().load_data_from_json_obj(json_obj)
        self._loaded = json_obj
        return [ds_text.load(json_obj)], {"0": "Text"}

    def prepare_save_context(self, context: Any) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._source = versions[-1].decode("utf-8") if versions else None

    def save_data_to_json_obj(self, data: list, block_names: Optional[dict] = None) -> Any:
        source = self._source if self._source is not None else self._loaded
        texts = [str(text) for text in (data[0] if data else [])]
        if source is None:
            return "\n".join(texts)
        return ds_text.write(source, texts)

    def reset_runtime_state(self) -> None:
        self._loaded = None
        self._source = None

    # -- context -----------------------------------------------------------------------------

    def _block_path(self, block_idx: int) -> str:
        try:
            pm = getattr(self.mw, "project_manager", None)
            block_map = getattr(self.mw, "block_to_project_file_map", {}) or {}
            index = block_map.get(block_idx, block_idx)
            return str(pm.project.blocks[index].source_file).replace("\\", "/")
        except (AttributeError, IndexError, KeyError, TypeError) as error:
            log_debug(f"pokemon_gen4: no file for block {block_idx}: {error}")
            return ""

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        rel = self._block_path(block_idx)
        return {"resource": rel, "label": os.path.splitext(os.path.basename(rel))[0]} if rel else {}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        rel = self._block_path(block_idx)
        return f"File {rel}" if rel else None

    # -- editing -----------------------------------------------------------------------------

    def get_editor_page_size(self) -> int:
        return LINES_PER_BOX

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_capabilities(self) -> Set[str]:
        return set()
