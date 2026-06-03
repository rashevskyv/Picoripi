from typing import Tuple, List
import re
from utils.utils import calculate_string_width, remove_all_tags
from plugins.common.text_fixer import GenericTextFixer
from .config import PROBLEM_WIDTH_EXCEEDED, PROBLEM_SHORT_LINE, PROBLEM_EMPTY_SUBLINE, PROBLEM_BAD_SPACING

NEWLINE_TAGS_PATTERN = re.compile(r'(\\n|\\p|\\l)')

class TextFixer(GenericTextFixer):
    def __init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref):
        super().__init__(main_window_ref, tag_manager_ref, problem_analyzer_ref)

    def _get_sublines_with_tags(self, text: str) -> List[Tuple[str, str]]:
        if not text:
            return []
        sublines = []
        parts = NEWLINE_TAGS_PATTERN.split(text)
        current_text = parts[0]
        for i in range(1, len(parts), 2):
            newline_tag = parts[i]
            text_after = parts[i+1]
            sublines.append((current_text, newline_tag))
            current_text = text_after
        if current_text or (not sublines and text):
            sublines.append((current_text, ""))
        return sublines

    def _reassemble_data_string(self, sublines_with_tags: List[Tuple[str, str]]) -> str:
        return "".join([text + tag for text, tag in sublines_with_tags])

    def _fix_width_exceeded(self, text: str, font_map: dict, threshold: int) -> str:
        sublines = self._get_sublines_with_tags(text)
        new_sublines_reassembled = []
        for text_part, original_newline_tag in sublines:
            width = calculate_string_width(text_part, font_map)
            if width <= threshold:
                new_sublines_reassembled.append((text_part, original_newline_tag))
                continue
            words = text_part.split(' ')
            current_line = ""
            for word in words:
                if not current_line:
                    current_line = word
                    continue
                temp_line = current_line + ' ' + word
                if calculate_string_width(temp_line, font_map) > threshold:
                    new_sublines_reassembled.append((current_line, '\\n'))
                    current_line = word
                else:
                    current_line = temp_line
            new_sublines_reassembled.append((current_line, original_newline_tag))
        return self._reassemble_data_string(new_sublines_reassembled)

    def _fix_short_lines(self, text: str, font_map: dict, threshold: int) -> str:
        sublines = self._get_sublines_with_tags(text)
        if len(sublines) < 2:
            return text
        i = 0
        while i < len(sublines) - 1:
            current_text, current_tag = sublines[i]
            next_text, next_tag = sublines[i+1]
            if self.problem_analyzer._check_short_line(current_text, next_text, font_map, threshold):
                words_in_next = next_text.split(' ')
                first_word_next = words_in_next[0]
                remaining_next = ' '.join(words_in_next[1:])
                new_current_text = (current_text + ' ' + first_word_next).strip()
                if not remaining_next.strip():
                    sublines[i] = (new_current_text, next_tag)
                    sublines.pop(i + 1)
                else:
                    sublines[i] = (new_current_text, current_tag)
                    sublines[i+1] = (remaining_next.strip(), next_tag)
            else:
                i += 1
        return self._reassemble_data_string(sublines)

    def _fix_empty_sublines(self, text: str) -> str:
        sublines = self._get_sublines_with_tags(text)
        if not sublines:
            return text
        filtered_sublines = []
        for i, (text_part, newline_tag) in enumerate(sublines):
            is_empty_and_not_last = not remove_all_tags(text_part).strip() and i < len(sublines) - 1
            if not is_empty_and_not_last:
                filtered_sublines.append((text_part, newline_tag))
        if len(filtered_sublines) == 1 and not remove_all_tags(filtered_sublines[0][0]).strip():
             return self._reassemble_data_string(sublines)
        return self._reassemble_data_string(filtered_sublines)

    def autofix_data_string(self,
                             data_string: str,
                             editor_font_map: dict,
                             editor_line_width_threshold: int,
                             logical_hard_limit: Optional[int] = None,
                             allowed_problems: Optional[Set[str]] = None) -> Tuple[str, bool]:
        if logical_hard_limit is None:
            logical_hard_limit = editor_line_width_threshold
        original_text = str(data_string)
        modified_text = original_text
        autofix_config = getattr(self.mw, 'autofix_enabled', {})
        max_iterations = 5
        for _ in range(max_iterations):
            text_before_pass = modified_text
            
            if allowed_problems is not None:
                if PROBLEM_EMPTY_SUBLINE in allowed_problems:
                    modified_text = self._fix_empty_sublines(modified_text)
                if PROBLEM_WIDTH_EXCEEDED in allowed_problems:
                    modified_text = self._fix_width_exceeded(modified_text, editor_font_map, logical_hard_limit)
                if PROBLEM_SHORT_LINE in allowed_problems:
                    modified_text = self._fix_short_lines(modified_text, editor_font_map, editor_line_width_threshold)
            else:
                if autofix_config.get(PROBLEM_EMPTY_SUBLINE, False):
                    modified_text = self._fix_empty_sublines(modified_text)
                if autofix_config.get(PROBLEM_WIDTH_EXCEEDED, False):
                    modified_text = self._fix_width_exceeded(modified_text, editor_font_map, logical_hard_limit)
                if autofix_config.get(PROBLEM_SHORT_LINE, False):
                    modified_text = self._fix_short_lines(modified_text, editor_font_map, editor_line_width_threshold)
                    
            if modified_text == text_before_pass:
                break
                
        if allowed_problems is not None:
            if PROBLEM_BAD_SPACING in allowed_problems:
                from utils.utils import clean_spaces
                final_text = clean_spaces(modified_text)
            else:
                final_text = modified_text
        else:
            if autofix_config.get(PROBLEM_BAD_SPACING, False):
                from utils.utils import clean_spaces
                final_text = clean_spaces(modified_text)
            else:
                final_text = modified_text
                
        return final_text, final_text != original_text