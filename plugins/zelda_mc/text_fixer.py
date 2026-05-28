import re
from typing import Optional, Set, Dict, Any, Tuple
from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, ALL_TAGS_PATTERN
from plugins.common.text_fixer import GenericTextFixer

WORD_CHAR_PATTERN_ZMC = re.compile(r"^[a-zA-Zа-яА-ЯіїєґІЇЄҐ]$")
ANY_TAG_RE_PATTERN_ZMC = r"(\{[^}]*\}|\[[^\]]*\])"
COLOR_WHITE_TAG_PATTERN_ZMC = re.compile(r"\{Color:White\}", re.IGNORECASE)
PUNCTUATION_PATTERN_ZMC = re.compile(r"^[,\.!?]$")

class TextFixer(GenericTextFixer):
    def __init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref):
        super().__init__(main_window_ref, tag_manager_ref, problem_analyzer_ref)

    def _fix_empty_odd_sublines_zmc(self, text: str) -> Tuple[str, bool]:
        sub_lines = text.split('\n')
        if len(sub_lines) <= 1:
            return text, False
        new_sub_lines = []
        made_change = False
        for i, sub_line in enumerate(sub_lines):
            is_odd_subline = (i + 1) % 2 != 0
            if ALL_TAGS_PATTERN.search(sub_line):
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

    def _fix_short_lines_zmc(self, text: str, font_map: dict, threshold: int) -> Tuple[str, bool]:
        sub_lines = text.split('\n')
        if len(sub_lines) <= 1: return text, False
        original_text = text
        made_change_in_this_fix_pass = True
        while made_change_in_this_fix_pass:
            made_change_in_this_fix_pass = False
            new_sub_lines = list(sub_lines)
            i = len(new_sub_lines) - 2
            while i >= 0:
                current_line = new_sub_lines[i]
                next_line = new_sub_lines[i+1]
                
                if self.problem_analyzer._check_short_line_zmc(current_line, next_line, font_map, threshold):
                    first_word_next_raw, rest_of_next_line_raw = self._extract_first_word_with_tags_generic(next_line)
                    current_line_rstripped = current_line.rstrip()
                    merged_line = current_line_rstripped
                    if current_line_rstripped and first_word_next_raw:
                        needs_space = False
                        if not current_line_rstripped.endswith(" ") and not first_word_next_raw.startswith(" "):
                            last_char_current = current_line_rstripped[-1]
                            first_char_next = first_word_next_raw[0]
                            is_current_ends_tag = last_char_current in ['}', ']']
                            is_next_starts_tag = first_char_next in ['{', '[']
                            is_next_starts_word_char = WORD_CHAR_PATTERN_ZMC.match(first_char_next) is not None
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

    def _fix_blue_sublines_zmc(self, text: str) -> Tuple[str, bool]:
        sub_lines = text.split('\n')
        if len(sub_lines) < 2: 
            return text, False

        new_sub_lines = []
        i = 0
        changed_in_pass = False
        while i < len(sub_lines):
            current_line_text = sub_lines[i]
            new_sub_lines.append(current_line_text)

            is_odd_subline = (i + 1) % 2 != 0
            if not is_odd_subline:
                i += 1
                continue

            text_no_tags = remove_all_tags(current_line_text)
            stripped_text_no_tags = text_no_tags.strip()

            if not stripped_text_no_tags or not stripped_text_no_tags[0].islower():
                i += 1
                continue
            
            if not self.problem_analyzer._ends_with_sentence_punctuation_zmc(stripped_text_no_tags):
                i += 1
                continue

            if i + 1 < len(sub_lines):
                next_line_text = sub_lines[i+1]
                next_line_no_tags = remove_all_tags(next_line_text)
                stripped_next_line_no_tags = next_line_no_tags.strip()
                
                if stripped_next_line_no_tags: 
                    new_sub_lines.append("")
                    changed_in_pass = True
            i += 1
        
        if changed_in_pass:
            final_text = "\n".join(new_sub_lines)
            return final_text, final_text != text
        return text, False

    def _fix_leading_spaces_in_sublines_zmc(self, text: str) -> Tuple[str, bool]:
        sub_lines = text.split('\n')
        fixed_sub_lines = []
        changed = False
        for sub_line_idx, sub_line in enumerate(sub_lines):
            if sub_line.startswith(" ") and not sub_line.startswith("  "):
                fixed_sub_lines.append(sub_line[1:])
                changed = True
            else:
                fixed_sub_lines.append(sub_line)
        if changed:
            final_text = "\n".join(fixed_sub_lines)
            return final_text, final_text != text
        return text, False

    def _cleanup_spaces_around_tags_zmc(self, text: str) -> Tuple[str, bool]:
        original_text = text
        text_changed_this_function_call = False
        pattern = re.compile(f"(?P<tag>{ANY_TAG_RE_PATTERN_ZMC})(?P<space> )(?P<after_space>.)?")
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
            is_color_white = COLOR_WHITE_TAG_PATTERN_ZMC.fullmatch(tag_content)
            should_remove_space = False
            if is_color_white:
                if char_after_space_content and PUNCTUATION_PATTERN_ZMC.match(char_after_space_content):
                    should_remove_space = True
            else: should_remove_space = True
            if not should_remove_space: result_parts.append(space_content)
            else: text_changed_this_function_call = True
            last_processed_end = match.start("after_space") if char_after_space_content else match.end("space")
            current_pos = last_processed_end
        final_text = "".join(result_parts)
        return final_text, final_text != original_text

    def autofix_data_string(self,
                            data_string: str,
                            editor_font_map: dict,
                            editor_line_width_threshold: int) -> Tuple[str, bool]:
        
        original_text = str(data_string)
        
        modified_text, changed1 = self._fix_empty_odd_sublines_zmc(original_text)
        
        merged_text, changed2 = self._fix_short_lines_zmc(modified_text, editor_font_map, editor_line_width_threshold)
        
        splitted_text, changed3 = self._fix_width_exceeded_generic(merged_text, editor_font_map, editor_line_width_threshold)
        
        final_text, changed4 = self._cleanup_spaces_around_tags_zmc(splitted_text)
        final_text, changed5 = self._fix_leading_spaces_in_sublines_zmc(final_text)
        
        return final_text, (changed1 or changed2 or changed3 or changed4 or changed5)