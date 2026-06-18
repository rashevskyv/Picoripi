from PyQt6.QtGui import QColor, QTextCharFormat, QFont
from PyQt6.QtCore import Qt
from typing import Optional, Set, Dict, Any, Tuple, List
import re
import json
import os

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import convert_spaces_to_dots_for_display

from .config import (
    PROBLEM_DEFINITIONS,
    PROBLEM_WIDTH_EXCEEDED,
    PROBLEM_SHORT_LINE,
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY,
    PROBLEM_TAG_WARNING,
    PROBLEM_SINGLE_WORD_SUBLINE,
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START,
    COLOR_MARKER_DEFINITIONS,
    CONTROL_CODES,
    PROBLEM_BAD_SPACING,
    PROBLEM_MISSING_ICON_SPACING,
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE
)
from .tag_manager import TagManager
from .problem_analyzer import ProblemAnalyzer
from .text_fixer import TextFixer
from .tag_logic import process_segment_tags_aggressively_zmc
from .tag_checker_handler import TagCheckerHandler

class ProblemIDs:
    """Problem i ds implementation."""
    PROBLEM_WIDTH_EXCEEDED = PROBLEM_WIDTH_EXCEEDED
    PROBLEM_SHORT_LINE = PROBLEM_SHORT_LINE
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY
    PROBLEM_TAG_WARNING = PROBLEM_TAG_WARNING
    PROBLEM_SINGLE_WORD_SUBLINE = PROBLEM_SINGLE_WORD_SUBLINE
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START = PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    PROBLEM_BAD_SPACING = PROBLEM_BAD_SPACING
    PROBLEM_MISSING_ICON_SPACING = PROBLEM_MISSING_ICON_SPACING
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE = PROBLEM_EMPTY_FIRST_LINE_OF_PAGE

class GameRules(BaseGameRules):
    """Game rules and translation logic for Game."""

    def __init__(self, main_window_ref=None):
        """Initialize a new instance."""
        super().__init__(main_window_ref)
        self.problem_definitions_cache = PROBLEM_DEFINITIONS
        self.tag_manager = TagManager(main_window_ref)
        self.problem_analyzer = ProblemAnalyzer(main_window_ref, self.tag_manager,
                                                self.problem_definitions_cache, ProblemIDs)
        self.text_fixer = TextFixer(main_window_ref, self.tag_manager, self.problem_analyzer)

    def load_data_from_json_obj(self, json_data: Any) -> Tuple[list, dict]:
        # Use base class implementation which now correctly handles flat lists and strings
        """Load data from json obj."""
        return super().load_data_from_json_obj(json_data)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        # If it's a list of lists, return as is (JSON format)
        """Save data to json obj."""
        if data and isinstance(data[0], list) and len(data) > 1:
            return data
        # Otherwise use base class for Kruptar/text format
        return super().save_data_to_json_obj(data, block_names)

    def get_display_name(self) -> str:
        """Get the display name."""
        return "The Legend of Zelda: The Minish Cap"

    def get_default_tag_mappings(self) -> Dict[str, str]:
        """Get the default tag mappings."""
        if self.mw and hasattr(self.mw, 'default_tag_mappings'):
            mappings = dict(self.mw.default_tag_mappings)
            if hasattr(self.mw, 'EDITOR_PLAYER_TAG') and hasattr(self.mw, 'ORIGINAL_PLAYER_TAG'):
                mappings[self.mw.EDITOR_PLAYER_TAG] = self.mw.ORIGINAL_PLAYER_TAG
            return mappings
        return {}

    def get_tag_checker_handler(self) -> Optional[TagCheckerHandler]:
        """Get the tag checker handler."""
        return TagCheckerHandler(self.mw)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        """Get the syntax highlighting rules."""
        return self.tag_manager.get_syntax_highlighting_rules()

    def get_legitimate_tags(self) -> Set[str]:
        """Get the legitimate tags."""
        return self.tag_manager.get_legitimate_tags()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        """Check if is tag legitimate."""
        return self.tag_manager.is_tag_legitimate(tag_to_check)

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get the problem definitions."""
        return self.problem_definitions_cache

    def get_color_marker_definitions(self) -> Dict[str, str]:
        """Get the color marker definitions."""
        return COLOR_MARKER_DEFINITIONS

    def get_short_problem_name(self, problem_id: str) -> str:
        """Get the short problem name."""
        if problem_id == PROBLEM_WIDTH_EXCEEDED: return "Width"
        if problem_id == PROBLEM_SHORT_LINE: return "Short"
        if problem_id == PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: return "EmptyPage"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE: return "1Word"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE_NON_START: return "1WordO"
        if problem_id == PROBLEM_TAG_WARNING: return "Tag"
        if problem_id == PROBLEM_BAD_SPACING: return "Spacing"
        if problem_id == PROBLEM_MISSING_ICON_SPACING: return "TagSpacing"
        return super().get_short_problem_name(problem_id)

    def get_plugin_actions(self) -> List[Dict[str, Any]]:
        """Get the plugin actions."""
        actions = [
            {
                'name': 'check_tags_mismatch',
                'text': 'Check Tags Mismatch',
                'tooltip': 'Check for tags mismatch between original and translation',
                'shortcut': None, 
                'handler': self.mw.plugin_handler.trigger_check_tags_action,
                'menu': 'Tools'
            }
        ]

        translator = getattr(self.mw, 'translation_handler', None)
        if translator:
            actions.extend([
                {
                    'name': 'ai_translate_current_string',
                    'text': 'AI Translate Current String (UA)',
                    'tooltip': 'Translate the current string into Ukrainian with AI',
                    'shortcut': 'Ctrl+Alt+T',
                    'handler': translator.translate_current_string,
                    'menu': 'Tools'
                },
                {
                    'name': 'ai_translate_selected_lines',
                    'text': 'AI Translate Selected Lines (UA)',
                    'tooltip': 'Translate the selected lines of the current string into Ukrainian',
                    'shortcut': 'Ctrl+Alt+L',
                    'handler': translator.translate_selected_lines,
                    'menu': 'Tools'
                },
                {
                    'name': 'ai_translate_current_block',
                    'text': 'AI Translate Entire Block (UA)',
                    'tooltip': 'Translate every string in the current block into Ukrainian',
                    'shortcut': 'Ctrl+Alt+B',
                    'handler': translator.translate_current_block,
                    'menu': 'Tools'
                },
                {
                    'name': 'ai_reset_translation_session',
                    'text': 'AI Reset Translation Session',
                    'tooltip': 'Очистити поточну AI-сесію перекладу',
                    'shortcut': None,
                    'handler': translator.reset_translation_session,
                    'menu': 'Tools'
                }
            ])

        return actions
    
    def get_text_representation_for_preview(self, data_string: str) -> str:
        """Get the text representation for preview."""
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
        """Get the text representation for editor."""
        return super().get_text_representation_for_editor(str(data_string_subline))

    def convert_editor_text_to_data(self, text: str) -> str:
        """Convert editor text to data."""
        return super().convert_editor_text_to_data(text)

    def analyze_subline(self,
                        text: str,
                        next_text: Optional[str],
                        subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int,
                        is_last_subline_in_data_string: bool,
                        editor_font_map: dict,
                        editor_line_width_threshold: int,
                        full_data_string_text_for_logical_check: str,
                        is_target_for_debug: bool = False,
                        logical_hard_limit: Optional[int] = None) -> Set[str]:
        """Analyze subline."""
        return self.problem_analyzer.analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor,
            is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold,
            full_data_string_text_for_logical_check, is_target_for_debug,
            logical_hard_limit=logical_hard_limit
        )

    def autofix_data_string(self,
                            data_string: str,
                            editor_font_map: dict,
                            editor_line_width_threshold: int,
                            logical_hard_limit: Optional[int] = None,
                            allowed_problems: Optional[Set[str]] = None,
                            block_idx: Optional[int] = None,
                            string_idx: Optional[int] = None,
                            page_local: bool = False,
                            disable_pagination: bool = False) -> Tuple[str, bool]:
        """Autofix data string."""
        return self.text_fixer.autofix_data_string(
            data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination
        )
    
    def process_pasted_segment(self,
                               segment_to_insert: str,
                               original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        """Process pasted segment."""
        from utils.utils import clean_spaces
        cleaned_segment = clean_spaces(segment_to_insert)
        return process_segment_tags_aggressively_zmc(
            cleaned_segment,
            original_text_for_tags,
            editor_player_tag_const
        )
    
    def get_base_game_rules_class(self):
        """Get the base game rules class."""
        return BaseGameRules
