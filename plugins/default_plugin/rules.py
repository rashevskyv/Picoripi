import re
from typing import Any, Dict, List, Optional, Set, Tuple

import utils.utils as width_utils
from PyQt6.QtGui import QTextCharFormat
from plugins.base_game_rules import BaseGameRules
from utils.utils import clean_spaces, convert_spaces_to_dots_for_display

from .config import (
    PROBLEM_BAD_SPACING,
    PROBLEM_BROKEN_ICON_HYPHEN,
    PROBLEM_DEFINITIONS,
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE,
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY,
    PROBLEM_MISSING_ICON_SPACING,
    PROBLEM_SHORT_LINE,
    PROBLEM_SINGLE_WORD_SUBLINE,
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START,
    PROBLEM_TAG_WARNING,
    PROBLEM_WIDTH_EXCEEDED,
)
from .problem_analyzer import ProblemAnalyzer
from .tag_manager import TAG_RE, TagManager
from .text_fixer import TextFixer


class ProblemIDs:
    PROBLEM_TAG_WARNING = PROBLEM_TAG_WARNING
    PROBLEM_WIDTH_EXCEEDED = PROBLEM_WIDTH_EXCEEDED
    PROBLEM_SHORT_LINE = PROBLEM_SHORT_LINE
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY
    PROBLEM_SINGLE_WORD_SUBLINE = PROBLEM_SINGLE_WORD_SUBLINE
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START = PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE = PROBLEM_EMPTY_FIRST_LINE_OF_PAGE
    PROBLEM_BAD_SPACING = PROBLEM_BAD_SPACING
    PROBLEM_MISSING_ICON_SPACING = PROBLEM_MISSING_ICON_SPACING
    PROBLEM_BROKEN_ICON_HYPHEN = PROBLEM_BROKEN_ICON_HYPHEN


class GameRules(BaseGameRules):
    """Minimal, copy-ready plugin template.

    This ruleset is intentionally generic: it accepts simple text, JSON string
    lists, and basic bracket/curly tags. Copy this package under a new plugin
    name, then replace the parser, tag rules, font metrics, and warnings with
    game-specific behavior.
    """

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.problem_definitions_cache = PROBLEM_DEFINITIONS
        self.tag_manager = TagManager(main_window_ref)
        self.problem_analyzer = ProblemAnalyzer(
            main_window_ref,
            self.tag_manager,
            self.problem_definitions_cache,
            ProblemIDs,
        )
        self.text_fixer = TextFixer(main_window_ref, self.tag_manager, self.problem_analyzer)
        self.problem_analyzer.game_rules = self
        self.text_fixer.game_rules = self

    def get_display_name(self) -> str:
        return "Default Plugin Template"

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

    def get_tag_pattern(self) -> Optional[re.Pattern]:
        return TAG_RE

    def get_default_tag_mappings(self) -> Dict[str, str]:
        return {}

    def get_text_representation_for_preview(self, data_string: str) -> str:
        newline_symbol = getattr(self.mw, "newline_display_symbol", "↵") if self.mw else "↵"
        aliased = self.replace_tags_with_aliases(str(data_string))
        processed = aliased.replace("\n", newline_symbol)
        show_dots = getattr(self.mw, "show_multiple_spaces_as_dots", True) if self.mw else True
        return convert_spaces_to_dots_for_display(processed, show_dots)

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        return super().get_text_representation_for_editor(str(data_string_subline))

    def convert_editor_text_to_data(self, text: str) -> str:
        return super().convert_editor_text_to_data(text)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        return self.tag_manager.get_syntax_highlighting_rules()

    def get_legitimate_tags(self) -> Set[str]:
        return self.tag_manager.get_legitimate_tags()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return self.tag_manager.is_tag_legitimate(tag_to_check)

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        return self.problem_definitions_cache

    def get_short_problem_name(self, problem_id: str) -> str:
        names = {
            PROBLEM_TAG_WARNING: "Tag",
            PROBLEM_WIDTH_EXCEEDED: "Width",
            PROBLEM_SHORT_LINE: "Short",
            PROBLEM_EMPTY_FIRST_LINE_OF_PAGE: "Empty1st",
            PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: "EmptyOdd",
            PROBLEM_SINGLE_WORD_SUBLINE: "1Word",
            PROBLEM_SINGLE_WORD_SUBLINE_NON_START: "1WordO",
            PROBLEM_BAD_SPACING: "Spacing",
            PROBLEM_MISSING_ICON_SPACING: "TagSpacing",
            PROBLEM_BROKEN_ICON_HYPHEN: "IconHyphen",
        }
        return names.get(problem_id, super().get_short_problem_name(problem_id))

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
        font_map = editor_font_map or {}
        threshold = editor_line_width_threshold or getattr(self.mw, "line_width_warning_threshold_pixels", 240)
        full_text = full_data_string_text_for_logical_check if full_data_string_text_for_logical_check is not None else text
        all_problems = self.problem_analyzer.analyze_data_string(
            full_text,
            font_map,
            threshold,
            logical_hard_limit,
        )

        if 0 <= subline_number_in_data_string < len(all_problems):
            line_specific = self.problem_analyzer.analyze_subline(
                text,
                next_text,
                subline_number_in_data_string,
                qtextblock_number_in_editor,
                is_last_subline_in_data_string,
                font_map,
                threshold,
                full_text,
                is_target_for_debug,
                logical_hard_limit=logical_hard_limit,
            )
            all_problems[subline_number_in_data_string].update(line_specific)
            return all_problems[subline_number_in_data_string]
        return set()

    def autofix_data_string(
        self,
        data_string: str,
        editor_font_map: dict,
        editor_line_width_threshold: int,
        logical_hard_limit: Optional[int] = None,
        allowed_problems: Optional[Set[str]] = None,
        block_idx: Optional[int] = None,
        string_idx: Optional[int] = None,
        page_local: bool = False,
        disable_pagination: bool = False,
    ) -> Tuple[str, bool]:
        return self.text_fixer.autofix_data_string(
            data_string,
            editor_font_map or {},
            editor_line_width_threshold,
            logical_hard_limit,
            allowed_problems,
            block_idx,
            string_idx,
            page_local,
            disable_pagination,
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
        return "default_plugin_script.md"

