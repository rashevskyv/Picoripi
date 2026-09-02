"""Rebuild text, save/refresh project state, spacing/line numbers."""
from __future__ import annotations


class PersistMixin:
    """Rebuild text, save/refresh project state, spacing/line numbers."""

    def rebuild_text_by_options(self):
        main_window = self._find_main_window()
        if not main_window or not hasattr(main_window, 'data_processor'):
            return

        text_parts = []
        for b_idx, s_idx in self.unique_string_indices:
            if self.search_in_original:
                text = main_window.data_processor._get_string_from_source(
                    b_idx, s_idx, main_window.data_store.data, "dialog_original"
                )
            else:
                text, _ = main_window.data_processor.get_current_string_text(b_idx, s_idx)

            if text is None:
                text = ""
            text_parts.append(text)

        raw_text = '\n'.join(text_parts)

        flat_line_numbers = []
        flat_block_indices = []
        for (b_idx, s_idx), text in zip(self.unique_string_indices, text_parts):
            subline_count = text.count('\n') + 1
            for _ in range(subline_count):
                flat_line_numbers.append(s_idx)
                flat_block_indices.append(b_idx)

        self.current_text = raw_text
        self.line_numbers = flat_line_numbers
        self.block_indices = flat_block_indices

        self._process_text_spacing_and_line_numbers()
        self._apply_zebra_striping()

    def _process_text_spacing_and_line_numbers(self):
        if not hasattr(self, 'block_indices') or not self.block_indices:
            super()._process_text_spacing_and_line_numbers()
            return

        line_count = self.current_text.count('\n') + 1

        if self.line_numbers and len(self.line_numbers) >= line_count:
            text_lines = self.current_text.split('\n')
            text_with_spacing = []
            new_line_numbers = []
            new_block_indices = []
            display_line_numbers = []
            subline_numbers = []

            prev_pair = (None, None)
            current_sub_idx = 0
            for i in range(line_count):
                current_line_num = self.line_numbers[i]
                current_block_idx = self.block_indices[i]
                current_pair = (current_block_idx, current_line_num)

                if current_pair != prev_pair:
                    display_line_numbers.append(current_line_num + 1 if current_line_num is not None else None)
                    prev_pair = current_pair
                    current_sub_idx = 1
                else:
                    display_line_numbers.append(None)
                    current_sub_idx += 1

                text_with_spacing.append(text_lines[i] if i < len(text_lines) else '')
                new_line_numbers.append(current_line_num)
                new_block_indices.append(current_block_idx)
                subline_numbers.append(current_sub_idx)

            self.current_text = '\n'.join(text_with_spacing)
            self.line_numbers = new_line_numbers
            self.block_indices = new_block_indices
            self.text_edit.setPlainText(self.current_text)

            self.text_edit.custom_line_numbers = display_line_numbers
            self.text_edit.custom_subline_numbers = subline_numbers
            self.text_edit.custom_message_numbers = new_line_numbers
            self.text_edit.updateLineNumberAreaWidth(0)

    def save_changes_to_project(self):
        main_window = self._find_main_window()
        if not main_window or not hasattr(main_window, 'data_store'):
            return

        corrected_text = self.get_corrected_text()
        if not corrected_text:
            return

        corrected_lines = corrected_text.split('\n')
        if not self.line_numbers or not self.block_indices:
            return

        grouped_lines = {}
        for line_text, s_idx, b_idx in zip(corrected_lines, self.line_numbers, self.block_indices):
            if s_idx is not None and b_idx is not None:
                key = (b_idx, s_idx)
                if key not in grouped_lines:
                    grouped_lines[key] = []
                grouped_lines[key].append(line_text)

        edited_data = main_window.data_store.edited_data
        changes_made = False
        changed_blocks = set()

        undo_manager = getattr(main_window, "undo_manager", None)
        if undo_manager:
            undo_manager.begin_group()

        for (b_idx, string_idx), lines_list in grouped_lines.items():
            new_text = '\n'.join(lines_list)
            res = main_window.data_processor.get_current_string_text(b_idx, string_idx)
            old_text = res[0] if (isinstance(res, tuple) and len(res) == 2) else ""
            if new_text != old_text:
                key = (b_idx, string_idx)
                edited_data[key] = new_text
                changes_made = True
                changed_blocks.add(b_idx)

                if b_idx == main_window.data_store.current_block_idx and string_idx == main_window.data_store.current_string_idx:
                    if hasattr(main_window, 'text_operation_handler'):
                        main_window.text_operation_handler.sync_subline_asterisks(
                            b_idx, string_idx, new_text
                        )

        if undo_manager:
            undo_manager.end_group()

        if changes_made:
            for b_idx in changed_blocks:
                if hasattr(main_window, 'data_store'):
                    main_window.data_store.mark_dirty(b_idx)
            if hasattr(main_window, 'ui_updater'):
                main_window.ui_updater.update_text_views()
                main_window.ui_updater.populate_blocks()

    def rebuild_text_from_project(self):
        main_window = self._find_main_window()
        if not main_window or not hasattr(main_window, 'data_store') or not main_window.data_store.data:
            return

        query = self.query
        case_sensitive = self.case_sensitive
        search_in_original = self.search_in_original
        ignore_tags = self.ignore_tags
        is_fuzzy = self.is_fuzzy

        all_lines = []
        for b_idx in range(len(main_window.data_store.data)):
            block_data = main_window.data_store.data[b_idx]
            if not isinstance(block_data, list):
                continue
            for string_idx in range(len(block_data)):
                if search_in_original:
                    text = main_window.data_processor._get_string_from_source(
                        b_idx, string_idx, main_window.data_store.data, "dialog_original"
                    )
                else:
                    text, _ = main_window.data_processor.get_current_string_text(b_idx, string_idx)
                if text is not None:
                    all_lines.append((b_idx, string_idx, text))

        text_parts = []
        line_numbers = []
        block_indices = []
        unique_string_indices = []

        import re
        from utils.utils import prepare_text_for_tagless_search, is_fuzzy_match

        effective_query = query
        if ignore_tags and query:
            effective_query = prepare_text_for_tagless_search(query)

        if query and effective_query:
            if is_fuzzy:
                word_pattern = re.compile(r'\w+')
                for b_idx, string_idx, text in all_lines:
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
            else:
                compare_query = effective_query if case_sensitive else effective_query.lower()
                for b_idx, string_idx, text in all_lines:
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

        self.unique_string_indices = unique_string_indices
        self.current_text = '\n'.join(text_parts)
        self.line_numbers = line_numbers
        self.block_indices = block_indices

        self._process_text_spacing_and_line_numbers()
        self._apply_zebra_striping()

    def refresh_from_project(self):
        """Re-read current text from data store and update matching display."""
        self.rebuild_text_by_options()
        self.text_edit.setPlainText(self.current_text)
        self._process_text_spacing_and_line_numbers()
        self._apply_zebra_striping()
        self.find_matches()
        self.pre_highlight_all_matches()
        self.show_current_item()
