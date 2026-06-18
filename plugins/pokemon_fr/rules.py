from typing import Dict, Any, Tuple, Set, Optional, List
from collections import OrderedDict
from PyQt6.QtGui import QTextCharFormat, QColor, QFont
from plugins.base_game_rules import BaseGameRules
from .config import (
    PROBLEM_DEFINITIONS,
    PROBLEM_WIDTH_EXCEEDED,
    PROBLEM_SHORT_LINE,
    PROBLEM_EMPTY_SUBLINE,
    PROBLEM_SINGLE_WORD_SUBLINE,
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START,
    PROBLEM_TAG_WARNING,
    PROBLEM_BAD_SPACING,
    PROBLEM_MISSING_ICON_SPACING,
    DEFAULT_TAG_MAPPINGS_POKEMON_FR,
    P_NEWLINE_MARKER,
    L_NEWLINE_MARKER,
    P_VISUAL_EDITOR_MARKER,
    L_VISUAL_EDITOR_MARKER,
    CONTROL_CODES
)
from .tag_manager import TagManager
from .problem_analyzer import ProblemAnalyzer
from .text_fixer import TextFixer
from utils.logging_utils import log_debug
from utils.utils import convert_spaces_to_dots_for_display
import re

class ProblemIDs:
    PROBLEM_WIDTH_EXCEEDED = PROBLEM_WIDTH_EXCEEDED
    PROBLEM_SHORT_LINE = PROBLEM_SHORT_LINE
    PROBLEM_EMPTY_SUBLINE = PROBLEM_EMPTY_SUBLINE
    PROBLEM_SINGLE_WORD_SUBLINE = PROBLEM_SINGLE_WORD_SUBLINE
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START = PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    PROBLEM_TAG_WARNING = PROBLEM_TAG_WARNING
    PROBLEM_BAD_SPACING = PROBLEM_BAD_SPACING
    PROBLEM_MISSING_ICON_SPACING = PROBLEM_MISSING_ICON_SPACING

class GameRules(BaseGameRules):
    """Game rules and translation logic for Game."""
    def __init__(self, main_window_ref=None):
        """Initialize a new instance."""
        super().__init__(main_window_ref)
        self.original_keys = []
        
        self.tag_manager = TagManager(main_window_ref)
        self.problem_analyzer = ProblemAnalyzer(main_window_ref, self.tag_manager, PROBLEM_DEFINITIONS, ProblemIDs)
        self.text_fixer = TextFixer(main_window_ref, self.tag_manager, self.problem_analyzer)
        self.problem_analyzer.game_rules = self
        self.text_fixer.game_rules = self
        self.PROBLEM_MISSING_ICON_SPACING = PROBLEM_MISSING_ICON_SPACING
        self.problem_ids = self.problem_analyzer.problem_ids

    def load_data_from_json_obj(self, json_data: Any) -> Tuple[list, dict]:
        """Load data from json obj."""
        if not isinstance(json_data, dict):
            return [], {}
        
        # We no longer clear self.original_keys here so it can accumulate across multiple blocks.
        # It is cleared explicitly by ProjectActionHandler and AppActionHandler before loading starts.
        app_data = []
        block_names = {}
        
        sorted_blocks = sorted(json_data.items())

        for i, (block_name, string_obj) in enumerate(sorted_blocks):
            if isinstance(string_obj, dict):
                string_list = list(string_obj.values())
                key_list = list(string_obj.keys())
                
                app_data.append(string_list)
                self.original_keys.append(key_list)
                block_names[str(i)] = block_name
            else:
                log_debug(f"[PokemonFR Plugin] Skipping block '{block_name}' because its value is not a dictionary.")
        
        return app_data, block_names

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        """Save data to json obj."""
        if not self.original_keys or len(self.original_keys) != len(data):
            raise ValueError("Original keys for Pokemon data are missing or mismatched. Cannot save.")
            
        output_json = OrderedDict()
        for i, block_data in enumerate(data):
            block_name = block_names.get(str(i))
            if not block_name or i >= len(self.original_keys):
                log_debug(f"[PokemonFR Plugin] Skipping block index {i} during save due to missing name or keys.")
                continue 
            
            keys_for_block = self.original_keys[i]
            if len(keys_for_block) != len(block_data):
                log_debug(f"[PokemonFR Plugin] Mismatch in string count for '{block_name}': expected {len(keys_for_block)}, got {len(block_data)}. Data will be padded/truncated.")

            string_obj = OrderedDict()
            for j, key in enumerate(keys_for_block):
                if j < len(block_data):
                    string_obj[key] = block_data[j]
                else:
                    string_obj[key] = "" # Pad with empty string if missing
            
            output_json[block_name] = string_obj
            
        return output_json
        
    def get_text_representation_for_preview(self, data_string: str) -> str:
        """Get the text representation for preview."""
        newline_symbol = "↵"
        if self.mw and hasattr(self.mw, "newline_display_symbol"):
            val = self.mw.newline_display_symbol
            if isinstance(val, str):
                newline_symbol = val
        
        aliased = self.replace_tags_with_aliases(str(data_string))
        processed_string = aliased.replace('\\p', P_NEWLINE_MARKER)
        processed_string = processed_string.replace('\\l', L_NEWLINE_MARKER)
        processed_string = processed_string.replace('\\n', newline_symbol)
        
        show_dots = False
        if self.mw and hasattr(self.mw, "show_multiple_spaces_as_dots"):
            val = self.mw.show_multiple_spaces_as_dots
            if isinstance(val, bool):
                show_dots = val
        
        return convert_spaces_to_dots_for_display(processed_string, show_dots)

    def get_enter_char(self) -> str:
        """Get the enter char."""
        return '\n'

    def get_shift_enter_char(self) -> str:
        """Get the shift enter char."""
        return f"{P_VISUAL_EDITOR_MARKER}\n"

    def get_ctrl_enter_char(self) -> str:
        """Get the ctrl enter char."""
        return f"{L_VISUAL_EDITOR_MARKER}\n"

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        """Get the text representation for editor."""
        processed = str(data_string_subline).replace('\\p', f"{P_VISUAL_EDITOR_MARKER}\n")
        processed = processed.replace('\\l', f"{L_VISUAL_EDITOR_MARKER}\n")
        processed = processed.replace('\\n', '\n')
        return super().get_text_representation_for_editor(processed)

    def convert_editor_text_to_data(self, text: str) -> str:
        """Convert editor text to data."""
        converted = super().convert_editor_text_to_data(text)
        actual_text = converted.replace(f"{P_VISUAL_EDITOR_MARKER}\n", '\\p')
        actual_text = actual_text.replace(f"{L_VISUAL_EDITOR_MARKER}\n", '\\l')
        actual_text = actual_text.replace('\n', '\\n')
        return actual_text

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        """Get the syntax highlighting rules."""
        return self.tag_manager.get_syntax_highlighting_rules()

    def get_display_name(self) -> str:
        """Get the display name."""
        return "Pokémon FireRed/LeafGreen"

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get the problem definitions."""
        return PROBLEM_DEFINITIONS

    def get_default_tag_mappings(self) -> Dict[str, str]:
        """Get the default tag mappings."""
        return DEFAULT_TAG_MAPPINGS_POKEMON_FR

    def get_short_problem_name(self, problem_id: str) -> str:
        """Get the short problem name."""
        if problem_id == PROBLEM_BAD_SPACING:
            return "Spacing"
        if problem_id == PROBLEM_MISSING_ICON_SPACING:
            return "TagSpacing"
        return super().get_short_problem_name(problem_id)

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
        problems_per_subline = self.problem_analyzer.analyze_data_string(
            full_data_string_text_for_logical_check,
            editor_font_map,
            editor_line_width_threshold,
            logical_hard_limit
        )
        
        if qtextblock_number_in_editor < len(problems_per_subline):
            return problems_per_subline[qtextblock_number_in_editor]
        
        return set()

    def autofix_data_string(self, data_string: str, editor_font_map: dict, editor_line_width_threshold: int, logical_hard_limit: Optional[int] = None, allowed_problems: Optional[Set[str]] = None, block_idx: Optional[int] = None, string_idx: Optional[int] = None, page_local: bool = False, disable_pagination: bool = False) -> Tuple[str, bool]:
        """Autofix data string."""
        return self.text_fixer.autofix_data_string(
            data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination
        )

    def process_pasted_segment(self, segment_to_insert: str, *args, **kwargs) -> Tuple[str, str, str]:
        """Process pasted segment."""
        from utils.utils import clean_spaces
        cleaned_segment = clean_spaces(segment_to_insert)
        return cleaned_segment, "OK", ""