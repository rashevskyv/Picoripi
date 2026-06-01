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
        return self.replace_aliases_with_tags(text)

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

    def get_dynamic_name_tags(self) -> Dict[str, str]:
        """Return a mapping of {tag_string: replacement_name} for dynamic in-game names.

        These tags are substituted *before* stripping tags during script-matching distillation,
        so that e.g. '{escape:0:0022}' in BMG text matches 'Epona' in the script.
        The dict key must be the exact tag string as it appears in editor text.
        """
        return {}
    
    def get_tag_checker_handler(self) -> Optional[Any]:
        return None
        
    def get_short_problem_name(self, problem_id: str) -> str:
        problem_definitions = self.get_problem_definitions()
        return problem_definitions.get(problem_id, {}).get("name", problem_id)

    def get_plugin_actions(self) -> List[Dict[str, Any]]:
        return []

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        return self.replace_tags_with_aliases(data_string_subline)

    def replace_tags_with_aliases(self, text: str) -> str:
        if not self.mw or not hasattr(self.mw, 'default_tag_mappings') or not self.mw.default_tag_mappings:
            return text
        sorted_mappings = sorted(self.mw.default_tag_mappings.items(), key=lambda item: len(item[1]), reverse=True)
        result = text
        for alias, original_tag in sorted_mappings:
            if original_tag:
                result = result.replace(original_tag, alias)
        return result

    def replace_aliases_with_tags(self, text: str) -> str:
        if not self.mw or not hasattr(self.mw, 'default_tag_mappings') or not self.mw.default_tag_mappings:
            return text
        sorted_mappings = sorted(self.mw.default_tag_mappings.items(), key=lambda item: len(item[0]), reverse=True)
        result = text
        for alias, original_tag in sorted_mappings:
            if alias:
                result = result.replace(alias, original_tag)
        return result

    def get_text_representation_for_preview(self, data_string: str) -> str:
        newline_symbol = "↵"
        if self.mw and hasattr(self.mw, "newline_display_symbol"):
            val = self.mw.newline_display_symbol
            if isinstance(val, str):
                newline_symbol = val
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

    def parse_walkthrough_transcript(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse game-specific walkthrough transcript text file into structured rooms and dialogue cues.
        Plugins should override this to handle custom separators, chapters, acts, speakers, etc.
        """
        import os
        import json
        import re
        from utils.logging_utils import log_info, log_warning
        
        transcript_list = []
        if not file_path or not os.path.exists(file_path):
            return transcript_list
            
        try:
            if file_path.lower().endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        transcript_list = data
                    elif isinstance(data, dict) and "lines" in data:
                        transcript_list = data["lines"]
            else:
                # Highly advanced text parser for structured and GameFAQ scripts
                # Supports standardized [Chapter: ...], {Action: ...}, classical SPEAKER: dialogue, 
                # as well as classic bracketed descriptions and uppercase gutter speakers.
                with open(file_path, "r", encoding="cp1252", errors="replace") as f:
                    lines = f.readlines()
                
                current_chapter = "Foreword"
                last_speaker = "Dialogue/Narrator"
                last_brackets = ""

                for idx, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 1. Detect Wave separators (e.g. ~~~~~~~~~~~~~~~~~~~~~~~~) to split micro-scenes
                    if line.startswith("~") or (len(line) > 5 and all(c == '~' for c in line)):
                        last_brackets = ""
                        continue
                    
                    # 2. Detect Standard Chapter / Location tags (e.g. [Chapter: Prologue])
                    chapter_location_match = re.match(r'^\[(Chapter|Location):\s*(.*)\]$', line)
                    if chapter_location_match:
                        clean_ch = re.sub(r'[^a-zA-Z0-9_\s]', '', chapter_location_match.group(2)).strip()
                        clean_ch = "_".join(clean_ch.split())
                        if len(clean_ch) > 3:
                            current_chapter = clean_ch
                        last_brackets = "" # Reset micro-scene boundary on new chapter
                        continue
                    
                    # 3. Detect Standard Action / Context tags (e.g. {Action: Zelda sighs})
                    action_match = re.match(r'^\{(Action|Context):\s*(.*)\}$', line)
                    if action_match:
                        last_brackets = action_match.group(2).strip()
                        continue

                    # 4. Fallback: Detect classic GameFAQ Chapter / Act changes
                    chapter_match = re.search(r'(Chapter\s+[IVXLCDM\d]+|ACT\s+[A-Z]+|Act\s+[A-Za-z]+)', line)
                    if chapter_match:
                        clean_ch = re.sub(r'[^a-zA-Z0-9_\s]', '', line).strip()
                        clean_ch = "_".join(clean_ch.split())
                        if len(clean_ch) > 3:
                            current_chapter = clean_ch
                        last_brackets = ""
                        continue

                    # 5. Fallback: Detect classic action descriptions in brackets [...]
                    if line.startswith("[") and line.endswith("]"):
                        last_brackets = line[1:-1].strip()
                        continue

                    # 6. Detect Standard Inline Speaker dialogue (e.g. "ZELDA: I must find Link.")
                    speaker_dialogue_match = re.match(r'^([A-Z][A-Z\s]+):\s*(.*)$', line)
                    if speaker_dialogue_match:
                        last_speaker = speaker_dialogue_match.group(1).strip()
                        text = speaker_dialogue_match.group(2).strip()
                        context_note = f"Action: {last_brackets}" if last_brackets else ""
                        transcript_list.append({
                            "text": text,
                            "speaker": last_speaker,
                            "timestamp": context_note or f"Scene_{idx}",
                            "room": current_chapter
                        })
                        continue

                    # 7. Fallback: Detect Speaker (Uppercase words on a separate line, e.g. "MIDNA")
                    if line.isupper() and len(line) >= 2 and not line.startswith("ACT") and not line.startswith("CHAPTER") and not line.startswith("VERSION"):
                        last_speaker = line
                        continue

                    # 8. Classic Dialogue lines (fallback for flat text)
                    text = line
                    context_note = f"Action: {last_brackets}" if last_brackets else ""
                    
                    transcript_list.append({
                        "text": text,
                        "speaker": last_speaker,
                        "timestamp": context_note or f"Scene_{idx}",
                        "room": current_chapter
                    })
        except Exception as e:
            log_warning(f"BaseGameRules: Failed to parse transcript: {e}")
            
        return transcript_list