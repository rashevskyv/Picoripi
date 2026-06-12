from typing import Tuple, List, Optional, Set
import re
from utils.utils import calculate_string_width, remove_all_tags
from plugins.common.text_fixer import GenericTextFixer
from .config import PROBLEM_WIDTH_EXCEEDED, PROBLEM_SHORT_LINE, PROBLEM_EMPTY_SUBLINE, PROBLEM_BAD_SPACING, PROBLEM_MISSING_ICON_SPACING, PROBLEM_SINGLE_WORD_SUBLINE, PROBLEM_SINGLE_WORD_SUBLINE_NON_START

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

    def _fix_short_lines(self, text: str, font_map: dict, threshold: int, logical_hard_limit: Optional[int] = None) -> str:
        sublines = self._get_sublines_with_tags(text)
        if len(sublines) < 2:
            return text
        lines_per_page = getattr(self.mw, 'lines_per_page', 4)
        i = 0
        while i < len(sublines) - 1:
            current_text, current_tag = sublines[i]
            next_text, next_tag = sublines[i+1]
            
            is_boundary = (i + 1) % lines_per_page == 0

            # Don't merge across empty lines (page-boundary padding)
            if not next_text.strip():
                i += 1
                continue

            if is_boundary:
                is_next_single_word_lowercase = (
                    self.problem_analyzer._check_single_word_subline_generic(next_text) and
                    not self.problem_analyzer._is_single_word_ok_generic(next_text)
                )
                if not is_next_single_word_lowercase:
                    i += 1
                    continue
                
                limit = logical_hard_limit if logical_hard_limit is not None else getattr(self.mw, 'game_dialog_max_width_pixels', threshold)
                if not isinstance(limit, (int, float)):
                    limit = threshold
                
                width_current = calculate_string_width(current_text, font_map)
                width_next = calculate_string_width(next_text.strip(), font_map)
                space_width = calculate_string_width(" ", font_map)
                if width_current + space_width + width_next > limit:
                    i += 1
                    continue
                    
            if self.problem_analyzer._check_short_line(current_text, next_text, font_map, threshold) or is_boundary:
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
                             allowed_problems: Optional[Set[str]] = None,
                             block_idx: Optional[int] = None,
                             string_idx: Optional[int] = None,
                             page_local: bool = False,
                             disable_pagination: bool = False) -> Tuple[str, bool]:
        if page_local:
            return self.autofix_page_local_wrapper(
                self.autofix_data_string,
                data_string,
                editor_font_map,
                editor_line_width_threshold,
                logical_hard_limit,
                allowed_problems,
                block_idx,
                string_idx
            )

        if logical_hard_limit is None:
            logical_hard_limit = editor_line_width_threshold

        global_max = getattr(self.mw, 'game_dialog_max_width_pixels', editor_line_width_threshold) if self.mw else editor_line_width_threshold
        try:
            global_max_val = int(global_max)
        except (TypeError, ValueError):
            global_max_val = editor_line_width_threshold
            
        standard_threshold = getattr(self.mw, 'line_width_warning_threshold_pixels', editor_line_width_threshold) if self.mw else editor_line_width_threshold
        try:
            standard_threshold_val = int(standard_threshold)
        except (TypeError, ValueError):
            standard_threshold_val = editor_line_width_threshold

        if logical_hard_limit != global_max_val and global_max_val > 0:
            editor_line_width_threshold = int(logical_hard_limit * (standard_threshold_val / global_max_val))

        original_text = str(data_string)
        modified_text = original_text
        from .config import DEFAULT_AUTOFIX_SETTINGS
        autofix_config = DEFAULT_AUTOFIX_SETTINGS.copy()
        if self.mw and hasattr(self.mw, 'autofix_enabled') and self.mw.autofix_enabled:
            autofix_config.update(self.mw.autofix_enabled)
        max_iterations = 5
        for _ in range(max_iterations):
            text_before_pass = modified_text
            
            if allowed_problems is not None:
                if PROBLEM_EMPTY_SUBLINE in allowed_problems:
                    modified_text = self._fix_empty_sublines(modified_text)
                if PROBLEM_WIDTH_EXCEEDED in allowed_problems:
                    modified_text = self._fix_width_exceeded(modified_text, editor_font_map, logical_hard_limit)
                if PROBLEM_SHORT_LINE in allowed_problems:
                    modified_text = self._fix_short_lines(modified_text, editor_font_map, editor_line_width_threshold, logical_hard_limit)
            else:
                if autofix_config.get(PROBLEM_EMPTY_SUBLINE, False):
                    modified_text = self._fix_empty_sublines(modified_text)
                if autofix_config.get(PROBLEM_WIDTH_EXCEEDED, False):
                    modified_text = self._fix_width_exceeded(modified_text, editor_font_map, logical_hard_limit)
                if autofix_config.get(PROBLEM_SHORT_LINE, False):
                    modified_text = self._fix_short_lines(modified_text, editor_font_map, editor_line_width_threshold, logical_hard_limit)
                    
            if modified_text == text_before_pass:
                break
                
        has_single_word_allowed = False
        if allowed_problems is not None:
            for p in allowed_problems:
                if "SINGLE_WORD" in p:
                    has_single_word_allowed = True
                    break
        else:
            has_single_word_allowed = autofix_config.get(PROBLEM_SINGLE_WORD_SUBLINE, False) or \
                                      autofix_config.get(PROBLEM_SINGLE_WORD_SUBLINE_NON_START, False)

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

        changed_missing_spacing = False
        is_missing_spacing_allowed = False
        if allowed_problems is not None:
            is_missing_spacing_allowed = PROBLEM_MISSING_ICON_SPACING in allowed_problems
        else:
            is_missing_spacing_allowed = autofix_config.get(PROBLEM_MISSING_ICON_SPACING, False)

        if is_missing_spacing_allowed:
            from utils.utils import fix_missing_icon_spacing, is_visible_tag
            default_tag_mappings = getattr(self.mw, "default_tag_mappings", {}) if self.mw else {}
            icon_sequences = getattr(self.mw, "icon_sequences", []) if self.mw else []
            
            def check_visible(t):
                return is_visible_tag(t, default_tag_mappings, editor_font_map, icon_sequences)
                
            fixed_spacing_text = fix_missing_icon_spacing(final_text, check_visible)
            if fixed_spacing_text != final_text:
                final_text = fixed_spacing_text
                changed_missing_spacing = True

        original_message_text = None
        if self.mw and block_idx is not None and string_idx is not None:
            if (self.mw.data_store.data and 
                0 <= block_idx < len(self.mw.data_store.data) and 
                0 <= string_idx < len(self.mw.data_store.data[block_idx])):
                original_message_text = str(self.mw.data_store.data[block_idx][string_idx])

        lines_per_page = getattr(self.mw, 'lines_per_page', 4) if self.mw else 4
        changed_shift = False
        changed_compact = False
        if not disable_pagination:
            final_text, changed_shift = self._shift_split_sentences(final_text, lines_per_page, original_message_text, block_idx=block_idx, string_idx=string_idx)
            short_line_allowed = (
                PROBLEM_SHORT_LINE in allowed_problems
                if allowed_problems is not None
                else autofix_config.get(PROBLEM_SHORT_LINE, False)
            )
            if short_line_allowed:
                changed_compact_val = self._compact_sentences_on_pages(
                    final_text, editor_font_map, editor_line_width_threshold, lines_per_page
                )
                final_text, changed_compact = changed_compact_val

        changed_orphans = False
        if has_single_word_allowed:
            final_text, changed_orphans = self._fix_single_word_orphans_generic(final_text)

        return final_text, (final_text != original_text or changed_missing_spacing or changed_shift or changed_compact or changed_orphans)