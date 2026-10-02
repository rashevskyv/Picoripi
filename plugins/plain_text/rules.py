"""
Plain Text plugin for text translation workbench.

This plugin provides text editing functionality with problem detection and autofix:
- Tags enclosed in square brackets []
- Newline handling: \\n, \\r
- Width detection and autofix
- Line merging/splitting based on width constraints
"""

from typing import List, Tuple, Dict, Optional, Any, Set
from plugins.base_game_rules import BaseGameRules
from plugins.common.config_factory import problem_ids
from plugins.common.tag_logic import process_pasted_segment
import utils.utils as uu
from utils.utils import convert_spaces_to_dots_for_display

from .config import PROBLEM_DEFINITIONS

# The ids keep the "ZWW" prefix this plugin started with: user settings refer to them.
ProblemIDs = problem_ids(PROBLEM_DEFINITIONS, "ZWW", without=("EMPTY_ODD_SUBLINE_DISPLAY", "BROKEN_ICON_HYPHEN"))


class GameRules(BaseGameRules):
    """Plain text game rules with problem detection and autofix."""

    problem_prefix = "ZWW"
    problem_definitions = PROBLEM_DEFINITIONS
    problem_ids = ProblemIDs
    tag_style = "square"
    analyze_whole_string_first = True

    def get_display_name(self) -> str:
        """Return the display name for this plugin."""
        return "Plain Text"

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Optional[Dict[str, str]]]:
        """Load data from json obj."""
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
        """Save data to json obj."""
        all_strings = []
        for block in blocks:
            all_strings.extend(block)
        return '\n'.join(str(s) for s in all_strings)

    def get_text_representation_for_preview(self, data_string: str) -> str:
        """Get the text representation for preview."""
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
        """Get the text representation for editor."""
        processed = str(data_string_subline)
        processed = processed.replace('\\n', '\n')
        processed = processed.replace('\\r', '\n')
        return super().get_text_representation_for_editor(processed)

    def convert_editor_text_to_data(self, text: str) -> str:
        """Convert editor text to data."""
        converted = super().convert_editor_text_to_data(text)
        return converted.replace('\n', '\\n')

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        """Calculate string width override."""
        return uu.calculate_string_width(text, font_map, default_char_width, icon_sequences=[])

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
        disable_pagination: bool = False
    ) -> Tuple[str, bool]:
        """Autofix works on editor text: the stored line breaks are escapes."""
        text_for_fixing = self.get_text_representation_for_editor(data_string)
        fixed_text, was_modified = super().autofix_data_string(
            text_for_fixing, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems,
            block_idx, string_idx, page_local, disable_pagination,
        )
        return self.convert_editor_text_to_data(fixed_text), was_modified

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str, editor_player_tag_const: str) -> Tuple[str, str, str]:
        """Process pasted segment."""
        from utils.utils import clean_spaces
        return process_pasted_segment(clean_spaces(segment_to_insert), original_text_for_tags, editor_player_tag_const)
