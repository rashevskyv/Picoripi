from typing import Optional, Set, List, Tuple
import re
from utils.utils import calculate_string_width, remove_all_tags
from plugins.common.problem_analyzer import GenericProblemAnalyzer
from .config import (PROBLEM_WIDTH_EXCEEDED, PROBLEM_SHORT_LINE, PROBLEM_EMPTY_SUBLINE,
                     PROBLEM_SINGLE_WORD_SUBLINE, PROBLEM_TAG_WARNING)

SENTENCE_END_PUNCTUATION_CHARS = ['.', '!', '?']
NEWLINE_TAGS_PATTERN = re.compile(r'(\\n|\\p|\\l)')

class ProblemAnalyzer(GenericProblemAnalyzer):
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        super().__init__(main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)
        self.problem_ids = {
            'WIDTH': PROBLEM_WIDTH_EXCEEDED,
            'SHORT': PROBLEM_SHORT_LINE,
            'EMPTY': PROBLEM_EMPTY_SUBLINE,
            'SINGLE': PROBLEM_SINGLE_WORD_SUBLINE,
            'TAG': PROBLEM_TAG_WARNING,
        }

    def _get_sublines_from_data_string(self, data_string: str) -> List[Tuple[str, str]]:
        sublines = []
        parts = NEWLINE_TAGS_PATTERN.split(data_string)
        current_text = parts[0]
        for i in range(1, len(parts), 2):
            newline_tag = parts[i]
            text_after = parts[i+1]
            sublines.append((current_text, newline_tag))
            current_text = text_after
        if current_text or (not sublines and data_string):
            sublines.append((current_text, ""))
        return sublines

    def _ends_with_sentence_punctuation(self, text_no_tags_stripped: str) -> bool:
        if not text_no_tags_stripped:
            return False
        return text_no_tags_stripped[-1] in SENTENCE_END_PUNCTUATION_CHARS

    def _check_short_line(self, current_subline: str, next_subline: str, font_map: dict, threshold: int) -> bool:
        current_subline_no_tags_stripped = remove_all_tags(current_subline).strip()
        if not current_subline_no_tags_stripped or self._ends_with_sentence_punctuation(current_subline_no_tags_stripped):
            return False
        next_subline_no_tags_stripped = remove_all_tags(next_subline).strip()
        if not next_subline_no_tags_stripped:
            return False
        first_word_next = next_subline_no_tags_stripped.split(maxsplit=1)[0]
        if not first_word_next:
            return False
        width_current = calculate_string_width(current_subline, font_map)
        width_first_word_next = calculate_string_width(first_word_next, font_map)
        space_width = calculate_string_width(" ", font_map)
        return (width_current + space_width + width_first_word_next) <= threshold

    def analyze_data_string(self, data_string: str, font_map: dict, threshold: int) -> List[Set[str]]:
        if not data_string:
            return []
        sublines_with_tags = self._get_sublines_from_data_string(data_string)
        problems_per_subline_idx = [set() for _ in sublines_with_tags]
        is_only_one_subline_in_total = len(sublines_with_tags) == 1
        for i, (text_part, newline_tag) in enumerate(sublines_with_tags):
            text_part_no_tags = remove_all_tags(text_part)
            width = calculate_string_width(text_part, font_map)
            if (text_part.count('{') != text_part.count('}')) or (text_part.count('[') != text_part.count(']')):
                problems_per_subline_idx[i].add(self.problem_ids['TAG'])
            if not text_part_no_tags.strip():
                if i < len(sublines_with_tags) - 1:
                    problems_per_subline_idx[i].add(self.problem_ids['EMPTY'])
            if width > threshold:
                problems_per_subline_idx[i].add(self.problem_ids['WIDTH'])
            if i + 1 < len(sublines_with_tags):
                next_text_part, _ = sublines_with_tags[i+1]
                if self._check_short_line(text_part, next_text_part, font_map, threshold):
                    problems_per_subline_idx[i].add(self.problem_ids['SHORT'])
            if not is_only_one_subline_in_total and self._check_single_word_subline_generic(text_part):
                 problems_per_subline_idx[i].add(self.problem_ids['SINGLE'])
        return problems_per_subline_idx

    def analyze_subline(self, text: str, **kwargs) -> Set[str]:
        return super().analyze_subline(text, None, 0, 0, True, kwargs.get('editor_font_map', {}), kwargs.get('editor_line_width_threshold', 0), "")