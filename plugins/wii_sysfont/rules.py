"""Minimal, copy-ready game plugin."""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import utils.utils as width_utils
from plugins.base_game_rules import BaseGameRules
from utils.utils import clean_spaces

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager


class GameRules(BaseGameRules):
    """Wii System Font. Generated from plugins/default_plugin.

    This ruleset is intentionally generic: it accepts simple text, JSON string
    lists, and basic bracket/curly tags. Replace the parser, tag rules, font
    metrics, and warnings with game-specific behavior. New plugins are created
    from this package with ``python tools/new_plugin.py``.

    The class attributes below are all the wiring a plugin needs: the base
    class builds the tag manager, the problem analyzer and the text fixer from
    them and answers the hooks that only pass a call on (problem definitions,
    highlighting, analysis, autofix, short problem names).
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"                  # "square" when the game's tags are [like this]
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def get_display_name(self) -> str:
        return "Wii System Font"

    def get_font_sources(self) -> List[Dict[str, Any]]:
        """The two system fonts, listed once the archived-font format (``brfna``, feat/ready-rabbids) is in."""
        from core.font_formats import is_supported
        if not is_supported("brfna"):
            return []
        return [{"label": "Wii system font 1 (wbf1.brfna)", "format": "brfna", "path": "fonts/wbf1.brfna"},
                {"label": "Wii system font 2 (wbf2.brfna)", "format": "brfna", "path": "fonts/wbf2.brfna"}]

    def get_capabilities(self) -> Set[str]:
        """Opt-in features. Empty here on purpose.

        See ``docs/wiki/3_Plugin_Developer_Guide.md`` ("Capabilities"). When the game's own files
        or a decompilation already encode window kinds, dialogue flow, or lore,
        copy the *approach* from ``plugins/zelda_bmg/`` (Twilight Princess) —
        that plugin reads those sources and advertises capabilities such as
        ``message_window_preview``. Do not copy its game-specific tables.
        """
        return set()

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if isinstance(json_obj, str):
            blocks = []
            for raw_block in re.split(r"\n\s*\n", json_obj.strip()):
                lines = [line for line in raw_block.splitlines() if line.strip()]
                if lines:
                    blocks.append(lines)
            if not blocks:
                blocks = [[]]
            return blocks, {str(i): f"Block {i + 1}" for i in range(len(blocks))}

        if isinstance(json_obj, list):
            if all(isinstance(block, list) for block in json_obj):
                return json_obj, {str(i): f"Block {i + 1}" for i in range(len(json_obj))}
            return [[str(item) for item in json_obj]], {"0": "Block 1"}

        if isinstance(json_obj, dict):
            strings = json_obj.get("strings")
            blocks = json_obj.get("blocks")
            if isinstance(blocks, list):
                return self.load_data_from_json_obj(blocks)
            if isinstance(strings, list):
                return self.load_data_from_json_obj(strings)

        return [[]], {"0": "Block 1"}

    def save_data_to_json_obj(self, blocks: List[List[str]], block_names: Optional[Dict[str, str]] = None) -> Any:
        rendered_blocks = ["\n".join(str(line) for line in block) for block in blocks]
        return "\n\n".join(rendered_blocks)

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        icon_sequences = getattr(self.mw, "icon_sequences", []) if self.mw else []
        mappings = getattr(self.mw, "default_tag_mappings", None) if self.mw else None
        return width_utils.calculate_string_width(
            text,
            font_map or {},
            default_char_width=default_char_width,
            icon_sequences=icon_sequences,
            default_tag_mappings=mappings,
        )

    def analyze_subline(
        self,
        text: str,
        next_text: Optional[str],
        subline_number_in_data_string: int,
        qtextblock_number_in_editor: int,
        is_last_subline_in_data_string: bool,
        editor_font_map: Optional[Dict] = None,
        editor_line_width_threshold: Optional[int] = None,
        full_data_string_text_for_logical_check: Optional[str] = None,
        is_target_for_debug: bool = False,
        logical_hard_limit: Optional[int] = None,
    ) -> Set[str]:
        """The base analysis, with defaults for a caller that gives no font map, width or full text."""
        threshold = editor_line_width_threshold or getattr(self.mw, "line_width_warning_threshold_pixels", 240)
        full_text = full_data_string_text_for_logical_check if full_data_string_text_for_logical_check is not None else text
        return super().analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor,
            is_last_subline_in_data_string, editor_font_map or {}, threshold, full_text,
            is_target_for_debug, logical_hard_limit=logical_hard_limit,
        )

    def process_pasted_segment(
        self,
        segment_to_insert: str,
        original_text_for_tags: str,
        editor_player_tag_const: str,
    ) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return 4

    def get_default_script_name(self) -> Optional[str]:
        return "wii_sysfont_script.md"
