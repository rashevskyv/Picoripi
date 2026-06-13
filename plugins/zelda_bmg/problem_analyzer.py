import re
from typing import Optional, Set, Dict, Any, List
from utils.utils import calculate_string_width, remove_all_tags
from plugins.common.problem_analyzer import GenericProblemAnalyzer

SENTENCE_END_PUNCTUATION_CHARS_ZBMG = ['.', '!', '?']
OPTIONAL_TRAILING_CHARS_ZBMG = ['"', "'"]

class ProblemAnalyzer(GenericProblemAnalyzer):
    """Problem analyzer implementation."""
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        """Initialize a new instance."""
        super().__init__(main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)

    def _ends_with_sentence_punctuation_zbmg(self, text_no_tags_stripped: str) -> bool:
        """Internal helper to ends with sentence punctuation zbmg."""
        if not text_no_tags_stripped:
            return False
        last_char = text_no_tags_stripped[-1]
        if last_char in OPTIONAL_TRAILING_CHARS_ZBMG:
            if len(text_no_tags_stripped) > 1:
                char_before_last = text_no_tags_stripped[-2]
                return char_before_last in SENTENCE_END_PUNCTUATION_CHARS_ZBMG
            return False
        return last_char in SENTENCE_END_PUNCTUATION_CHARS_ZBMG

    def _calculate_width(self, text: str, font_map: dict) -> int:
        """Internal helper to calculate width."""
        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', None) if self.mw else None
        
        if self.mw and hasattr(self.mw, 'current_game_rules') and self.mw.current_game_rules:
            if hasattr(self.mw.current_game_rules, 'calculate_string_width_override'):
                override_val = self.mw.current_game_rules.calculate_string_width_override(text, font_map)
                if override_val is not None:
                    return override_val
                    
        return calculate_string_width(
            text, 
            font_map, 
            default_char_width=6,
            icon_sequences=icon_sequences, 
            default_tag_mappings=default_tag_mappings
        )

    def _check_short_line_zbmg(self, current_subline_text: str, next_subline_text: str, font_map: dict, threshold: int) -> bool:
        """Internal helper to check short line zbmg."""
        if next_subline_text.lstrip().startswith("{*}") or next_subline_text.lstrip().startswith("{tab}"):
            return False

        from utils.utils import has_visible_content, extract_first_word_with_tags, get_line_words_and_visible_tags

        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}
        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []

        if not has_visible_content(current_subline_text, default_tag_mappings, font_map, icon_sequences):
            return False

        current_subline_no_tags_stripped = remove_all_tags(current_subline_text).strip()
        if self._ends_with_sentence_punctuation_zbmg(current_subline_no_tags_stripped):
            return False

        # Don't merge if the next subline starts with a page break or pause escape code
        if re.search(r'^\s*\{(?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)\}', next_subline_text, re.IGNORECASE):
            return False

        first_word_next, remaining_next = extract_first_word_with_tags(next_subline_text)
        if not first_word_next:
            return False
        
        width_current_rstripped = self._calculate_width(current_subline_text.rstrip(), font_map)
        space_width = self._calculate_width(" ", font_map)

        # Check if first_word_next is a single-letter word
        clean_first = remove_all_tags(first_word_next).strip()
        clean_first_letters = re.sub(r'[^\w]', '', clean_first)
        is_single_letter = len(clean_first_letters) == 1 and clean_first_letters.isalpha()

        if is_single_letter and remaining_next.strip():
            second_word_next, _ = extract_first_word_with_tags(remaining_next)
            combined_word = first_word_next + " " + second_word_next
            width_first_word_next = self._calculate_width(combined_word, font_map)
        else:
            width_first_word_next = self._calculate_width(first_word_next, font_map)

        # If next line has exactly two words, only allow warning if BOTH words can fit
        next_words = get_line_words_and_visible_tags(next_subline_text, self.mw)
        if len(next_words) == 2:
            width_next_full = self._calculate_width(next_subline_text.strip(), font_map)
            return (threshold - width_current_rstripped) >= (width_next_full + space_width)

        return (threshold - width_current_rstripped) >= (width_first_word_next + space_width)

    def check_for_empty_first_line_of_page(self, text: str) -> List[int]:
        """Check for empty first line of page."""
        text_alias = re.sub(r'\{escape:6:000a\}', '{*}', text, flags=re.IGNORECASE)
        if "{*}" in text_alias:
            return []
        lines = text.split('\n')
        problem_lines = []
        lines_per_page = 4
        if self.mw and hasattr(self.mw, 'lines_per_page'):
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

    def analyze_data_string(self, data_string: str, font_map: dict, threshold: int, logical_hard_limit: Optional[int] = None) -> List[Set[str]]:
        # Convert tags to aliases for rules check
        """Analyze data string."""
        data_string_alias = re.sub(r'\{escape:6:000a\}', '{*}', data_string, flags=re.IGNORECASE)
        data_string_alias = re.sub(r'\{escape:6:000b\}', '{tab}', data_string_alias, flags=re.IGNORECASE)
        
        sublines = data_string_alias.split('\n')
        problems_per_subline = [set() for _ in sublines]
        empty_first_lines = self.check_for_empty_first_line_of_page(data_string_alias)
        for line_idx in empty_first_lines:
            if line_idx < len(problems_per_subline):
                problems_per_subline[line_idx].add(self.problem_ids.PROBLEM_EMPTY_FIRST_LINE_OF_PAGE)
        
        limit = logical_hard_limit if logical_hard_limit is not None else getattr(self.mw, 'game_dialog_max_width_pixels', threshold)
        if not isinstance(limit, (int, float)):
            limit = threshold
            
        has_star_tag = "{*}" in data_string_alias
        
        # Check {*} and {tab} formatting rules
        in_tab_section = False
        for i, subline in enumerate(sublines):
            stripped_subline = subline.strip()
            if stripped_subline.startswith("{*}"):
                in_tab_section = True
                if re.search(r'^\{\*\}\s', subline.lstrip()) or "{tab}" in subline:
                    problems_per_subline[i].add(self.problem_ids.PROBLEM_STAR_TAG_RULES)
            elif in_tab_section:
                starts_with_tab = subline.startswith("{tab}")
                has_space_after_tab = subline.startswith("{tab} ")
                has_other_tabs = "{tab}" in subline[5:] if starts_with_tab else "{tab}" in subline
                if not starts_with_tab or has_space_after_tab or has_other_tabs:
                    problems_per_subline[i].add(self.problem_ids.PROBLEM_STAR_TAG_RULES)
            else:
                if "{tab}" in subline:
                    problems_per_subline[i].add(self.problem_ids.PROBLEM_STAR_TAG_RULES)

        for i, subline in enumerate(sublines):
            # Calculate width with original string tags to preserve exact escape tag lengths
            orig_subline = re.sub(r'\{\*\}', '{escape:6:000a}', subline)
            orig_subline = re.sub(r'\{tab\}', '{escape:6:000b}', orig_subline)
            pixel_width_subline = self._calculate_width(orig_subline.rstrip(), font_map)
            if pixel_width_subline > limit:
                problems_per_subline[i].add(self.problem_ids.PROBLEM_WIDTH_EXCEEDED)
            if self._check_bad_spacing(subline):
                problems_per_subline[i].add(self.problem_ids.PROBLEM_BAD_SPACING)
            if self._check_missing_icon_spacing(subline):
                problems_per_subline[i].add(self.problem_ids.PROBLEM_MISSING_ICON_SPACING)
            
            if has_star_tag:
                lines_per_page = len(sublines) + 1
            else:
                lines_per_page = 4
                if self.mw and hasattr(self.mw, 'lines_per_page'):
                    lines_per_page = getattr(self.mw, 'lines_per_page', 4)

            next_subline = sublines[i + 1] if i + 1 < len(sublines) else None
            if next_subline is not None:
                if not next_subline.lstrip().startswith("{*}") and not next_subline.lstrip().startswith("{tab}"):
                    if (i + 1) % lines_per_page != 0:
                        if self._check_short_line_zbmg(subline, next_subline, font_map, threshold):
                            problems_per_subline[i].add(self.problem_ids.PROBLEM_SHORT_LINE)
            
            if not has_star_tag and len(sublines) > 1:
                if self._check_single_word_subline_generic(subline):
                    if not self._is_single_word_ok_generic(subline):
                        if i % lines_per_page == 0:
                            page_lines = sublines[i : i + lines_per_page]
                            has_content_after = any(line.strip() for line in page_lines[1:])
                            if has_content_after:
                                problems_per_subline[i].add(self.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE)
                            else:
                                problems_per_subline[i].add(self.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE_NON_START)
                        else:
                            problems_per_subline[i].add(self.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE_NON_START)
                    
        return problems_per_subline

    def analyze_subline(self, *args, **kwargs) -> Set[str]:
        """Analyze subline."""
        return set()
