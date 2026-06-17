import os
import re
import json
from typing import Any, Tuple, Dict, List, Set, Optional
from PyQt6.QtGui import QTextCharFormat, QColor, QFont

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_info, log_warning, log_debug, log_error
from utils.utils import convert_spaces_to_dots_for_display

# Load mapping for Ukrainian letters
plugin_dir = os.path.dirname(os.path.abspath(__file__))

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
    PROBLEM_MISSING_ICON_SPACING,
    PROBLEM_STAR_TAG_RULES
)
from .tag_manager import TagManager
from .problem_analyzer import ProblemAnalyzer
from .text_fixer import TextFixer
from .tag_logic import process_segment_tags_aggressively_zbmg

class ProblemIDs:
    """Problem i ds implementation."""
    PROBLEM_TAG_WARNING = PROBLEM_TAG_WARNING
    PROBLEM_WIDTH_EXCEEDED = PROBLEM_WIDTH_EXCEEDED
    PROBLEM_SHORT_LINE = PROBLEM_SHORT_LINE
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY
    PROBLEM_SINGLE_WORD_SUBLINE = PROBLEM_SINGLE_WORD_SUBLINE
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START = PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE = PROBLEM_EMPTY_FIRST_LINE_OF_PAGE
    PROBLEM_BAD_SPACING = PROBLEM_BAD_SPACING
    PROBLEM_MISSING_ICON_SPACING = PROBLEM_MISSING_ICON_SPACING
    PROBLEM_STAR_TAG_RULES = PROBLEM_STAR_TAG_RULES

class GameRules(BaseGameRules):
    """Game rules and translation logic for Game."""
    def __init__(self, main_window_ref=None):
        """Initialize a new instance."""
        super().__init__(main_window_ref)
        self.problem_definitions_cache = PROBLEM_DEFINITIONS
        self.problem_ids = ProblemIDs
        self.tag_manager = TagManager(main_window_ref)
        self.problem_analyzer = ProblemAnalyzer(main_window_ref, self.tag_manager,
                                                self.problem_definitions_cache, ProblemIDs)
        self.text_fixer = TextFixer(main_window_ref, self.tag_manager, self.problem_analyzer)
        self.last_loaded_bmg = None
        self.translation_map = {}
        self.reverse_translation_map = {}
        self._last_map_path = None
        self._last_map_mtime = 0
        self.load_translation_map()

    def get_dynamic_name_tags(self) -> dict:
        """Twilight Princess BMG dynamic name escape tags.

        In TP BMG files, the player name (Link) and the horse name (Epona)
        are stored as escape tags that the game replaces at runtime.
        These substitutions allow distilled script-matching to find strings
        that contain these tags by treating them as plain text.

        Tag format in editor: {escape:<type>:<hex_data>}
          - Link  -> {escape:0:0000} or {escape:0:0001}
          - Epona -> {escape:0:0022}
        """
        return {
            "{PLAYER}": "Link",
            "{escape:0:0000}": "Link",
            "{escape:0:0001}": "Link",
            "{escape:0:0022}": "Epona",
        }



    def load_translation_map(self):
        """Load translation map."""
        project_dir = None
        if self.mw and hasattr(self.mw, 'project_manager') and self.mw.project_manager:
            project_dir = self.mw.project_manager.project_dir

        path = None
        if project_dir:
            proj_path = os.path.join(project_dir, 'translation_map.json')
            if not os.path.exists(proj_path):
                # Автоматично копіюємо з папки плагіна або створюємо порожній
                plugin_map_path = os.path.join(plugin_dir, 'translation_map.json')
                try:
                    if os.path.exists(plugin_map_path):
                        import shutil
                        shutil.copy2(plugin_map_path, proj_path)
                        log_info(f"Copied default translation_map.json from plugin to project: {proj_path}")
                    else:
                        with open(proj_path, 'w', encoding='utf-8') as f:
                            f.write("{}")
                        log_info(f"Created empty translation_map.json in project: {proj_path}")
                except Exception as e:
                    log_warning(f"Failed to copy/create translation_map.json in project: {e}")
            path = proj_path
        else:
            path = os.path.join(plugin_dir, 'translation_map.json')

        try:
            mtime = os.path.getmtime(path) if os.path.exists(path) else 0
        except Exception:
            mtime = 0

        if path != self._last_map_path or mtime != self._last_map_mtime:
            self._last_map_path = path
            self._last_map_mtime = mtime
            self.translation_map = {}
            self.reverse_translation_map = {}
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        raw_map = json.loads(f.read())
                        self.translation_map = {}
                        for k, v in raw_map.items():
                            # Accept synthetic keys "#g{idx}" (empty-glyph mappings) as-is
                            if k.startswith("#g") or v.startswith("#g"):
                                self.translation_map[k] = v
                            elif len(k) == 1 and len(v) == 1:
                                self.translation_map[k] = v
                                
                        # Rebuild reverse map only from normal (non-synthetic) entries
                        self.reverse_translation_map = {
                            v: k for k, v in self.translation_map.items()
                            if not k.startswith("#g") and not v.startswith("#g")
                        }
                    log_info(f"Loaded {len(self.translation_map)} translation characters mappings from {path}")
                except Exception as e:
                    log_warning(f"Error loading translation_map.json from {path}: {e}")

    def decode_string_with_mapping(self, s: str) -> str:
        """Decode CP1252 string (with active umlauts) into Ukrainian letters."""
        self.load_translation_map()
        result = []
        for char in s:
            # 1. Try normal reverse translation mapping
            decoded = self.reverse_translation_map.get(char)
            if decoded:
                result.append(decoded)
                continue
                
            # 2. Try synthetic reverse mapping: check if ord(char) corresponds to a synthetic key
            synth_key = f"#g{ord(char) - 1}"
            decoded_synth = self.translation_map.get(synth_key)
            if decoded_synth:
                result.append(decoded_synth)
                continue
                
            result.append(char)
        return "".join(result)

    def encode_string_with_mapping(self, s: str) -> str:
        """Encode Ukrainian letters back into CP1252 characters for BMG compatibility."""
        self.load_translation_map()
        result = []
        for char in s:
            # 1. Get mapped value
            val = self.translation_map.get(char, char)
            
            # 2. If it's a synthetic empty-glyph mapping like "#g224", encode as character with code 225 (glyph_idx + 1)
            if val.startswith("#g"):
                try:
                    glyph_idx = int(val[2:])
                    val = chr(glyph_idx + 1)
                except Exception:
                    pass
            result.append(val)
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
        """Load data from json obj."""
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
        """Save data to json obj."""
        try:
            log_debug(f"zelda_bmg: save_data_to_json_obj called. data type={type(data)}, len={len(data) if data else 0}", category="file_ops")
            if data and len(data) > 0:
                log_debug(f"zelda_bmg: data[0] type={type(data[0])}, len={len(data[0]) if hasattr(data[0], '__len__') else 'N/A'}", category="file_ops")
            if not data or not isinstance(data[0], list):
                log_warning("zelda_bmg: save_data_to_json_obj early exit because data is empty or data[0] is not a list!", category="file_ops")
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

            out_bytes = bmg.save()
            log_info(f"Successfully packed {len(new_messages)} messages into BMG binary.", category="file_ops")
            return out_bytes
        except Exception as e:
            log_error(f"Error packing BMG in plugin: {e}", exc_info=True, category="file_ops")
            return b""

    def get_display_name(self) -> str:
        """Get the display name."""
        return "Zelda: Twilight Princess BMG"

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get the problem definitions."""
        return self.problem_definitions_cache

    def get_short_problem_name(self, problem_id: str) -> str:
        """Get the short problem name."""
        if problem_id == PROBLEM_WIDTH_EXCEEDED: return "Width"
        if problem_id == PROBLEM_SHORT_LINE: return "Short"
        if problem_id == PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: return "EmptyOddD"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE: return "1Word"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE_NON_START: return "1WordO"
        if problem_id == PROBLEM_EMPTY_FIRST_LINE_OF_PAGE: return "Empty1st"
        if problem_id == PROBLEM_BAD_SPACING: return "Spacing"
        if problem_id == PROBLEM_MISSING_ICON_SPACING: return "TagSpacing"
        if problem_id == PROBLEM_STAR_TAG_RULES: return "StarTag"
        return super().get_short_problem_name(problem_id)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        """Get the syntax highlighting rules."""
        return self.tag_manager.get_syntax_highlighting_rules()

    def get_legitimate_tags(self) -> Set[str]:
        """Get the legitimate tags."""
        return self.tag_manager.get_legitimate_tags()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        """Check if is tag legitimate."""
        return self.tag_manager.is_tag_legitimate(tag_to_check)

    def get_spellcheck_ignore_pattern(self) -> str:
        # Ignore curly braces {...} which are used for tags and escape sequences
        """Get the spellcheck ignore pattern."""
        return r'\{[^}]*\}'

    def get_editor_page_size(self) -> int:
        """Get the editor page size."""
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
                        is_target_for_debug: bool = False,
                        logical_hard_limit: Optional[int] = None) -> Set[str]:
        """Analyze subline."""
        all_problems = self.problem_analyzer.analyze_data_string(full_data_string_text_for_logical_check, editor_font_map, editor_line_width_threshold, logical_hard_limit)

        if subline_number_in_data_string < len(all_problems):
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
        return process_segment_tags_aggressively_zbmg(
            cleaned_segment,
            original_text_for_tags,
            editor_player_tag_const
        )

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        """Calculate string width override."""
        icon_sequences = getattr(self.mw, 'icon_sequences', [])
        from utils.utils import calculate_string_width
        return calculate_string_width(text, font_map, default_char_width, icon_sequences=icon_sequences)

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
