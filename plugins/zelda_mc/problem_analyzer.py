import re
from typing import Optional, Set, Dict, Any
from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, ALL_TAGS_PATTERN
from plugins.common.problem_analyzer import GenericProblemAnalyzer

SENTENCE_END_PUNCTUATION_CHARS_ZMC = ['.', '!', '?']
OPTIONAL_TRAILING_CHARS_ZMC = ['"', "'"]

class ProblemAnalyzer(GenericProblemAnalyzer):
    """Problem analyzer implementation."""
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        """Initialize a new instance."""
        super().__init__(main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)

    def _ends_with_sentence_punctuation_zmc(self, text_no_tags_stripped: str) -> bool:
        """Internal helper to ends with sentence punctuation zmc."""
        if not text_no_tags_stripped:
            return False
        last_char = text_no_tags_stripped[-1]
        if last_char in OPTIONAL_TRAILING_CHARS_ZMC:
            if len(text_no_tags_stripped) > 1:
                char_before_last = text_no_tags_stripped[-2]
                return char_before_last in SENTENCE_END_PUNCTUATION_CHARS_ZMC
            return False
        return last_char in SENTENCE_END_PUNCTUATION_CHARS_ZMC

    def _check_short_line_zmc(self, current_subline_text: str, next_subline_text: str, font_map: dict, threshold: int) -> bool:
        """Internal helper to check short line zmc."""
        from utils.utils import has_visible_content, extract_first_word_with_tags, get_line_words_and_visible_tags

        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}
        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []

        if not has_visible_content(current_subline_text, default_tag_mappings, font_map, icon_sequences):
            return False

        current_subline_no_tags_stripped = remove_all_tags(current_subline_text).strip()
        if self._ends_with_sentence_punctuation_zmc(current_subline_no_tags_stripped):
            return False

        first_word_next, _ = extract_first_word_with_tags(next_subline_text)
        if not first_word_next:
            return False

        text_for_width_calc_current = convert_dots_to_spaces_from_editor(current_subline_text.rstrip())
        text_for_width_calc_next_word = convert_dots_to_spaces_from_editor(first_word_next)

        width_current_rstripped = calculate_string_width(
            text_for_width_calc_current, 
            font_map, 
            icon_sequences=icon_sequences, 
            default_tag_mappings=default_tag_mappings
        )
        width_first_word_next = calculate_string_width(
            text_for_width_calc_next_word, 
            font_map, 
            icon_sequences=icon_sequences, 
            default_tag_mappings=default_tag_mappings
        )
        space_width = calculate_string_width(" ", font_map)

        # If next line has exactly two words, only allow warning if BOTH words can fit
        next_words = get_line_words_and_visible_tags(next_subline_text, self.mw)
        if len(next_words) == 2:
            text_for_width_calc_next_full = convert_dots_to_spaces_from_editor(next_subline_text.strip())
            width_next_full = calculate_string_width(
                text_for_width_calc_next_full, 
                font_map,
                icon_sequences=icon_sequences,
                default_tag_mappings=default_tag_mappings
            )
            return (threshold - width_current_rstripped) >= (width_next_full + space_width)

        return (threshold - width_current_rstripped) >= (width_first_word_next + space_width)

    def _check_empty_odd_subline_display_zmc(self,
                                             subline_text: str,
                                             subline_qtextblock_number_in_editor: int,
                                             is_logically_single_and_empty_data_string: bool) -> bool:

        """Internal helper to check empty odd subline display zmc."""
        lines_per_page = getattr(self.mw, 'lines_per_page', 4)
        is_first_line_of_page = (subline_qtextblock_number_in_editor % lines_per_page) == 0

        if is_logically_single_and_empty_data_string:
            return False

        if not is_first_line_of_page:
            return False

        text_no_dots = convert_dots_to_spaces_from_editor(subline_text)
        text_no_tags_for_empty_check = remove_all_tags(text_no_dots)
        stripped_text_no_tags_for_empty_check = text_no_tags_for_empty_check.strip()
        is_content_empty_or_zero = not stripped_text_no_tags_for_empty_check or stripped_text_no_tags_for_empty_check == "0"

        return is_content_empty_or_zero

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
        found_problems = super().analyze_subline(text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug, logical_hard_limit=logical_hard_limit)
        
        text_with_spaces = convert_dots_to_spaces_from_editor(text)
        next_text_with_spaces = convert_dots_to_spaces_from_editor(next_text) if next_text is not None else None

        is_logically_single_and_empty_data_string_check = (full_data_string_text_for_logical_check == "" and subline_number_in_data_string == 0 and is_last_subline_in_data_string)

        if self._check_empty_odd_subline_display_zmc(text, qtextblock_number_in_editor, is_logically_single_and_empty_data_string_check):
             found_problems.add(self.problem_ids.PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY)

        lines_per_page = 4
        if self.mw and hasattr(self.mw, 'lines_per_page'):
            lines_per_page = getattr(self.mw, 'lines_per_page', 4)

        if next_text_with_spaces is not None:
            if (subline_number_in_data_string + 1) % lines_per_page != 0:
                if self._check_short_line_zmc(text_with_spaces, next_text_with_spaces, editor_font_map, editor_line_width_threshold):
                    found_problems.add(self.problem_ids.PROBLEM_SHORT_LINE)

        is_only_one_subline = (subline_number_in_data_string == 0 and is_last_subline_in_data_string)
        if not is_only_one_subline:
            if self._check_single_word_subline_generic(text_with_spaces):
                if not self._is_single_word_ok_generic(text_with_spaces):
                    sublines = full_data_string_text_for_logical_check.split('\n')
                    is_allowed_orphan = False
                    if subline_number_in_data_string > 0 and subline_number_in_data_string < len(sublines):
                        is_allowed_orphan = self._is_single_word_orphan_allowed(
                            text_with_spaces,
                            sublines[subline_number_in_data_string - 1],
                            editor_font_map
                        )
                    
                    if not is_allowed_orphan:
                        if subline_number_in_data_string % lines_per_page == 0:
                            start_idx = subline_number_in_data_string
                            page_lines = sublines[start_idx : start_idx + lines_per_page]
                            has_content_after = any(line.strip() for line in page_lines[1:])
                            if has_content_after:
                                found_problems.add(self.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE)
                            else:
                                found_problems.add(self.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE_NON_START)
                        else:
                            found_problems.add(self.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE_NON_START)

        return found_problems