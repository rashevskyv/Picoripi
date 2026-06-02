from typing import Optional, Set, List
import re
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor

class GenericProblemAnalyzer:
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        self.mw = main_window_ref
        self.tag_manager = tag_manager_ref
        self.problem_definitions = problem_definitions_ref
        self.problem_ids = problem_ids_ref

    def _check_bad_spacing(self, text: str) -> bool:
        if not text:
            return False
        clean_text = convert_dots_to_spaces_from_editor(text)
        clean_text = remove_all_tags(clean_text)
        if clean_text.startswith(" "):
            return True
        if "  " in clean_text:
            return True
        return False

    def _check_single_word_subline_generic(self, subline_text: str) -> bool:
        text_no_tags = remove_all_tags(subline_text).strip()
        if not text_no_tags: 
            return False
        words = text_no_tags.split()
        if len(words) != 1:
            return False
        word = words[0]
        word_content_pattern = re.compile(r'[\wа-яА-ЯіїІїЄєґҐ]+') 
        return bool(word_content_pattern.search(word))

    def _is_single_word_ok_generic(self, subline_text: str) -> bool:
        text_no_tags = remove_all_tags(subline_text).strip()
        if not text_no_tags:
            return True
        words = text_no_tags.split()
        if len(words) != 1:
            return True
        word = words[0]
        
        first_letter_match = re.search(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ]', word)
        if not first_letter_match:
            return True
            
        is_capital = first_letter_match.group(0).isupper()
        
        # Word starting with a capital letter is ALWAYS ok (no warning)
        if is_capital:
            return True
            
        return False

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
        found_problems = set()
        
        # Common width check
        limit = logical_hard_limit if logical_hard_limit is not None else getattr(self.mw, 'game_dialog_max_width_pixels', editor_line_width_threshold)
        if not isinstance(limit, (int, float)):
            limit = editor_line_width_threshold
        pixel_width = calculate_string_width(text.rstrip(), editor_font_map)
        if pixel_width > limit:
            if hasattr(self.problem_ids, 'PROBLEM_WIDTH_EXCEEDED'):
                found_problems.add(self.problem_ids.PROBLEM_WIDTH_EXCEEDED)
            elif 'WIDTH' in self.problem_ids:
                 found_problems.add(self.problem_ids['WIDTH'])

        # Spacing check
        if self._check_bad_spacing(text):
            if isinstance(self.problem_ids, dict):
                if 'BAD_SPACING' in self.problem_ids:
                    found_problems.add(self.problem_ids['BAD_SPACING'])
            else:
                if hasattr(self.problem_ids, 'PROBLEM_BAD_SPACING'):
                    found_problems.add(self.problem_ids.PROBLEM_BAD_SPACING)

        return found_problems
