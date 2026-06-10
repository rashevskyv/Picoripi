"""
Plain Text plugin for text translation workbench.

This plugin provides text editing functionality with problem detection and autofix:
- Tags enclosed in square brackets []
- Newline handling: \n, \r
- Width detection and autofix
- Line merging/splitting based on width constraints
"""

import re
from typing import List, Tuple, Dict, Optional, Any, Set
from plugins.base_game_rules import BaseGameRules
from PyQt6.QtGui import QTextCharFormat
from utils.utils import calculate_string_width, convert_spaces_to_dots_for_display

from .config import (
    PROBLEM_DEFINITIONS,
    PROBLEM_WIDTH_EXCEEDED,
    PROBLEM_SHORT_LINE,
    PROBLEM_TAG_WARNING,
    PROBLEM_SINGLE_WORD_SUBLINE,
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START,
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE,
    PROBLEM_BAD_SPACING,
    PROBLEM_MISSING_ICON_SPACING
)
from .tag_manager import TagManager
from .problem_analyzer import ProblemAnalyzer
from .text_fixer import TextFixer
from .tag_logic import process_segment_tags_aggressively_zww


class ProblemIDs:
    PROBLEM_WIDTH_EXCEEDED = PROBLEM_WIDTH_EXCEEDED
    PROBLEM_SHORT_LINE = PROBLEM_SHORT_LINE
    PROBLEM_TAG_WARNING = PROBLEM_TAG_WARNING
    PROBLEM_SINGLE_WORD_SUBLINE = PROBLEM_SINGLE_WORD_SUBLINE
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START = PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE = PROBLEM_EMPTY_FIRST_LINE_OF_PAGE
    PROBLEM_BAD_SPACING = PROBLEM_BAD_SPACING
    PROBLEM_MISSING_ICON_SPACING = PROBLEM_MISSING_ICON_SPACING


class GameRules(BaseGameRules):
    """Plain text game rules with problem detection and autofix."""

    def __init__(self, main_window_ref=None):
        """Initialize plain text game rules with problem analyzer and autofix."""
        super().__init__(main_window_ref)
        self.problem_definitions_cache = PROBLEM_DEFINITIONS
        self.tag_manager = TagManager(main_window_ref)
        self.problem_analyzer = ProblemAnalyzer(main_window_ref, self.tag_manager,
                                                self.problem_definitions_cache, ProblemIDs)
        self.text_fixer = TextFixer(main_window_ref, self.tag_manager, self.problem_analyzer)

    def get_display_name(self) -> str:
        """Return the display name for this plugin."""
        return "Plain Text"

    def get_default_tag_mappings(self) -> Dict[str, str]:
        return {}

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Optional[Dict[str, str]]]:
        blocks = []
        block_names = {}
        if isinstance(json_obj, str):
            lines = [line for line in json_obj.split('\n') if line.strip()]
            if lines:
                blocks.append(lines)
                block_names["0"] = "Block 0"

        if not blocks:
            blocks = [[]]
            block_names = {"0": "Block 0"}
        return blocks, block_names

    def save_data_to_json_obj(self, blocks: List[List[str]], block_names: Optional[Dict[str, str]] = None) -> Any:
        all_strings = []
        for block in blocks:
            all_strings.extend(block)
        return '\n'.join(str(s) for s in all_strings)

    def get_tag_pattern(self) -> Optional[re.Pattern]:
        return re.compile(r'\[([^\]]+)\]')

    def get_text_representation_for_preview(self, data_string: str) -> str:
        newline_symbol = "↵"
        if self.mw and hasattr(self.mw, "newline_display_symbol"):
            val = self.mw.newline_display_symbol
            if isinstance(val, str):
                newline_symbol = val
        aliased = self.replace_tags_with_aliases(str(data_string))
        processed = aliased.replace('\\n', newline_symbol)
        processed = processed.replace('\\r', newline_symbol)
        
        show_dots = True
        if self.mw and hasattr(self.mw, "show_multiple_spaces_as_dots"):
            val = self.mw.show_multiple_spaces_as_dots
            if isinstance(val, bool):
                show_dots = val
        return convert_spaces_to_dots_for_display(processed, show_dots)

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        processed = str(data_string_subline)
        processed = processed.replace('\\n', '\n')
        processed = processed.replace('\\r', '\n')
        return super().get_text_representation_for_editor(processed)

    def convert_editor_text_to_data(self, text: str) -> str:
        converted = super().convert_editor_text_to_data(text)
        return converted.replace('\n', '\\n')

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        return self.tag_manager.get_syntax_highlighting_rules()

    def get_legitimate_tags(self) -> Set[str]:
        return self.tag_manager.get_legitimate_tags()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return self.tag_manager.is_tag_legitimate(tag_to_check)

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        return self.problem_definitions_cache

    def get_short_problem_name(self, problem_id: str) -> str:
        if problem_id == PROBLEM_WIDTH_EXCEEDED: return "Width"
        if problem_id == PROBLEM_SHORT_LINE: return "Short"
        if problem_id == PROBLEM_EMPTY_FIRST_LINE_OF_PAGE: return "Empty1st"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE: return "1Word"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE_NON_START: return "1WordO"
        if problem_id == PROBLEM_TAG_WARNING: return "Tag"
        if problem_id == PROBLEM_BAD_SPACING: return "Spacing"
        if problem_id == PROBLEM_MISSING_ICON_SPACING: return "IconSpacing"
        return super().get_short_problem_name(problem_id)

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        return calculate_string_width(text, font_map, default_char_width, icon_sequences=[])

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
        logical_hard_limit: Optional[int] = None
    ) -> set:

        all_problems = self.problem_analyzer.analyze_data_string(
            full_data_string_text_for_logical_check,
            editor_font_map,
            editor_line_width_threshold,
            logical_hard_limit
        )

        if subline_number_in_data_string < len(all_problems):
            # Add line-specific problems that are not part of the full string analysis
            line_specific_problems = self.problem_analyzer.analyze_subline(
                text,
                next_text,
                subline_number_in_data_string,
                qtextblock_number_in_editor,
                is_last_subline_in_data_string,
                editor_font_map,
                editor_line_width_threshold,
                full_data_string_text_for_logical_check,
                is_target_for_debug,
                logical_hard_limit=logical_hard_limit
            )
            all_problems[subline_number_in_data_string].update(line_specific_problems)
            return all_problems[subline_number_in_data_string]

        return self.problem_analyzer.analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string,
            editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug,
            logical_hard_limit=logical_hard_limit
        )

    def autofix_data_string(
        self,
        data_string: str,
        editor_font_map: dict,
        editor_line_width_threshold: int,
        logical_hard_limit: Optional[int] = None,
        allowed_problems: Optional[Set[str]] = None,
        block_idx: Optional[int] = None,
        string_idx: Optional[int] = None
    ) -> Tuple[str, bool]:
        
        text_for_fixing = self.get_text_representation_for_editor(data_string)
        
        fixed_text, was_modified = self.text_fixer.autofix_data_string(
            text_for_fixing, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx
        )
        
        final_text = self.convert_editor_text_to_data(fixed_text)
        
        return final_text, was_modified

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str, editor_player_tag_const: str) -> Tuple[str, str, str]:
        from utils.utils import clean_spaces
        cleaned_segment = clean_spaces(segment_to_insert)
        return process_segment_tags_aggressively_zww(
            segment_to_insert=cleaned_segment,
            original_text_for_tags=original_text_for_tags,
            editor_player_tag_const=editor_player_tag_const
        )