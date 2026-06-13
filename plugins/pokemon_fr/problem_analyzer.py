from typing import Optional, Set, List, Tuple
import re
from utils.utils import calculate_string_width, remove_all_tags
from plugins.common.problem_analyzer import GenericProblemAnalyzer
from .config import (PROBLEM_WIDTH_EXCEEDED, PROBLEM_SHORT_LINE, PROBLEM_EMPTY_SUBLINE,
                     PROBLEM_SINGLE_WORD_SUBLINE, PROBLEM_SINGLE_WORD_SUBLINE_NON_START, PROBLEM_TAG_WARNING,
                     PROBLEM_BAD_SPACING, PROBLEM_MISSING_ICON_SPACING)

SENTENCE_END_PUNCTUATION_CHARS = ['.', '!', '?']
NEWLINE_TAGS_PATTERN = re.compile(r'(\\n|\\p|\\l)')

class ProblemAnalyzer(GenericProblemAnalyzer):
    """Problem analyzer implementation."""
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        """Initialize a new instance."""
        super().__init__(main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)
        self.problem_ids = {
            'WIDTH': PROBLEM_WIDTH_EXCEEDED,
            'SHORT': PROBLEM_SHORT_LINE,
            'EMPTY': PROBLEM_EMPTY_SUBLINE,
            'SINGLE': PROBLEM_SINGLE_WORD_SUBLINE,
            'SINGLE_NON_START': PROBLEM_SINGLE_WORD_SUBLINE_NON_START,
            'TAG': PROBLEM_TAG_WARNING,
            'BAD_SPACING': PROBLEM_BAD_SPACING,
            'MISSING_ICON_SPACING': PROBLEM_MISSING_ICON_SPACING
        }

    def _get_sublines_from_data_string(self, data_string: str) -> List[Tuple[str, str]]:
        """Internal helper to get the sublines from data string."""
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
        """Internal helper to ends with sentence punctuation."""
        if not text_no_tags_stripped:
            return False
        return text_no_tags_stripped[-1] in SENTENCE_END_PUNCTUATION_CHARS

    def _check_short_line(self, current_subline: str, next_subline: str, font_map: dict, threshold: int) -> bool:
        """Internal helper to check short line."""
        from utils.utils import has_visible_content, extract_first_word_with_tags, get_line_words_and_visible_tags

        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}
        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []

        if not has_visible_content(current_subline, default_tag_mappings, font_map, icon_sequences):
            return False

        current_subline_no_tags_stripped = remove_all_tags(current_subline).strip()
        if self._ends_with_sentence_punctuation(current_subline_no_tags_stripped):
            return False

        first_word_next, _ = extract_first_word_with_tags(next_subline)
        if not first_word_next:
            return False

        width_current = calculate_string_width(
            current_subline, 
            font_map, 
            icon_sequences=icon_sequences, 
            default_tag_mappings=default_tag_mappings
        )
        width_first_word_next = calculate_string_width(
            first_word_next, 
            font_map, 
            icon_sequences=icon_sequences, 
            default_tag_mappings=default_tag_mappings
        )
        space_width = calculate_string_width(" ", font_map)

        # If next line has exactly two words, only allow warning if BOTH words can fit
        next_words = get_line_words_and_visible_tags(next_subline, self.mw)
        if len(next_words) == 2:
            width_next_full = calculate_string_width(
                next_subline.strip(), 
                font_map,
                icon_sequences=icon_sequences,
                default_tag_mappings=default_tag_mappings
            )
            return (width_current + space_width + width_next_full) <= threshold

        return (width_current + space_width + width_first_word_next) <= threshold

    def analyze_data_string(self, data_string: str, font_map: dict, threshold: int, logical_hard_limit: Optional[int] = None) -> List[Set[str]]:
        """Analyze data string."""
        if not data_string:
            return []
        sublines_with_tags = self._get_sublines_from_data_string(data_string)
        problems_per_subline_idx = [set() for _ in sublines_with_tags]
        is_only_one_subline_in_total = len(sublines_with_tags) == 1
        limit = logical_hard_limit if logical_hard_limit is not None else getattr(self.mw, 'game_dialog_max_width_pixels', threshold)
        if not isinstance(limit, (int, float)):
            limit = threshold
        for i, (text_part, newline_tag) in enumerate(sublines_with_tags):
            text_part_no_tags = remove_all_tags(text_part)
            width = calculate_string_width(text_part, font_map)
            if (text_part.count('{') != text_part.count('}')) or (text_part.count('[') != text_part.count(']')):
                problems_per_subline_idx[i].add(self.problem_ids['TAG'])
            if not text_part_no_tags.strip():
                if i < len(sublines_with_tags) - 1:
                     problems_per_subline_idx[i].add(self.problem_ids['EMPTY'])
            if width > limit:
                 problems_per_subline_idx[i].add(self.problem_ids['WIDTH'])
            if self._check_bad_spacing(text_part):
                 problems_per_subline_idx[i].add(self.problem_ids['BAD_SPACING'])
            if self._check_missing_icon_spacing(text_part):
                 problems_per_subline_idx[i].add(self.problem_ids['MISSING_ICON_SPACING'])
            lines_per_page = 4
            if self.mw and hasattr(self.mw, 'lines_per_page'):
                lines_per_page = getattr(self.mw, 'lines_per_page', 4)

            if i + 1 < len(sublines_with_tags):
                if (i + 1) % lines_per_page != 0:
                    next_text_part, _ = sublines_with_tags[i+1]
                    if self._check_short_line(text_part, next_text_part, font_map, threshold):
                        problems_per_subline_idx[i].add(self.problem_ids['SHORT'])

            if len(sublines_with_tags) > 1:
                if self._check_single_word_subline_generic(text_part):
                    if not self._is_single_word_ok_generic(text_part):
                        if i % lines_per_page == 0:
                            page_lines = [part for part, _ in sublines_with_tags[i : i + lines_per_page]]
                            has_content_after = any(line.strip() for line in page_lines[1:])
                            if has_content_after:
                                problems_per_subline_idx[i].add(self.problem_ids['SINGLE'])
                            else:
                                problems_per_subline_idx[i].add(self.problem_ids['SINGLE_NON_START'])
                        else:
                            problems_per_subline_idx[i].add(self.problem_ids['SINGLE_NON_START'])
        return problems_per_subline_idx

    def analyze_subline(self, text: str, **kwargs) -> Set[str]:
        """Analyze subline."""
        return super().analyze_subline(
            text, None, 0, 0, True, 
            kwargs.get('editor_font_map', {}), 
            kwargs.get('editor_line_width_threshold', 0), 
            "", 
            logical_hard_limit=kwargs.get('logical_hard_limit', None)
        )