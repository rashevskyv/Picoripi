# --- START OF FILE plugins/zelda_bmg/rules.py ---
import os
import re
import json
from typing import Any, Tuple, Dict, List, Set, Optional
from PyQt5.QtGui import QTextCharFormat, QColor, QFont

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_info, log_warning, log_debug
from utils.utils import convert_spaces_to_dots_for_display

# Load mapping for Ukrainian letters
plugin_dir = os.path.dirname(os.path.abspath(__file__))
mapping_path = os.path.join(plugin_dir, 'translation_map.json')
translation_map = {}
reverse_translation_map = {}

if os.path.exists(mapping_path):
    try:
        with open(mapping_path, 'r', encoding='utf-8') as f:
            translation_map = json_data = f.read()
            import json
            translation_map = json.loads(json_data)
            reverse_translation_map = {v: k for k, v in translation_map.items()}
            log_info(f"Loaded {len(translation_map)} translation characters mappings for Ukrainian language.")
    except Exception as e:
        log_warning(f"Error loading translation_map.json: {e}")

from .config import (
    PROBLEM_DEFINITIONS,
    PROBLEM_TAG_WARNING,
    PROBLEM_WIDTH_EXCEEDED,
    PROBLEM_SHORT_LINE,
    PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL,
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY,
    PROBLEM_SINGLE_WORD_SUBLINE,
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE
)
from .tag_manager import TagManager
from .problem_analyzer import ProblemAnalyzer
from .text_fixer import TextFixer
from .tag_logic import process_segment_tags_aggressively_zbmg

class ProblemIDs:
    PROBLEM_TAG_WARNING = PROBLEM_TAG_WARNING
    PROBLEM_WIDTH_EXCEEDED = PROBLEM_WIDTH_EXCEEDED
    PROBLEM_SHORT_LINE = PROBLEM_SHORT_LINE
    PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL = PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY
    PROBLEM_SINGLE_WORD_SUBLINE = PROBLEM_SINGLE_WORD_SUBLINE
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE = PROBLEM_EMPTY_FIRST_LINE_OF_PAGE

class GameRules(BaseGameRules):
    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.problem_definitions_cache = PROBLEM_DEFINITIONS
        self.problem_ids = ProblemIDs
        self.tag_manager = TagManager(main_window_ref)
        self.problem_analyzer = ProblemAnalyzer(main_window_ref, self.tag_manager,
                                                self.problem_definitions_cache, ProblemIDs)
        self.text_fixer = TextFixer(main_window_ref, self.tag_manager, self.problem_analyzer)
        self.last_loaded_bmg = None

    def decode_string_with_mapping(self, s: str) -> str:
        """Decode CP1252 string (with active umlauts) into Ukrainian letters."""
        result = []
        for char in s:
            result.append(reverse_translation_map.get(char, char))
        return "".join(result)

    def encode_string_with_mapping(self, s: str) -> str:
        """Encode Ukrainian letters back into CP1252 characters for BMG compatibility."""
        result = []
        for char in s:
            result.append(translation_map.get(char, char))
        return "".join(result)

    def msg_to_editor_text(self, bmg_msg: Any) -> str:
        """Convert BMG message parts to editor representation."""
        parts = []
        for item in bmg_msg.parts:
            if isinstance(item, str):
                parts.append(self.decode_string_with_mapping(item))
            elif isinstance(item, dict) and item.get("type") == "escape":
                esc_type = item.get("escape_type")
                hex_data = item.get("data", "")
                parts.append(f"{{escape:{esc_type}:{hex_data}}}")
        return "".join(parts)

    def editor_text_to_msg_content(self, text: str) -> list:
        """Convert editor representation back to BMG message parts list."""
        content = []
        pattern = r'(\{escape:\d+:[0-9a-fA-F]*\})'
        tokens = re.split(pattern, text)
        for token in tokens:
            if not token:
                continue
            match = re.match(r'\{escape:(\d+):([0-9a-fA-F]*)\}', token)
            if match:
                esc_type = int(match.group(1))
                hex_data = match.group(2)
                content.append({
                    "type": "escape",
                    "escape_type": esc_type,
                    "data": hex_data
                })
            else:
                content.append(self.encode_string_with_mapping(token))
        return content

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Optional[Dict[str, str]]]:
        if not isinstance(json_obj, bytes):
            # Fallback to standard BaseGameRules logic if not binary
            return super().load_data_from_json_obj(json_obj)

        log_info("Parsing BMG binary data in zelda_bmg plugin...")
        from bmg_tool import BMGFile
        
        bmg = BMGFile()
        try:
            bmg.load(json_obj)
        except Exception as e:
            log_warning(f"Error parsing BMG in plugin: {e}")
            return [], {}

        self.last_loaded_bmg = bmg
        
        strings_list = []
        block_names = {}
        
        for idx, msg in enumerate(bmg.messages):
            strings_list.append(self.msg_to_editor_text(msg))
            msg_id = getattr(msg, 'id', idx)
            block_names[str(idx)] = f"Message ID: {msg_id} (Idx {idx})"

        log_info(f"Loaded {len(strings_list)} messages from BMG.")
        return [strings_list], block_names

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if not data or not isinstance(data[0], list):
            return b""

        strings_list = data[0]
        from bmg_tool import BMGFile, BMGMessage

        bmg = self.last_loaded_bmg
        if not bmg:
            # Fallback if no file was previously loaded
            bmg = BMGFile()
            bmg.endianness = '>'
            bmg.encoding = 'cp1252'
            bmg.id = 0

        new_messages = []
        for idx, text in enumerate(strings_list):
            orig_msg = bmg.messages[idx] if bmg and idx < len(bmg.messages) else None
            msg_id = getattr(orig_msg, 'id', idx) if orig_msg else idx
            info = getattr(orig_msg, 'info', b'\x00\x00\x00\x00') if orig_msg else b'\x00\x00\x00\x00'
            is_null = getattr(orig_msg, 'is_null', False) if orig_msg else False
            
            msg = BMGMessage(info=info, parts=self.editor_text_to_msg_content(text), is_null=is_null)
            msg.id = msg_id
            new_messages.append(msg)

        bmg.messages = new_messages

        try:
            out_bytes = bmg.save()
            log_info(f"Successfully packed {len(new_messages)} messages into BMG binary.")
            return out_bytes
        except Exception as e:
            log_warning(f"Error packing BMG in plugin: {e}")
            return b""

    def get_display_name(self) -> str:
        return "Zelda: Twilight Princess BMG"

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        return self.problem_definitions_cache

    def get_short_problem_name(self, problem_id: str) -> str:
        if problem_id == PROBLEM_WIDTH_EXCEEDED: return "Width"
        if problem_id == PROBLEM_SHORT_LINE: return "Short"
        if problem_id == PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL: return "EmptyOddL"
        if problem_id == PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: return "EmptyOddD"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE: return "1Word"
        if problem_id == PROBLEM_EMPTY_FIRST_LINE_OF_PAGE: return "Empty1st"
        return super().get_short_problem_name(problem_id)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        return self.tag_manager.get_syntax_highlighting_rules()

    def get_legitimate_tags(self) -> Set[str]:
        return self.tag_manager.get_legitimate_tags()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return self.tag_manager.is_tag_legitimate(tag_to_check)

    def get_spellcheck_ignore_pattern(self) -> str:
        # Ignore curly braces {...} which are used for tags and escape sequences
        return r'\{[^}]*\}'

    def get_editor_page_size(self) -> int:
        return 1

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
        all_problems = self.problem_analyzer.analyze_data_string(full_data_string_text_for_logical_check, editor_font_map, editor_line_width_threshold)

        if subline_number_in_data_string < len(all_problems):
            line_specific_problems = self.problem_analyzer.analyze_subline(
                text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string,
                editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug
            )
            all_problems[subline_number_in_data_string].update(line_specific_problems)
            return all_problems[subline_number_in_data_string]

        return self.problem_analyzer.analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string,
            editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug
        )

    def autofix_data_string(self,
                            data_string: str,
                            editor_font_map: dict,
                            editor_line_width_threshold: int) -> Tuple[str, bool]:
        return self.text_fixer.autofix_data_string(
            data_string, editor_font_map, editor_line_width_threshold
        )

    def process_pasted_segment(self,
                                segment_to_insert: str,
                                original_text_for_tags: str,
                                editor_player_tag_const: str) -> Tuple[str, str, str]:
        return process_segment_tags_aggressively_zbmg(
            segment_to_insert,
            original_text_for_tags,
            editor_player_tag_const
        )

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        icon_sequences = getattr(self.mw, 'icon_sequences', [])
        from utils.utils import calculate_string_width
        return calculate_string_width(text, font_map, default_char_width, icon_sequences=icon_sequences)

    def get_text_representation_for_preview(self, data_string: str) -> str:
        newline_symbol = getattr(self.mw, "newline_display_symbol", "↵") if self.mw else "↵"
        processed_string = str(data_string).replace('\n', newline_symbol)
        return convert_spaces_to_dots_for_display(processed_string, self.mw.show_multiple_spaces_as_dots)

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        return str(data_string_subline)

    def convert_editor_text_to_data(self, text: str) -> str:
        return text
