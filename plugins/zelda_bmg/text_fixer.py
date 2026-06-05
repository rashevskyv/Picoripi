import re
from typing import Optional, Set, Dict, Any, Tuple
from plugins.common.text_fixer import GenericTextFixer
from .tag_logic import ANY_TAG_PATTERN_BMG
from utils.utils import remove_all_tags
from .config import PROBLEM_WIDTH_EXCEEDED, PROBLEM_SHORT_LINE, PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY, PROBLEM_EMPTY_FIRST_LINE_OF_PAGE, PROBLEM_BAD_SPACING, PROBLEM_MISSING_ICON_SPACING, PROBLEM_SINGLE_WORD_SUBLINE, PROBLEM_SINGLE_WORD_SUBLINE_NON_START

WORD_CHAR_PATTERN_ZBMG = re.compile(r"^[a-zA-Zа-яА-ЯіїєґІЇЄҐ]$")
CLOSING_COLOR_TAG_BMG = "{COLOR_DEFAULT}"
PUNCTUATION_PATTERN_ZBMG = re.compile(r"^[,\.!?]$")

class TextFixer(GenericTextFixer):
    def __init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref):
        super().__init__(main_window_ref, tag_manager_ref, problem_analyzer_ref)

    def _is_forced_alias(self, tag: str) -> bool:
        if tag.lower().startswith("{f:"):
            return True
        mappings = getattr(self.mw, "default_tag_mappings", {}) if self.mw else {}
        if mappings:
            for alias, original in mappings.items():
                if original == tag and alias.lower().startswith("{f:"):
                    return True
        return False

    def _fix_empty_odd_sublines_zbmg(self, text: str) -> Tuple[str, bool]:
        sub_lines = text.split('\n')
        if len(sub_lines) <= 1:
            return text, False
        new_sub_lines = []
        made_change = False
        for i, sub_line in enumerate(sub_lines):
            is_odd_subline = (i + 1) % 2 != 0
            if ANY_TAG_PATTERN_BMG.search(sub_line):
                new_sub_lines.append(sub_line)
                continue
            
            text_no_tags = remove_all_tags(sub_line)
            stripped_text_no_tags = text_no_tags.strip()
            is_empty_or_zero = not stripped_text_no_tags or stripped_text_no_tags == "0"
            if is_odd_subline and is_empty_or_zero:
                made_change = True
                continue
            new_sub_lines.append(sub_line)
        if not made_change:
            return text, False
        if text and not new_sub_lines:
            return "", True
        final_text_list = []
        for i in range(len(new_sub_lines)):
            if i > 0 and not new_sub_lines[i].strip() and not new_sub_lines[i-1].strip():
                continue
            final_text_list.append(new_sub_lines[i])
        joined_text = "\n".join(final_text_list)
        return joined_text, joined_text != text

    def _fix_short_lines_zbmg(self, text: str, font_map: dict, threshold: int, logical_hard_limit: Optional[int] = None) -> Tuple[str, bool]:
        sub_lines = text.split('\n')
        if len(sub_lines) <= 1: return text, False
        original_text = text
        made_change_in_this_fix_pass = True
        lines_per_page = getattr(self.mw, 'lines_per_page', 4)
        while made_change_in_this_fix_pass:
            made_change_in_this_fix_pass = False
            new_sub_lines = list(sub_lines)
            i = len(new_sub_lines) - 2
            while i >= 0:
                current_line = new_sub_lines[i]
                next_line = new_sub_lines[i+1]
                
                is_boundary = (i + 1) % lines_per_page == 0
                if is_boundary:
                    is_next_single_word_lowercase = (
                        self.problem_analyzer._check_single_word_subline_generic(next_line) and
                        not self.problem_analyzer._is_single_word_ok_generic(next_line)
                    )
                    if not is_next_single_word_lowercase:
                        i -= 1
                        continue
                    
                    limit = logical_hard_limit if logical_hard_limit is not None else getattr(self.mw, 'game_dialog_max_width_pixels', threshold)
                    if not isinstance(limit, (int, float)):
                        limit = threshold
                    
                    width_current = self._calculate_width(current_line.rstrip(), font_map)
                    width_next = self._calculate_width(next_line.strip(), font_map)
                    space_width = self._calculate_width(" ", font_map)
                    if width_current + space_width + width_next > limit:
                        i -= 1
                        continue
                
                if self.problem_analyzer._check_short_line_zbmg(current_line, next_line, font_map, threshold) or is_boundary:
                    first_word_next_raw, rest_of_next_line_raw = self._extract_first_word_with_tags_generic(next_line)
                    current_line_rstripped = current_line.rstrip()
                    merged_line = current_line_rstripped
                    if current_line_rstripped and first_word_next_raw:
                        needs_space = False
                        if not current_line_rstripped.endswith(" ") and not first_word_next_raw.startswith(" "):
                            last_char_current = current_line_rstripped[-1]
                            first_char_next = first_word_next_raw[0]
                            is_current_ends_tag = last_char_current == '}'
                            is_next_starts_tag = first_char_next == '{'
                            is_next_starts_word_char = WORD_CHAR_PATTERN_ZBMG.match(first_char_next) is not None
                            if is_current_ends_tag and is_next_starts_word_char: needs_space = True
                            elif not is_current_ends_tag and not is_next_starts_tag: needs_space = True
                            elif not is_current_ends_tag and is_next_starts_tag: needs_space = True
                        if needs_space: merged_line += " "
                    merged_line += first_word_next_raw
                    new_sub_lines[i] = merged_line
                    new_sub_lines[i+1] = rest_of_next_line_raw
                    if not new_sub_lines[i+1].strip() and len(new_sub_lines) > i + 1 :
                        del new_sub_lines[i+1]
                    made_change_in_this_fix_pass = True
                    sub_lines = list(new_sub_lines)
                    break
                i -= 1
            if not made_change_in_this_fix_pass: break
        final_text = "\n".join(sub_lines)
        return final_text, final_text != original_text

    def _cleanup_spaces_around_tags_zbmg(self, text: str) -> Tuple[str, bool]:
        original_text = text
        pattern = re.compile(r"(?P<tag>\{[^}]*\})(?P<space> )(?P<after_space>.)?")
        current_pos = 0
        result_parts = []
        last_processed_end = 0
        while current_pos < len(text):
            match = pattern.search(text, current_pos)
            if not match:
                result_parts.append(text[last_processed_end:])
                break
            tag_match_start_pos = match.start("tag")
            result_parts.append(text[last_processed_end:tag_match_start_pos])
            tag_content = match.group("tag")
            space_content = match.group("space")
            char_after_space_content = match.group("after_space") if match.group("after_space") is not None else ""
            result_parts.append(tag_content)
            is_closing_tag = tag_content.lower() in [
                CLOSING_COLOR_TAG_BMG.lower(),
                "{color:white}",
                "{escape:255:000000}"
            ]
            is_forced = self._is_forced_alias(tag_content)
            should_remove_space = False
            if is_forced:
                # Forced aliases act as text, so the space after them should NOT be removed
                should_remove_space = False
            elif is_closing_tag:
                if char_after_space_content and PUNCTUATION_PATTERN_ZBMG.match(char_after_space_content):
                    should_remove_space = True
            else: 
                should_remove_space = True
            if not should_remove_space: 
                result_parts.append(space_content)
            last_processed_end = match.start("after_space") if char_after_space_content else match.end("space")
            current_pos = last_processed_end
        final_text = "".join(result_parts)
        # Force remove spaces before punctuation marks after any tags (e.g. "{tag} ," -> "{tag},")
        final_text = re.sub(r'(\{[^}]*\}|\[[^\]]*\])\s+([,\.!?;:…])', r'\1\2', final_text)
        return final_text, final_text != original_text

    def fix_empty_first_line_of_page(self, text: str) -> Tuple[str, bool]:
        lines = text.split('\n')
        problem_indices = self.problem_analyzer.check_for_empty_first_line_of_page(text)
        if not problem_indices:
            return text, False
        indices_to_remove = set(problem_indices)
        new_lines = [line for i, line in enumerate(lines) if i not in indices_to_remove]
        new_text = '\n'.join(new_lines)
        return new_text, new_text != text

    def autofix_data_string(self,
                             data_string: str,
                             editor_font_map: dict,
                             editor_line_width_threshold: int,
                             logical_hard_limit: Optional[int] = None,
                             allowed_problems: Optional[Set[str]] = None) -> Tuple[str, bool]:
        if logical_hard_limit is None:
            logical_hard_limit = editor_line_width_threshold
        original_text = str(data_string)
        
        from .config import DEFAULT_AUTOFIX_SETTINGS
        autofix_config = getattr(self.mw, 'autofix_enabled', {}) if self.mw else DEFAULT_AUTOFIX_SETTINGS
        if not autofix_config:
            autofix_config = DEFAULT_AUTOFIX_SETTINGS
        def is_allowed(prob_id):
            if allowed_problems is not None:
                return prob_id in allowed_problems
            return autofix_config.get(prob_id, False)

        if is_allowed(PROBLEM_EMPTY_FIRST_LINE_OF_PAGE):
            text_after_page_fix, _ = self.fix_empty_first_line_of_page(original_text)
        else:
            text_after_page_fix = original_text

        if is_allowed(PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY):
            modified_text, _ = self._fix_empty_odd_sublines_zbmg(text_after_page_fix)
        else:
            modified_text = text_after_page_fix

        max_iterations = 10
        for _ in range(max_iterations):
            text_before_pass = modified_text
            changed_merge = False
            changed_split = False
            
            if is_allowed(PROBLEM_SHORT_LINE):
                merged_text, changed_merge = self._fix_short_lines_zbmg(modified_text, editor_font_map, editor_line_width_threshold, logical_hard_limit)
            else:
                merged_text = modified_text
                
            if is_allowed(PROBLEM_WIDTH_EXCEEDED):
                splitted_text, changed_split = self._fix_width_exceeded_generic(merged_text, editor_font_map, logical_hard_limit)
            else:
                splitted_text = merged_text
                
            modified_text = splitted_text
            if not changed_merge and not changed_split:
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

        if has_single_word_allowed:
            modified_text, _ = self._fix_single_word_orphans_generic(modified_text)

        if is_allowed(PROBLEM_BAD_SPACING):
            cleaned_text, _ = self._cleanup_spaces_around_tags_zbmg(modified_text)
            from utils.utils import clean_spaces
            final_text = clean_spaces(cleaned_text)
        else:
            final_text = modified_text

        changed_missing_spacing = False
        if is_allowed(PROBLEM_MISSING_ICON_SPACING):
            from utils.utils import fix_missing_icon_spacing, is_visible_tag
            default_tag_mappings = getattr(self.mw, "default_tag_mappings", {}) if self.mw else {}
            icon_sequences = getattr(self.mw, "icon_sequences", []) if self.mw else []
            
            def check_visible(t):
                return is_visible_tag(t, default_tag_mappings, editor_font_map, icon_sequences)
                
            fixed_spacing_text = fix_missing_icon_spacing(final_text, check_visible)
            if fixed_spacing_text != final_text:
                final_text = fixed_spacing_text
                changed_missing_spacing = True

        lines_per_page = getattr(self.mw, 'lines_per_page', 4) if self.mw else 4
        final_text, changed_shift = self._shift_split_sentences(final_text, lines_per_page)

        return final_text, (final_text != original_text or changed_missing_spacing or changed_shift)
