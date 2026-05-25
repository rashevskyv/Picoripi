# --- START OF FILE plugins/plain_text/problem_analyzer.py ---
import re
from typing import Optional, Set, Dict, Any, List
from utils.utils import calculate_string_width, remove_all_tags
from plugins.common.problem_analyzer import GenericProblemAnalyzer

SENTENCE_END_PUNCTUATION_CHARS_ZWW = ['.', '!', '?']
OPTIONAL_TRAILING_CHARS_ZWW = ['"', "'"]

class ProblemAnalyzer(GenericProblemAnalyzer):
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        super().__init__(main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)

    def _ends_with_sentence_punctuation_zww(self, text_no_tags_stripped: str) -> bool:
        if not text_no_tags_stripped:
            return False
        last_char = text_no_tags_stripped[-1]
        if last_char in OPTIONAL_TRAILING_CHARS_ZWW:
            if len(text_no_tags_stripped) > 1:
                char_before_last = text_no_tags_stripped[-2]
                return char_before_last in SENTENCE_END_PUNCTUATION_CHARS_ZWW
            return False
        return last_char in SENTENCE_END_PUNCTUATION_CHARS_ZWW

    def _check_short_line_zww(self, current_subline_text: str, next_subline_text: str, font_map: dict, threshold: int) -> bool:
        current_subline_no_tags_stripped = remove_all_tags(current_subline_text).strip()
        if not current_subline_no_tags_stripped or self._ends_with_sentence_punctuation_zww(current_subline_no_tags_stripped):
            return False
        next_subline_no_tags_stripped = remove_all_tags(next_subline_text).strip()
        if not next_subline_no_tags_stripped:
            return False
        first_word_next = next_subline_no_tags_stripped.split(maxsplit=1)[0]
        if not first_word_next:
            return False
        width_current_rstripped = calculate_string_width(current_subline_text.rstrip(), font_map)
        width_first_word_next = calculate_string_width(first_word_next, font_map)
        space_width = calculate_string_width(" ", font_map)
        return (threshold - width_current_rstripped) >= (width_first_word_next + space_width)

    def check_for_empty_first_line_of_page(self, text: str) -> List[int]:
        lines = text.split('\n')
        problem_lines = []
        lines_per_page = getattr(self.mw, 'lines_per_page', 4)
        for i in range(len(lines)):
            if i % lines_per_page == 0:
                is_first_line_empty = not lines[i].strip()
                if is_first_line_empty:
                    page_lines = lines[i : i + lines_per_page]
                    if len(page_lines) > 1:
                        has_content_after = any(line.strip() for line in page_lines[1:])
                        if has_content_after:
                            problem_lines.append(i)
        return problem_lines

    def analyze_data_string(self, data_string: str, font_map: dict, threshold: int) -> List[Set[str]]:
        sublines = data_string.split('\n')
        problems_per_subline = [set() for _ in sublines]
        empty_first_lines = self.check_for_empty_first_line_of_page(data_string)
        for line_idx in empty_first_lines:
            if line_idx < len(problems_per_subline):
                problems_per_subline[line_idx].add(self.problem_ids.PROBLEM_EMPTY_FIRST_LINE_OF_PAGE)
        for i, subline in enumerate(sublines):
            pixel_width_subline = calculate_string_width(subline.rstrip(), font_map)
            if pixel_width_subline > threshold:
                problems_per_subline[i].add(self.problem_ids.PROBLEM_WIDTH_EXCEEDED)
            next_subline = sublines[i + 1] if i + 1 < len(sublines) else None
            if next_subline is not None:
                if self._check_short_line_zww(subline, next_subline, font_map, threshold):
                    problems_per_subline[i].add(self.problem_ids.PROBLEM_SHORT_LINE)
            is_odd_logical_subline = (i + 1) % 2 != 0
            if i > 0 and is_odd_logical_subline:
                if self._check_single_word_subline_generic(subline):
                    problems_per_subline[i].add(self.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE)
        return problems_per_subline

    def analyze_subline(self, *args, **kwargs) -> Set[str]:
        return set()