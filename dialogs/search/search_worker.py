# dialogs/search/search_worker.py
import re
from PyQt6.QtCore import QThread, pyqtSignal
from utils.logging_utils import log_error
from utils.utils import prepare_text_for_tagless_search, is_fuzzy_match, find_smart_matches
from dialogs.search.search_utils import prepare_text_for_tagless_search_with_mapping

class SearchWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list, str, list, list, list) # items_to_review, current_text, line_numbers, block_indices, unique_string_indices
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, mode: str, params: dict):
        super().__init__()
        self.mode = mode
        self.params = params
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self.mode == 'local':
                self._run_local()
            elif self.mode == 'global':
                self._run_global()
        except Exception as e:
            log_error(f"SearchWorker: Error: {e}", exc_info=True)
            self.error.emit(str(e))

    def _run_local(self):
        text = self.params['text']
        query = self.params['query']
        ignore_tags = self.params['ignore_tags']
        is_fuzzy = self.params['is_fuzzy']
        case_sensitive = self.params['case_sensitive']
        line_numbers = self.params.get('line_numbers', [])
        block_idx = self.params.get('block_idx', -1)
        block_indices = self.params.get('block_indices', [])

        items_to_review = []
        effective_query = query
        if ignore_tags:
            effective_query = prepare_text_for_tagless_search(query)

        if not effective_query:
            self.finished.emit([], text, line_numbers, block_indices, [])
            return

        lines = text.split('\n')
        total_lines = len(lines)
        char_offset = 0

        for line_idx, line in enumerate(lines):
            if self._is_cancelled:
                self.cancelled.emit()
                return

            if line_numbers and line_idx < len(line_numbers) and line_numbers[line_idx] is None:
                char_offset += len(line) + 1
                continue

            if ignore_tags:
                clean_line, mapping = prepare_text_for_tagless_search_with_mapping(line)
            else:
                clean_line = line.replace('·', ' ')
                mapping = list(range(len(line)))

            if is_fuzzy:
                word_pattern = re.compile(r'\w+')
                for match in word_pattern.finditer(clean_line):
                    if self._is_cancelled:
                        self.cancelled.emit()
                        return
                    word = match.group(0)
                    if is_fuzzy_match(effective_query, word, threshold=0.75):
                        start_in_clean = match.start()
                        end_in_clean = match.end()

                        raw_start = mapping[start_in_clean]
                        raw_end = mapping[end_in_clean - 1] + 1

                        start_pos = char_offset + raw_start
                        end_pos = char_offset + raw_end
                        matched_text = line[raw_start:raw_end]
                        items_to_review.append((start_pos, end_pos, matched_text, line_idx))
            else:
                matches = find_smart_matches(clean_line, effective_query, case_sensitive)
                for start_in_clean, end_in_clean in matches:
                    if self._is_cancelled:
                        self.cancelled.emit()
                        return
                    raw_start = mapping[start_in_clean]
                    raw_end = mapping[end_in_clean - 1] + 1

                    start_pos = char_offset + raw_start
                    end_pos = char_offset + raw_end
                    matched_text = line[raw_start:raw_end]
                    items_to_review.append((start_pos, end_pos, matched_text, line_idx))

            char_offset += len(line) + 1
            if line_idx % 20 == 0 or line_idx == total_lines - 1:
                if total_lines > 0:
                    self.progress.emit(int((line_idx + 1) / total_lines * 100))

        if not self._is_cancelled:
            self.finished.emit(items_to_review, text, line_numbers, block_indices, [])
        else:
            self.cancelled.emit()

    def _run_global(self):
        data = self.params['data']
        data_processor = self.params['data_processor']
        query = self.params['query']
        case_sensitive = self.params['case_sensitive']
        search_in_original = self.params['search_in_original']
        ignore_tags = self.params['ignore_tags']
        is_fuzzy = self.params['is_fuzzy']

        all_lines = []
        total_blocks = len(data)

        for b_idx in range(total_blocks):
            if self._is_cancelled:
                self.cancelled.emit()
                return
            block_data = data[b_idx]
            if not isinstance(block_data, list):
                continue
            for string_idx in range(len(block_data)):
                if search_in_original:
                    text = data_processor._get_string_from_source(b_idx, string_idx, data, "dialog_original")
                else:
                    text, _ = data_processor.get_current_string_text(b_idx, string_idx)
                if text is not None:
                    all_lines.append((b_idx, string_idx, text))

        text_parts = []
        line_numbers = []
        block_indices = []
        unique_string_indices = []

        effective_query = query
        if ignore_tags and query:
            effective_query = prepare_text_for_tagless_search(query)

        total_all_lines = len(all_lines)
        if query and effective_query and total_all_lines > 0:
            if is_fuzzy:
                word_pattern = re.compile(r'\w+')
                for idx, (b_idx, string_idx, text) in enumerate(all_lines):
                    if self._is_cancelled:
                        self.cancelled.emit()
                        return
                    if ignore_tags:
                        text_for_search = prepare_text_for_tagless_search(text)
                    else:
                        text_for_search = text.replace('·', ' ')

                    has_match = False
                    for match in word_pattern.finditer(text_for_search):
                        word = match.group(0)
                        if is_fuzzy_match(effective_query, word, threshold=0.75):
                            has_match = True
                            break
                    if has_match:
                        text_parts.append(text)
                        pair = (b_idx, string_idx)
                        if not unique_string_indices or unique_string_indices[-1] != pair:
                            unique_string_indices.append(pair)
                        subline_count = text.count('\n') + 1
                        for _ in range(subline_count):
                            line_numbers.append(string_idx)
                            block_indices.append(b_idx)

                    if idx % 100 == 0 or idx == total_all_lines - 1:
                        self.progress.emit(int((idx + 1) / total_all_lines * 50))
            else:
                compare_query = effective_query if case_sensitive else effective_query.lower()
                for idx, (b_idx, string_idx, text) in enumerate(all_lines):
                    if self._is_cancelled:
                        self.cancelled.emit()
                        return
                    if ignore_tags:
                        text_for_search = prepare_text_for_tagless_search(text)
                    else:
                        text_for_search = text.replace('·', ' ')

                    compare_text = text_for_search if case_sensitive else text_for_search.lower()
                    if compare_query in compare_text:
                        text_parts.append(text)
                        pair = (b_idx, string_idx)
                        if not unique_string_indices or unique_string_indices[-1] != pair:
                            unique_string_indices.append(pair)
                        subline_count = text.count('\n') + 1
                        for _ in range(subline_count):
                            line_numbers.append(string_idx)
                            block_indices.append(b_idx)

                    if idx % 100 == 0 or idx == total_all_lines - 1:
                        self.progress.emit(int((idx + 1) / total_all_lines * 50))

        current_text = '\n'.join(text_parts)

        items_to_review = []
        if current_text:
            lines = current_text.split('\n')
            total_lines = len(lines)
            char_offset = 0
            for line_idx, line in enumerate(lines):
                if self._is_cancelled:
                    self.cancelled.emit()
                    return
                if line_numbers and line_idx < len(line_numbers) and line_numbers[line_idx] is None:
                    char_offset += len(line) + 1
                    continue

                if ignore_tags:
                    clean_line, mapping = prepare_text_for_tagless_search_with_mapping(line)
                else:
                    clean_line = line.replace('·', ' ')
                    mapping = list(range(len(line)))

                if is_fuzzy:
                    word_pattern = re.compile(r'\w+')
                    for match in word_pattern.finditer(clean_line):
                        word = match.group(0)
                        if is_fuzzy_match(effective_query, word, threshold=0.75):
                            start_in_clean = match.start()
                            end_in_clean = match.end()

                            raw_start = mapping[start_in_clean]
                            raw_end = mapping[end_in_clean - 1] + 1

                            start_pos = char_offset + raw_start
                            end_pos = char_offset + raw_end
                            matched_text = line[raw_start:raw_end]
                            items_to_review.append((start_pos, end_pos, matched_text, line_idx))
                else:
                    matches = find_smart_matches(clean_line, effective_query, case_sensitive)
                    for start_in_clean, end_in_clean in matches:
                        raw_start = mapping[start_in_clean]
                        raw_end = mapping[end_in_clean - 1] + 1

                        start_pos = char_offset + raw_start
                        end_pos = char_offset + raw_end
                        matched_text = line[raw_start:raw_end]
                        items_to_review.append((start_pos, end_pos, matched_text, line_idx))

                char_offset += len(line) + 1

                if line_idx % 20 == 0 or line_idx == total_lines - 1:
                    if total_lines > 0:
                        self.progress.emit(50 + int((line_idx + 1) / total_lines * 50))

        if not self._is_cancelled:
            self.finished.emit(items_to_review, current_text, line_numbers, block_indices, unique_string_indices)
        else:
            self.cancelled.emit()
