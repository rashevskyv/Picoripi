# --- START OF FILE plugins/base_game_rules.py ---
from typing import List, Tuple, Dict, Optional, Any, Set
from PyQt5.QtGui import QTextCharFormat
import json
import re

class BaseGameRules:
    """
    Base class for game-specific rules.
    Supports the 'Kruptar' format: strings delimited by {END} + empty line.
    """
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref

    def load_data_from_json_obj(self, json_data: Any) -> Tuple[list, dict]:
        if isinstance(json_data, list):
            # If it's an empty list, return it as a single empty block
            if not json_data:
                return [[]], {}
            # If it's already a list of lists, return as is
            if all(isinstance(sub, list) for sub in json_data):
                return json_data, {}
            # Otherwise, assume it's a single block containing these items
            return [json_data], {}
        
        if isinstance(json_data, dict):
            # Try to handle common dict-based formats (e.g. { "strings": [...] })
            if "strings" in json_data and isinstance(json_data["strings"], list):
                return self.load_data_from_json_obj(json_data["strings"])
            # Fallback for generic dict: wrap in list? No, probably return as is if it's a block
            # But the UI expects List[List[str]].
            return [], {}

        if isinstance(json_data, str):
            # Kruptar format check: if it contains {END}, split by it
            if '{END}' in json_data:
                raw_strings = re.split(r'\{END\}', json_data)
                processed_strings = []
                for s in raw_strings:
                    cleaned = s.strip('\r\n')
                    # If it's not empty, or it's the last one and contains content
                    if cleaned:
                        processed_strings.append(cleaned)
                    elif s == raw_strings[-1] and s.strip():
                         processed_strings.append(s.strip())
                return [processed_strings], {}
            
            # Fallback: treat as a single block with lines
            lines = json_data.splitlines()
            return [lines], {}
        return [], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        # If we are dealing with a single block (typical for .txt files)
        if len(data) == 1 and isinstance(data[0], list):
            # If we suspect Kruptar format (or just want to be safe if we loaded it that way)
            # For now, let's assume if we have {END} in the original or if it's multi-line strings
            # we might want to use {END}. But to be safe and consistent with user request:
            # "один блок - одна строка. {END} + порожня строка - симантичний символ"
            return "\n\n".join([str(line) + "\n{END}" for line in data[0]])
        return data
    
    def get_enter_char(self) -> str:
        return '\n'
        
    def get_shift_enter_char(self) -> str:
        return '\n'

    def get_ctrl_enter_char(self) -> str:
        return '\n'

    def convert_editor_text_to_data(self, text: str) -> str:
        return text

    def get_display_name(self) -> str:
        if self.mw and hasattr(self.mw, 'display_name'):
            return self.mw.display_name
        return "Base Game (No Plugin)"

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        return {}

    def get_color_marker_definitions(self) -> Dict[str, str]:
        """Returns descriptions for manual color markers."""
        return {}

    def get_spellcheck_ignore_pattern(self) -> str:
        """Returns a regex pattern of sequences to ignore during spellcheck (e.g. tags, control codes)."""
        # Default: ignore standard curly and square bracket tags
        patterns = [r'\{[^}]*\}', r'\[[^\]]*\]']
        
        # Add control codes from plugin if defined
        # We check both class attribute and module-level constant
        codes = []
        if hasattr(self, 'CONTROL_CODES'):
            codes = self.CONTROL_CODES
        else:
            # Try to get from the module where the subclass is defined
            import sys
            module = sys.modules.get(self.__class__.__module__)
            if module and hasattr(module, 'CONTROL_CODES'):
                codes = module.CONTROL_CODES
        
        if codes:
            # Escape each code to handle special regex characters like backslash or dots
            escaped_codes = [re.escape(c) for c in codes]
            patterns.extend(escaped_codes)
            
        return '|'.join(patterns)

    def analyze_subline(self,
                        text: str,
                        next_text: Optional[str],
                        subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int,
                        is_last_subline_in_data_string: bool,
                        editor_font_map: dict,
                        editor_line_width_threshold: int,
                        full_data_string_text_for_logical_check: str,
                        is_target_for_debug: bool = False) -> Set[str]:
        return set()

    def autofix_data_string(self,
                            data_string: str,
                            editor_font_map: dict,
                            editor_line_width_threshold: int) -> Tuple[str, bool]:
        return data_string, False

    def process_pasted_segment(self,
                                segment_to_insert: str,
                                original_text_for_tags: str,
                                editor_player_tag_const: str) -> Tuple[str, str, str]:
        return segment_to_insert, "OK", ""
        
    def get_base_game_rules_class(self):
        return BaseGameRules

    def get_default_tag_mappings(self) -> Dict[str, str]:
        return {}
    
    def get_tag_checker_handler(self) -> Optional[Any]:
        return None
        
    def get_short_problem_name(self, problem_id: str) -> str:
        problem_definitions = self.get_problem_definitions()
        return problem_definitions.get(problem_id, {}).get("name", problem_id)

    def get_plugin_actions(self) -> List[Dict[str, Any]]:
        return []

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        return data_string_subline

    def get_text_representation_for_preview(self, data_string: str) -> str:
        newline_symbol = getattr(self.mw, "newline_display_symbol", "↵") if self.mw else "↵"
        return data_string.replace('\n', newline_symbol)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        return []

    def get_legitimate_tags(self) -> Set[str]:
        return set()

    def get_context_menu_actions(self, editor_widget, selected_text: Optional[str]) -> List[Dict[str, Any]]:
        return []

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int) -> Optional[int]:
        return None

    def get_editor_page_size(self) -> int:
        return 2

    def get_custom_context_tags(self) -> Dict[str, List[Dict[str, str]]]:
        if self.mw and hasattr(self.mw, 'context_menu_tags'):
            return self.mw.context_menu_tags
        return {"single_tags": [], "wrap_tags": []}

    def save_custom_context_tags(self, tags_data: dict) -> None:
        if self.mw and hasattr(self.mw, 'context_menu_tags'):
            self.mw.context_menu_tags = tags_data
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()

    def get_font_for_block(self, block_idx: int) -> Optional[Dict[str, str]]:
        """Returns a dict with 'original_font_name' and 'font_name' if block has specific font overrides."""
        return None