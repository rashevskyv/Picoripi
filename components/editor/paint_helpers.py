import re
from PyQt5.QtGui import QTextBlock
from PyQt5.QtWidgets import QMainWindow
from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, SPACE_DOT_SYMBOL, ALL_TAGS_PATTERN

SENTENCE_END_PUNCTUATION_PATTERN = re.compile(r'[.,!?](?:["\']|")?$')

class LNETPaintHelpers:
    def __init__(self, editor):
        self.editor = editor

    def _map_no_tag_index_to_raw_text_index(self, raw_qtextline_text: str, line_text_segment_no_tags: str, target_no_tag_index_in_segment: int) -> int:
        if target_no_tag_index_in_segment == 0:
            current_idx = 0
            while current_idx < len(raw_qtextline_text):
                char = raw_qtextline_text[current_idx]
                if char.isspace() or char == SPACE_DOT_SYMBOL:
                    current_idx += 1
                    continue
                is_tag_char = False
                for tag_match in ALL_TAGS_PATTERN.finditer(raw_qtextline_text[current_idx:]):
                    if tag_match.start() == 0:
                        tag_content = tag_match.group(0)
                        current_idx += len(tag_content)
                        is_tag_char = True
                        break
                if is_tag_char:
                    continue
                return current_idx
            return 0

        words_no_tags = list(re.finditer(r'\S+', line_text_segment_no_tags))
        target_word_text_no_tags = ""
        current_word_idx_no_tags = -1

        for i, word_match_no_tags in enumerate(words_no_tags):
            if word_match_no_tags.start() == target_no_tag_index_in_segment:
                target_word_text_no_tags = word_match_no_tags.group(0)
                current_word_idx_no_tags = i
                break

        if not target_word_text_no_tags :
            return min(target_no_tag_index_in_segment, len(raw_qtextline_text) -1 if raw_qtextline_text else 0)

        target_word_occurrence_count = 0
        for i in range(current_word_idx_no_tags + 1):
            if words_no_tags[i].group(0) == target_word_text_no_tags:
                target_word_occurrence_count += 1

        actual_word_occurrence_in_raw = 0
        for raw_match in re.finditer(r'\S+', raw_qtextline_text):
            raw_word_from_match = raw_match.group(0)
            raw_word_with_spaces = convert_dots_to_spaces_from_editor(raw_word_from_match)
            cleaned_word_for_comparison = remove_all_tags(raw_word_with_spaces)

            if cleaned_word_for_comparison == target_word_text_no_tags:
                actual_word_occurrence_in_raw += 1
                if actual_word_occurrence_in_raw == target_word_occurrence_count:
                    return raw_match.start()

        return min(target_no_tag_index_in_segment, len(raw_qtextline_text) -1 if raw_qtextline_text else 0)