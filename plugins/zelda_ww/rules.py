import os
import re
from typing import Any, Tuple, Dict, List, Set, Optional

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_info, log_warning
from utils.utils import calculate_string_width, convert_spaces_to_dots_for_display

from .config import (
    PROBLEM_DEFINITIONS,
    PROBLEM_TAG_WARNING,
    PROBLEM_WIDTH_EXCEEDED,
    PROBLEM_SHORT_LINE,
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY,
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
    PROBLEM_TAG_WARNING = PROBLEM_TAG_WARNING
    PROBLEM_WIDTH_EXCEEDED = PROBLEM_WIDTH_EXCEEDED
    PROBLEM_SHORT_LINE = PROBLEM_SHORT_LINE
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY
    PROBLEM_SINGLE_WORD_SUBLINE = PROBLEM_SINGLE_WORD_SUBLINE
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START = PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE = PROBLEM_EMPTY_FIRST_LINE_OF_PAGE
    PROBLEM_BAD_SPACING = PROBLEM_BAD_SPACING
    PROBLEM_MISSING_ICON_SPACING = PROBLEM_MISSING_ICON_SPACING

class GameRules(BaseGameRules):
    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.problem_definitions_cache = PROBLEM_DEFINITIONS
        # Додаємо посилання на ProblemIDs, щоб UI міг звертатися до self.mw.current_game_rules.problem_ids
        self.problem_ids = ProblemIDs 
        self.tag_manager = TagManager(main_window_ref)
        self.problem_analyzer = ProblemAnalyzer(main_window_ref, self.tag_manager,
                                                self.problem_definitions_cache, ProblemIDs)
        self.text_fixer = TextFixer(main_window_ref, self.tag_manager, self.problem_analyzer)

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Optional[Dict[str, str]]]:
        # Use base class implementation for Kruptar format support
        return super().load_data_from_json_obj(json_obj)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        # Use base class implementation for Kruptar format support
        return super().save_data_to_json_obj(data, block_names)

    def get_display_name(self) -> str:
        return "Zelda: The Wind Waker"

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        return self.problem_definitions_cache

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, Any]]:
        return self.tag_manager.get_syntax_highlighting_rules()
        
    def get_legitimate_tags(self) -> Set[str]:
        return self.tag_manager.get_legitimate_tags()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return self.tag_manager.is_tag_legitimate(tag_to_check)

    def analyze_subline(self, text: str, next_text: Optional[str], subline_number_in_data_string: int, qtextblock_number_in_editor: int, is_last_subline_in_data_string: bool, editor_font_map: dict, editor_line_width_threshold: int, full_data_string_text_for_logical_check: str, is_target_for_debug: bool = False, logical_hard_limit: Optional[int] = None) -> set:
        
        all_problems = self.problem_analyzer.analyze_data_string(full_data_string_text_for_logical_check, editor_font_map, editor_line_width_threshold, logical_hard_limit)

        if subline_number_in_data_string < len(all_problems):
            # Add line-specific problems that are not part of the full string analysis
            line_specific_problems = self.problem_analyzer.analyze_subline(
                text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string,
                editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug,
                logical_hard_limit=logical_hard_limit
            )
            all_problems[subline_number_in_data_string].update(line_specific_problems)
            return all_problems[subline_number_in_data_string]

        return self.problem_analyzer.analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string,
            editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug,
            logical_hard_limit=logical_hard_limit
        )

    def autofix_data_string(self, data_string: str, editor_font_map: dict, editor_line_width_threshold: int, logical_hard_limit: Optional[int] = None, allowed_problems: Optional[Set[str]] = None) -> Tuple[str, bool]:
        return self.text_fixer.autofix_data_string(
            data_string=data_string,
            editor_font_map=editor_font_map,
            editor_line_width_threshold=editor_line_width_threshold,
            logical_hard_limit=logical_hard_limit,
            allowed_problems=allowed_problems
        )

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str, editor_player_tag_const: str) -> Tuple[str, str, str]:
        from utils.utils import clean_spaces
        cleaned_segment = clean_spaces(segment_to_insert)
        return process_segment_tags_aggressively_zww(
            segment_to_insert=cleaned_segment,
            original_text_for_tags=original_text_for_tags,
            editor_player_tag_const=editor_player_tag_const
        )

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        icon_sequences = getattr(self.mw, 'icon_sequences', [])
        return calculate_string_width(text, font_map, default_char_width, icon_sequences=icon_sequences)
        
    def get_short_problem_name(self, problem_id: str) -> str:
        if problem_id == PROBLEM_WIDTH_EXCEEDED: return "Width"
        if problem_id == PROBLEM_SHORT_LINE: return "Short"
        if problem_id == PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: return "EmptyOddD"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE: return "1Word"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE_NON_START: return "1WordO"
        if problem_id == PROBLEM_EMPTY_FIRST_LINE_OF_PAGE: return "Empty1st"
        if problem_id == PROBLEM_BAD_SPACING: return "Spacing"
        if problem_id == PROBLEM_MISSING_ICON_SPACING: return "IconSpacing"
        return super().get_short_problem_name(problem_id)
        
    def get_text_representation_for_preview(self, data_string: str) -> str:
        newline_symbol = "↵"
        if self.mw and hasattr(self.mw, "newline_display_symbol"):
            val = self.mw.newline_display_symbol
            if isinstance(val, str):
                newline_symbol = val
        aliased = self.replace_tags_with_aliases(str(data_string))
        processed_string = aliased.replace('\n', newline_symbol)
        
        show_dots = False
        if self.mw and hasattr(self.mw, "show_multiple_spaces_as_dots"):
            val = self.mw.show_multiple_spaces_as_dots
            if isinstance(val, bool):
                show_dots = val
        return convert_spaces_to_dots_for_display(processed_string, show_dots)

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        return super().get_text_representation_for_editor(str(data_string_subline))
        
    def convert_editor_text_to_data(self, text: str) -> str:
        return super().convert_editor_text_to_data(text)
        
    def get_enter_char(self) -> str: return '\n'
    def get_shift_enter_char(self) -> str: return '\n'
    def get_ctrl_enter_char(self) -> str: return '\n'
    
    def get_editor_page_size(self) -> int:
        return 1