from typing import Any
import re
from PyQt6.QtGui import QColor, QTextCursor
from utils.utils import (
    convert_dots_to_spaces_from_editor, calculate_string_width,
    remove_all_tags
)

class PreviewRenderer:
    """Handles rendering of preview texts, chunked loading and highlights applying."""
    def __init__(self, main_window: Any, data_processor: Any, preview_cache: Any):
        """Initialize the preview renderer."""
        self.mw = main_window
        self.data_processor = data_processor
        self.preview_cache = preview_cache
        self._placeholder_texts = {}
        self._lazy_load_block_idx = -999
        self._lazy_load_target_indices = []
        self._lazy_load_next_index = 0

    def _apply_highlights_for_block(self, block_idx: int):
        """Apply block-level highlights to the preview_text_edit."""
        if block_idx not in (-1,):
            view_token = getattr(self.mw.data_store, "view_block_token", block_idx)
            if view_token in (-2, -3, -4, -5):
                block_idx = view_token

        data_source = getattr(self.mw.data_store, 'data', None)
        if not isinstance(data_source, list):
            if hasattr(self.mw, 'data') and isinstance(self.mw.data, list):
                data_source = self.mw.data
            else:
                data_source = []

        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit or not hasattr(preview_edit, 'highlightManager') or not self.mw.current_game_rules:
            return

        preview_edit.highlightManager.clearAllProblemHighlights()

        is_chapter = (block_idx == -2)
        is_speaker = (block_idx in (-3, -4, -5))
        is_virtual = is_chapter or is_speaker
        if not is_virtual and not (0 <= block_idx < len(data_source)):
            return

        displayed_indices = getattr(self.mw.data_store, 'displayed_string_indices', [])
        if not displayed_indices:
             if is_virtual:
                 displayed_indices = list(getattr(self.mw.data_store, 'chapter_mappings', []))
             else:
                 displayed_indices = list(range(len(data_source[block_idx])))

        problem_string_indices = set()
        detection_config = getattr(self.mw, 'detection_enabled', {})
        if hasattr(self.mw.data_store, 'problems_per_subline'):
            problems_dict = self.mw.data_store.problems_per_subline
            if isinstance(problems_dict, dict):
                for key, problems in problems_dict.items():
                    if is_virtual:
                        if any(detection_config.get(p_id, True) for p_id in problems):
                            problem_string_indices.add((key[0], key[1]))
                    else:
                        if key[0] == block_idx:
                            if any(detection_config.get(p_id, True) for p_id in problems):
                                problem_string_indices.add(key[1])

        for preview_idx, real_idx in enumerate(displayed_indices):
            if is_virtual:
                if real_idx in problem_string_indices:
                    preview_edit.addProblemLineHighlight(preview_idx)
            else:
                if real_idx in problem_string_indices:
                    preview_edit.addProblemLineHighlight(preview_idx)

        # Highlight categorized strings if enabled
        if not is_chapter and getattr(self.mw.data_store, 'highlight_categorized', False) and not self.mw.data_store.current_category_name:
            categorized_indices = self._get_all_categorized_indices_for_block(block_idx)
            if categorized_indices:
                preview_indices = []
                for p_idx, r_idx in enumerate(displayed_indices):
                    if r_idx in categorized_indices:
                        preview_indices.append(p_idx)
                if preview_indices:
                    highlight_color = QColor(100, 180, 255, 120)
                    preview_edit.highlightManager.setCategorizedLineHighlights(preview_indices, highlight_color)
        else:
            preview_edit.highlightManager.clearCategorizedLineHighlights()

    def _apply_highlights_to_editor(self, editor, block_idx: int, string_idx: int):
        """Apply line highlights to original/edited text editors."""
        if not editor or not hasattr(editor, 'highlightManager'):
            return

        editor.highlightManager.clearAllProblemHighlights()

        if not getattr(self.mw, 'warnings_enabled', True):
            return
        if not isinstance(block_idx, int) or not isinstance(string_idx, int) or block_idx < 0 or string_idx < 0:
            return

        doc = editor.document()
        for i in range(doc.blockCount()):
            problem_key = (block_idx, string_idx, i)
            if problem_key in self.mw.data_store.problems_per_subline:
                problems = self.mw.data_store.problems_per_subline[problem_key]
                if problems:
                    is_critical = False; warning_color = None
                    for p_id in problems:
                        def_ = self.mw.current_game_rules.get_problem_definitions().get(p_id, {})
                        if def_.get("severity") == "error":
                            is_critical = True
                            break
                        elif "color" in def_:
                             warning_color = def_["color"]

                    if is_critical:
                        editor.highlightManager.addCriticalProblemHighlight(i)
                    else:
                        editor.highlightManager.addWarningLineHighlight(i, warning_color)

            if problem_key in self.mw.data_store.problems_per_subline:
                 problems = self.mw.data_store.problems_per_subline[problem_key]
                 if hasattr(self.mw.current_game_rules, 'problem_ids') and hasattr(self.mw.current_game_rules.problem_ids, 'PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY'):
                     if self.mw.current_game_rules.problem_ids.PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY in problems:
                         editor.highlightManager.addEmptyOddSublineHighlight(i)

            if editor.objectName() == "edited_text_edit":
                block = doc.findBlockByNumber(i)
                q_block_text_raw_dots = block.text()

                from utils.utils import resolve_width_limits
                string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
                _, current_threshold_game_px = resolve_width_limits(
                    string_meta, getattr(self.mw, 'current_game_rules', None),
                    block_idx, string_idx,
                    self.mw.line_width_warning_threshold_pixels,
                    self.mw.game_dialog_max_width_pixels)

                line_text_with_spaces_and_tags = convert_dots_to_spaces_from_editor(q_block_text_raw_dots)
                line_text_no_tags_for_width_calc = remove_all_tags(line_text_with_spaces_and_tags).rstrip()

                if line_text_with_spaces_and_tags.rstrip():
                    font_map_for_line = self.mw.helper.get_font_map_for_string(block_idx, string_idx)
                    visual_line_width_game_px = calculate_string_width(line_text_with_spaces_and_tags.rstrip(), font_map_for_line, default_tag_mappings=getattr(self.mw, 'default_tag_mappings', None))

                    if visual_line_width_game_px > current_threshold_game_px:
                        words_in_no_tag_segment = [{'text': match.group(0), 'start_idx_in_segment': match.start()} for match in re.finditer(r'\S+', line_text_no_tags_for_width_calc)]

                        target_char_index_in_no_tag_segment = 0
                        if words_in_no_tag_segment:
                            found_target_word = False
                            for word_info in reversed(words_in_no_tag_segment):
                                text_before_word_no_tags = line_text_no_tags_for_width_calc[:word_info['start_idx_in_segment']]
                                width_before_word_game_px = calculate_string_width(text_before_word_no_tags, font_map_for_line)
                                if width_before_word_game_px <= current_threshold_game_px:
                                    target_char_index_in_no_tag_segment = word_info['start_idx_in_segment']
                                    found_target_word = True
                                    break
                            if not found_target_word:
                                target_char_index_in_no_tag_segment = 0

                        if hasattr(editor, 'paint_helpers'):
                            actual_char_index = editor.paint_helpers._map_no_tag_index_to_raw_text_index(
                                q_block_text_raw_dots,
                                line_text_no_tags_for_width_calc,
                                target_char_index_in_no_tag_segment
                            )
                            highlight_color = QColor("#90EE90")
                            editor.highlightManager.add_width_exceed_char_highlight(block, actual_char_index, highlight_color)

    def _get_all_categorized_indices_for_block(self, block_idx: int) -> set:
        """Get set of all string indices that are assigned to any virtual block (category)."""
        if block_idx < 0: return set()
        pm = getattr(self.mw, 'project_manager', None)
        if not pm or not pm.project: return set()

        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)
        if not isinstance(proj_b_idx, int) or proj_b_idx >= len(pm.project.blocks): return set()

        block = pm.project.blocks[proj_b_idx]
        categorized_indices = set()
        for cat in block.categories:
            categorized_indices.update(cat.line_indices)
        return categorized_indices

    def _load_next_preview_chunk(self):
        """Internal helper to load next preview chunk."""
        from utils.logging_utils import log_error
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        mw_pu = getattr(self, 'preview_updater', None)
        if mw_pu is None:
            mw_pu = getattr(self.mw.ui_updater, 'preview_updater', None) if hasattr(self.mw, 'ui_updater') else None

        if not preview_edit or not hasattr(self, '_lazy_load_next_index') or not hasattr(self, '_lazy_load_target_indices'):
            if mw_pu and hasattr(mw_pu, '_lazy_load_timer') and mw_pu._lazy_load_timer:
                mw_pu._lazy_load_timer.stop()
            return

        try:
            block_idx = self._lazy_load_block_idx
            target_indices = self._lazy_load_target_indices
            start_idx = self._lazy_load_next_index
            end_idx = min(start_idx + 500, len(target_indices))

            if start_idx >= len(target_indices):
                if mw_pu and hasattr(mw_pu, '_lazy_load_timer') and mw_pu._lazy_load_timer:
                    mw_pu._lazy_load_timer.stop()
                return

            chunk_indices = target_indices[start_idx:end_idx]
            preview_lines = []
            cache_key = self.preview_cache.get_cache_key(block_idx, getattr(self.mw.data_store, 'current_category_name', None))
            cache = self.preview_cache.cache.get(cache_key)
            if cache:
                self.preview_cache.cache.move_to_end(cache_key)

            for offset, real_idx in enumerate(chunk_indices):
                line_idx = start_idx + offset
                preview_line_text = None
                if cache and line_idx < len(cache['lines']) and line_idx < cache['next_index']:
                    preview_line_text = cache['lines'][line_idx]

                if preview_line_text is None:
                    if real_idx == -1:
                        preview_line_text = self._placeholder_texts.get(line_idx, "[Empty Lines]")
                    else:
                        b_idx = block_idx
                        s_idx = real_idx
                        if isinstance(real_idx, tuple):
                            b_idx, s_idx = real_idx
                        text_for_preview_raw, _ = self.data_processor.get_current_string_text(b_idx, s_idx)
                        if self.mw.current_game_rules:
                            preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                        else:
                            preview_line_text = str(text_for_preview_raw)
                preview_lines.append(preview_line_text)

            _saved_programmatic_flag = self.mw.is_programmatically_changing_text
            self.mw.is_programmatically_changing_text = True

            try:
                doc = preview_edit.document()
                import sys
                cursor_cls = QTextCursor
                if 'ui.updaters.preview_updater' in sys.modules:
                    mod = sys.modules['ui.updaters.preview_updater']
                    if hasattr(mod, 'QTextCursor'):
                        cursor_cls = getattr(mod, 'QTextCursor')

                try:
                    cursor = cursor_cls(doc)
                except (TypeError, Exception):
                    cursor = doc
                if hasattr(cursor, 'beginEditBlock') and callable(cursor.beginEditBlock):
                    cursor.beginEditBlock()
                for offset, preview_line_text in enumerate(preview_lines):
                    line_idx = start_idx + offset
                    if cache and line_idx < len(cache['lines']):
                        cache['lines'][line_idx] = preview_line_text

                    block = doc.findBlockByNumber(line_idx)
                    if block.isValid():
                        if hasattr(cursor, 'setPosition'):
                            cursor.setPosition(block.position())
                            cursor.setPosition(block.position() + len(block.text()), QTextCursor.MoveMode.KeepAnchor)
                            cursor.insertText(preview_line_text)
                if hasattr(cursor, 'endEditBlock') and callable(cursor.endEditBlock):
                    cursor.endEditBlock()

                if cache:
                    cache['next_index'] = end_idx
            finally:
                self.mw.is_programmatically_changing_text = _saved_programmatic_flag

            self._lazy_load_next_index = end_idx

            self._apply_highlights_for_block(block_idx)

            preview_idx_to_select = -1
            is_chapter = (block_idx == -2)
            is_speaker = (block_idx in (-3, -4, -5))
            is_virtual = is_chapter or is_speaker
            if is_virtual:
                target_tuple = (self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx)
                if target_tuple in target_indices:
                    preview_idx_to_select = target_indices.index(target_tuple)
            else:
                if self.mw.data_store.current_string_idx in target_indices:
                    preview_idx_to_select = target_indices.index(self.mw.data_store.current_string_idx)

            if preview_idx_to_select != -1 and \
               hasattr(preview_edit, 'set_selected_lines') and \
               0 <= preview_idx_to_select < preview_edit.document().blockCount():
                preview_edit.set_selected_lines([preview_idx_to_select])

            if end_idx >= len(target_indices):
                if mw_pu and hasattr(mw_pu, '_lazy_load_timer') and mw_pu._lazy_load_timer:
                    mw_pu._lazy_load_timer.stop()

        except Exception as ex:
            log_error(f"Error in _load_next_preview_chunk: {ex}", exc_info=True)
            if mw_pu and hasattr(mw_pu, '_lazy_load_timer') and mw_pu._lazy_load_timer:
                mw_pu._lazy_load_timer.stop()
