from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QTextCursor
from utils.utils import convert_spaces_to_dots_for_display, convert_dots_to_spaces_from_editor, remove_curly_tags, calculate_string_width, remove_all_tags, calculate_strict_string_width
from core.glossary_manager import GlossaryOccurrence
from .base_ui_updater import BaseUIUpdater

class PreviewUpdater(BaseUIUpdater):
    def __init__(self, main_window, data_processor):
        super().__init__(main_window, data_processor)
        self._preview_cache = {}

    def highlight_glossary_occurrence(self, occurrence: GlossaryOccurrence):
        """Highlights a glossary occurrence in the original_text_edit."""
        if not hasattr(self.mw, 'original_text_edit'):
            return

        editor = self.mw.original_text_edit
        if not hasattr(editor, 'highlightManager'):
            return

        editor.highlightManager.clear_search_match_highlights()
        
        block_number = occurrence.line_idx
        start_char = occurrence.start
        length = occurrence.end - occurrence.start
        
        editor.highlightManager.add_search_match_highlight(block_number, start_char, length)

    def synchronize_original_cursor(self):
        if not hasattr(self.mw, 'edited_text_edit') or not hasattr(self.mw, 'original_text_edit') or \
           not self.mw.edited_text_edit or not self.mw.original_text_edit:
            return
        
        if self.mw.data_store.current_block_idx == -1 or self.mw.data_store.current_string_idx == -1 or \
           not self.mw.edited_text_edit.document().toPlainText(): 
            if hasattr(self.mw.original_text_edit, 'highlightManager'):
                self.mw.original_text_edit.highlightManager.setLinkedCursorPosition(-1, -1) 
            return

        edited_cursor = self.mw.edited_text_edit.textCursor()
        current_line_in_edited = edited_cursor.blockNumber()
        current_col_in_edited = edited_cursor.positionInBlock()

        if hasattr(self.mw.original_text_edit, 'highlightManager'):
            self.mw.original_text_edit.highlightManager.setLinkedCursorPosition(current_line_in_edited, current_col_in_edited)

    def _apply_highlights_for_block(self, block_idx: int):
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit or not hasattr(preview_edit, 'highlightManager') or not self.mw.current_game_rules:
            return

        preview_edit.highlightManager.clearAllProblemHighlights()
        
        if not (0 <= block_idx < len(self.mw.data_store.data)):
            return

        displayed_indices = getattr(self.mw.data_store, 'displayed_string_indices', [])
        if not displayed_indices:
             # If no filtering is active, use all
             displayed_indices = list(range(len(self.mw.data_store.data[block_idx])))

        # OPTIMIZATION: Collect only strings with problems to avoid scanning 5000+ items
        problem_string_indices = set()
        if hasattr(self.mw.data_store, 'problems_per_subline'):
            for key in self.mw.data_store.problems_per_subline:
                if key[0] == block_idx:
                    problem_string_indices.add(key[1])

        for preview_idx, real_idx in enumerate(displayed_indices):
            if real_idx in problem_string_indices:
                if self.mw.list_selection_handler._data_string_has_any_problem(block_idx, real_idx):
                    preview_edit.addProblemLineHighlight(preview_idx)
        
        # Highlight categorized strings if enabled
        if getattr(self.mw.data_store, 'highlight_categorized', False) and not self.mw.data_store.current_category_name:
            categorized_indices = self._get_all_categorized_indices_for_block(block_idx)
            if categorized_indices:
                preview_indices = []
                for p_idx, r_idx in enumerate(displayed_indices):
                    if r_idx in categorized_indices:
                        preview_indices.append(p_idx)
                if preview_indices:
                    highlight_color = QColor(100, 180, 255, 120) # More visible blue
                    preview_edit.highlightManager.setCategorizedLineHighlights(preview_indices, highlight_color)
        else:
            preview_edit.highlightManager.clearCategorizedLineHighlights()

    def _apply_highlights_to_editor(self, editor, block_idx: int, string_idx: int):
        if not editor or not hasattr(editor, 'highlightManager'):
            return
        
        editor.highlightManager.clearAllProblemHighlights()
        
        if block_idx < 0 or string_idx < 0:
            return

        doc = editor.document()
        for i in range(doc.blockCount()):
            problem_key = (block_idx, string_idx, i)
            if problem_key in self.mw.data_store.problems_per_subline:
                problems = self.mw.data_store.problems_per_subline[problem_key]
                if problems:
                    # Determine if critical or warning
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
                        
            # Also check for specific highlights that have their own methods in HighlightManager
            if problem_key in self.mw.data_store.problems_per_subline:
                 problems = self.mw.data_store.problems_per_subline[problem_key]
                 if hasattr(self.mw.current_game_rules, 'problem_ids') and hasattr(self.mw.current_game_rules.problem_ids, 'PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY'):
                     if self.mw.current_game_rules.problem_ids.PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY in problems:
                         editor.highlightManager.addEmptyOddSublineHighlight(i)

            # Move Width Exceed Char calculation here, away from paintEvent
            if editor.objectName() == "edited_text_edit":
                block = doc.findBlockByNumber(i)
                q_block_text_raw_dots = block.text()
                
                string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
                current_threshold_game_px = string_meta.get("width", self.mw.line_width_warning_threshold_pixels)
                
                line_text_with_spaces_and_tags = convert_dots_to_spaces_from_editor(q_block_text_raw_dots)
                line_text_no_tags_for_width_calc = remove_all_tags(line_text_with_spaces_and_tags).rstrip()
                
                if line_text_no_tags_for_width_calc:
                    import re
                    font_map_for_line = self.mw.helper.get_font_map_for_string(block_idx, string_idx)
                    visual_line_width_game_px = calculate_string_width(line_text_no_tags_for_width_calc, font_map_for_line)
                    
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
                                
                        # Use same logic to map back to raw text index
                        if hasattr(editor, 'paint_helpers'):
                            actual_char_index = editor.paint_helpers._map_no_tag_index_to_raw_text_index(
                                q_block_text_raw_dots,
                                line_text_no_tags_for_width_calc,
                                target_char_index_in_no_tag_segment
                            )
                            # Add highlight
                            highlight_color = QColor("#90EE90") 
                            editor.highlightManager.add_width_exceed_char_highlight(block, actual_char_index, highlight_color)


    def _get_all_categorized_indices_for_block(self, block_idx: int) -> set:
        """Get set of all string indices that are assigned to any virtual block (category)."""
        if block_idx < 0: return set()
        pm = getattr(self.mw, 'project_manager', None)
        if not pm or not pm.project: return set()
        
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)
        if proj_b_idx >= len(pm.project.blocks): return set()
        
        block = pm.project.blocks[proj_b_idx]
        categorized_indices = set()
        for cat in block.categories:
            categorized_indices.update(cat.line_indices)
        return categorized_indices

    def populate_strings_for_block(self, block_idx, category_name=None, force=False):
        if not hasattr(self.mw, 'preview_text_edit'):
            return

        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        original_edit = getattr(self.mw, 'original_text_edit', None)
        edited_edit = getattr(self.mw, 'edited_text_edit', None)

        old_preview_scrollbar_value = preview_edit.verticalScrollBar().value() if preview_edit else 0
        
        _saved_programmatic_flag = self.mw.is_programmatically_changing_text
        self.mw.is_programmatically_changing_text = True
        self.mw.data_store.current_category_name = category_name

        # Show "Highlight moved" / "Hide moved" only when this block has categories
        block_has_categories = False
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
            pm = self.mw.project_manager
            block_map = getattr(self.mw, 'block_to_project_file_map', {})
            proj_b_idx = block_map.get(block_idx, block_idx)
            if 0 <= proj_b_idx < len(pm.project.blocks):
                block_has_categories = bool(pm.project.blocks[proj_b_idx].categories)
        show_cat_toggles = block_has_categories and not category_name
        if hasattr(self.mw, 'highlight_categorized_checkbox'):
            self.mw.highlight_categorized_checkbox.setVisible(show_cat_toggles)
        if hasattr(self.mw, 'hide_categorized_checkbox'):
            self.mw.hide_categorized_checkbox.setVisible(show_cat_toggles)

        # Use a local cache of the last populated block to avoid redundant full resets
        last_block_idx = getattr(self, '_last_populated_block_idx', -999)
        last_category_name = getattr(self, '_last_populated_category_name', None)
        block_changed = (block_idx != last_block_idx) or (category_name != last_category_name)

        if block_changed:
            if preview_edit: preview_edit.reset_selection_state()
            if original_edit: original_edit.reset_selection_state()
            if edited_edit: edited_edit.reset_selection_state()
            self._last_populated_block_idx = block_idx
            self._last_populated_category_name = category_name

        if block_idx < 0 or not self.mw.data_store.data or block_idx >= len(self.mw.data_store.data) or not isinstance(self.mw.data_store.data[block_idx], list):
            self._preview_cache.clear()
            self.mw.data_store.displayed_string_indices = []
            if preview_edit:
                preview_edit.override_total_lines = None
                preview_edit.updateLineNumberAreaWidth(0)
                if preview_edit.toPlainText() != "": preview_edit.setPlainText("")
            if original_edit and original_edit.toPlainText() != "": original_edit.setPlainText("")
            if edited_edit and edited_edit.toPlainText() != "": edited_edit.setPlainText("")
            self.update_text_views(); self.synchronize_original_cursor() 
            if preview_edit: preview_edit.verticalScrollBar().setValue(old_preview_scrollbar_value)
            self.mw.is_programmatically_changing_text = False 
            return
        
        if preview_edit and self.mw.current_game_rules:
            # Determine which indices to show
            target_indices = []
            if category_name and hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                pm = self.mw.project_manager
                block_map = getattr(self.mw, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_idx, block_idx)
                if proj_b_idx < len(pm.project.blocks):
                    block = pm.project.blocks[proj_b_idx]
                    category = next((c for c in block.categories if c.name == category_name), None)
                    if category:
                        target_indices = category.line_indices

            if not target_indices and not category_name:
                target_indices = list(range(len(self.mw.data_store.data[block_idx])))
                # Filter out categorized if "Hide moved" is enabled
                if getattr(self.mw.data_store, 'hide_categorized', False):
                    categorized_indices = self._get_all_categorized_indices_for_block(block_idx)
                    target_indices = [idx for idx in target_indices if idx not in categorized_indices]
            
            # Re-verify indices are within bounds
            target_indices = [i for i in target_indices if 0 <= i < len(self.mw.data_store.data[block_idx])]
            
            # Check if displayed indices actually changed (for "Hide moved" toggle)
            old_indices = getattr(self.mw.data_store, 'displayed_string_indices', [])
            if not old_indices and hasattr(self.mw, 'displayed_string_indices'):
                old_indices = self.mw.displayed_string_indices
            displayed_indices_changed = (target_indices != old_indices)
            
            self.mw.data_store.displayed_string_indices = target_indices

            # Initialize lazy load timer if not exists
            if not hasattr(self, '_lazy_load_timer'):
                from PyQt5.QtCore import QObject
                timer_parent = self.mw if isinstance(self.mw, QObject) else None
                self._lazy_load_timer = QTimer(timer_parent)
                self._lazy_load_timer.timeout.connect(self._load_next_preview_chunk)

            if self._lazy_load_timer.isActive():
                self._lazy_load_timer.stop()

            # Map current_string_idx to preview index if possible
            preview_idx_to_select = -1
            if self.mw.data_store.current_string_idx in target_indices:
                preview_idx_to_select = target_indices.index(self.mw.data_store.current_string_idx)

            # Set override_total_lines to prevent dynamic width change
            if len(target_indices) > 0:
                preview_edit.override_total_lines = len(target_indices)
            else:
                preview_edit.override_total_lines = None
            preview_edit.updateLineNumberAreaWidth(0)

            # Generate full text if block changed OR if the subset of strings changed (e.g. Hide moved toggled) OR force refresh
            if block_changed or displayed_indices_changed or force:
                cache_key = (block_idx, category_name)
                if force and cache_key in self._preview_cache:
                    del self._preview_cache[cache_key]

                initial_chunk_size = max(200, preview_idx_to_select + 50)
                
                use_cache = False
                if cache_key in self._preview_cache:
                    cache = self._preview_cache[cache_key]
                    if cache.get('target_indices') == target_indices:
                        use_cache = True
                
                if use_cache:
                    cache = self._preview_cache[cache_key]
                    self._lazy_load_block_idx = block_idx
                    self._lazy_load_target_indices = target_indices
                    self._lazy_load_next_index = cache['next_index']
                    
                    preview_full_text = "\n".join(cache['lines'])
                    preview_edit.setPlainText(preview_full_text)
                    
                    if self._lazy_load_next_index < len(target_indices):
                        self._lazy_load_timer.start(15)
                    else:
                        if self._lazy_load_timer.isActive():
                            self._lazy_load_timer.stop()
                else:
                    if len(target_indices) > initial_chunk_size:
                        self._lazy_load_block_idx = block_idx
                        self._lazy_load_target_indices = target_indices
                        self._lazy_load_next_index = initial_chunk_size
                        
                        preview_lines = [""] * len(target_indices)
                        chunk_indices = target_indices[:initial_chunk_size]
                        for idx_offset, real_idx in enumerate(chunk_indices):
                            text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, real_idx)
                            preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                            preview_lines[idx_offset] = preview_line_text
                        
                        # Save to cache
                        self._preview_cache[cache_key] = {
                            'lines': preview_lines,
                            'next_index': initial_chunk_size,
                            'target_indices': target_indices
                        }
                        
                        preview_full_text = "\n".join(preview_lines)
                        preview_edit.setPlainText(preview_full_text)
                        self._lazy_load_timer.start(15)
                    else:
                        self._lazy_load_next_index = len(target_indices)
                        preview_lines = []
                        for real_idx in target_indices:
                            text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, real_idx)
                            preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                            preview_lines.append(preview_line_text)
                        
                        # Save to cache
                        self._preview_cache[cache_key] = {
                            'lines': preview_lines,
                            'next_index': len(target_indices),
                            'target_indices': target_indices
                        }
                        
                        preview_full_text = "\n".join(preview_lines)
                        if preview_edit.toPlainText() != preview_full_text:
                            preview_edit.setPlainText(preview_full_text)

            # Apply highlights based on NEW displayed_string_indices (MUST be after setPlainText)
            self._apply_highlights_for_block(block_idx)

            if preview_idx_to_select != -1 and \
               hasattr(preview_edit, 'set_selected_lines') and \
               0 <= preview_idx_to_select < preview_edit.document().blockCount(): 
                preview_edit.set_selected_lines([preview_idx_to_select])

            # Only restore scroll value if block changed AND we are NOT intentionally selecting a string
            # (If we are selecting a string, ensureCursorVisible will be called later in string_selected_from_preview)
            if block_changed and self.mw.data_store.current_string_idx == -1:
                preview_edit.verticalScrollBar().setValue(old_preview_scrollbar_value)
        
        self.update_text_views() 
        self.synchronize_original_cursor() 
        self.mw.is_programmatically_changing_text = _saved_programmatic_flag

    def _load_next_preview_chunk(self):
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit or not hasattr(self, '_lazy_load_next_index') or not hasattr(self, '_lazy_load_target_indices'):
            if hasattr(self, '_lazy_load_timer'):
                self._lazy_load_timer.stop()
            return

        block_idx = self._lazy_load_block_idx
        target_indices = self._lazy_load_target_indices
        start_idx = self._lazy_load_next_index
        end_idx = min(start_idx + 500, len(target_indices))
        
        if start_idx >= len(target_indices):
            self._lazy_load_timer.stop()
            return
            
        chunk_indices = target_indices[start_idx:end_idx]
        preview_lines = []
        for real_idx in chunk_indices:
            text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, real_idx)
            preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
            preview_lines.append(preview_line_text)
            
        _saved_programmatic_flag = self.mw.is_programmatically_changing_text
        self.mw.is_programmatically_changing_text = True
        
        try:
            cache_key = (block_idx, getattr(self.mw.data_store, 'current_category_name', None))
            cache = self._preview_cache.get(cache_key)
            
            doc = preview_edit.document()
            cursor = QTextCursor(doc)
            cursor.beginEditBlock()
            for offset, preview_line_text in enumerate(preview_lines):
                line_idx = start_idx + offset
                if cache and line_idx < len(cache['lines']):
                    cache['lines'][line_idx] = preview_line_text
                
                block = doc.findBlockByNumber(line_idx)
                if block.isValid():
                    cursor.setPosition(block.position())
                    cursor.setPosition(block.position() + len(block.text()), QTextCursor.KeepAnchor)
                    cursor.insertText(preview_line_text)
            cursor.endEditBlock()
            
            if cache:
                cache['next_index'] = end_idx
        finally:
            self.mw.is_programmatically_changing_text = _saved_programmatic_flag
            
        self._lazy_load_next_index = end_idx
        
        self._apply_highlights_for_block(block_idx)
        
        preview_idx_to_select = -1
        if self.mw.data_store.current_string_idx in target_indices:
            preview_idx_to_select = target_indices.index(self.mw.data_store.current_string_idx)

        if preview_idx_to_select != -1 and \
           hasattr(preview_edit, 'set_selected_lines') and \
           0 <= preview_idx_to_select < preview_edit.document().blockCount():
            preview_edit.set_selected_lines([preview_idx_to_select])
            
        if end_idx >= len(target_indices):
            self._lazy_load_timer.stop()

    def update_text_views(self): 
        if getattr(self, '_in_update_text_views', False):
            return
        self._in_update_text_views = True
        is_programmatic_call_flag_original = self.mw.is_programmatically_changing_text
        
        self.mw.is_programmatically_changing_text = True
        try:
            self._do_update_text_views(is_programmatic_call_flag_original)
        finally:
            self.mw.is_programmatically_changing_text = is_programmatic_call_flag_original
            self._in_update_text_views = False

    def _do_update_text_views(self, is_programmatic_call_flag_original):

        original_text_raw = ""
        edited_text_raw = ""
        if self.mw.data_store.current_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
            original_text_raw = self.data_processor._get_string_from_source(
                self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx, self.mw.data_store.data, 
                "original_data_for_readonly_view"
            )
            if original_text_raw is None: original_text_raw = ""
            edited_text_raw, _ = self.data_processor.get_current_string_text(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
            if edited_text_raw is None: edited_text_raw = ""
        
        if self.mw.current_game_rules and hasattr(self.mw.current_game_rules, 'get_text_representation_for_editor'):
            original_text_for_display_processed = str(self.mw.current_game_rules.get_text_representation_for_editor(str(original_text_raw)))
            edited_text_for_display_processed = str(self.mw.current_game_rules.get_text_representation_for_editor(str(edited_text_raw)))
        else: 
            original_text_for_display_processed = str(original_text_raw)
            edited_text_for_display_processed = str(edited_text_raw)

        original_text_for_display = convert_spaces_to_dots_for_display(original_text_for_display_processed, self.mw.show_multiple_spaces_as_dots)
        edited_text_for_display_converted = convert_spaces_to_dots_for_display(edited_text_for_display_processed, self.mw.show_multiple_spaces_as_dots)
        
        orig_edit = self.mw.original_text_edit
        if orig_edit:
            if orig_edit.toPlainText() != original_text_for_display:
                orig_text_edit_cursor_pos = int(orig_edit.textCursor().position())
                orig_anchor_pos = int(orig_edit.textCursor().anchor())
                orig_has_selection = bool(orig_edit.textCursor().hasSelection())
                orig_edit.setPlainText(original_text_for_display)
                new_orig_cursor = orig_edit.textCursor()
                new_orig_cursor.setPosition(min(orig_anchor_pos, len(original_text_for_display)))
                if orig_has_selection: new_orig_cursor.setPosition(min(orig_text_edit_cursor_pos, len(original_text_for_display)), QTextCursor.KeepAnchor)
                else: new_orig_cursor.setPosition(min(orig_text_edit_cursor_pos, len(original_text_for_display)))
                orig_edit.setTextCursor(new_orig_cursor)

        edited_widget = self.mw.edited_text_edit
        if edited_widget:
            if edited_widget.toPlainText() != edited_text_for_display_converted:
                saved_edited_cursor_pos = int(edited_widget.textCursor().position())
                saved_edited_anchor_pos = int(edited_widget.textCursor().anchor())
                saved_edited_has_selection = bool(edited_widget.textCursor().hasSelection())
                
                edited_widget.setPlainText(edited_text_for_display_converted)

                restored_cursor = edited_widget.textCursor()
                new_edited_anchor_pos = min(saved_edited_anchor_pos, len(edited_text_for_display_converted))
                new_edited_cursor_pos = min(saved_edited_cursor_pos, len(edited_text_for_display_converted))
                restored_cursor.setPosition(new_edited_anchor_pos)
                if saved_edited_has_selection: restored_cursor.setPosition(new_edited_cursor_pos, QTextCursor.KeepAnchor)
                else: restored_cursor.setPosition(new_edited_cursor_pos)
                edited_widget.setTextCursor(restored_cursor)
            
        # Optional: Calculate original strictly (without fallback char width) width
        if hasattr(self.mw, 'original_width_label'):
            if self.mw.data_store.current_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
                font_map_for_string = self.mw.helper.get_font_map_for_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
                icon_sequences = getattr(self.mw, 'icon_sequences', [])
                
                original_lines = str(original_text_raw).split('\n')
                widths = []
                for line in original_lines:
                    w = calculate_strict_string_width(line, font_map_for_string, icon_sequences=icon_sequences)
                    if w is None:
                        widths = None
                        break
                    widths.append(w)
                
                strict_width = max(widths) if widths is not None and widths else None
                
                if strict_width is not None:
                    self.mw.original_width_label.setText(f"Width: {strict_width}px")
                    self.mw.original_width_label.show()
                else:
                    self.mw.original_width_label.setText("")
                    self.mw.original_width_label.hide()
            else:
                self.mw.original_width_label.setText("")
                self.mw.original_width_label.hide()

        # Apply highlights to editors
        if self.mw.data_store.current_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
             self._apply_highlights_to_editor(self.mw.edited_text_edit, self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
             self._apply_highlights_to_editor(self.mw.original_text_edit, self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)

             # Reapply syntax highlighting if applicable (Removed manual rehighlight calls as they are redundant and slow)
             pass

             # Apply font based on exact logic
             if self.mw.current_game_rules:
                  font_info = self.mw.current_game_rules.get_font_for_block(self.mw.data_store.current_block_idx)
                  if font_info:
                      custom_font_original = self.mw.helper.get_font_for_name(font_info['original_font_name'])
                      if custom_font_original:
                          self.mw.original_text_edit.setDocumentFont(custom_font_original)
                          
                      custom_font_edited = self.mw.helper.get_font_for_name(font_info['font_name'])
                      if custom_font_edited:
                          self.mw.edited_text_edit.setDocumentFont(custom_font_edited)
                          
                      if getattr(self.mw, 'string_settings_handler', None) and font_info.get('font_name'):
                           setattr(self.mw.data_store, 'current_font_name', font_info['font_name'])

             self.mw.ui_updater.update_status_bar()
        else: 
            self.mw.ui_updater.clear_status_bar()

        # Update BFN visual preview
        if hasattr(self.mw, 'bfn_preview_widget') and self.mw.bfn_preview_widget:
            self.mw.bfn_preview_widget.update_preview_text(edited_text_raw)

        # Sync text with active BFN Font Editor simulation if it is open
        if hasattr(self.mw, '_bfn_editor_window') and self.mw._bfn_editor_window is not None:
            try:
                editor = self.mw._bfn_editor_window
                is_mock = False
                try:
                    from unittest.mock import Mock
                    if isinstance(editor, Mock):
                        is_mock = True
                except ImportError:
                    pass
                    
                if not is_mock and not editor.isHidden():
                    sync_enabled = True
                    if hasattr(editor, 'chk_sync_sim_text'):
                        sync_enabled = editor.chk_sync_sim_text.isChecked()
                    if sync_enabled:
                        editor.sim_input.blockSignals(True)
                        editor.sim_input.setPlainText(edited_text_raw)
                        editor.sim_input.blockSignals(False)
                        editor.update_simulation()
            except RuntimeError:
                self.mw._bfn_editor_window = None
            except Exception:
                pass

        if hasattr(self.mw, 'dictionary_tooltip') and self.mw.dictionary_tooltip:
             self.mw.dictionary_tooltip.hide()

    def update_preview_visibility(self):
        """Update visibility of the visual preview widget based on loaded fonts and menu toggle state."""
        preview_widget = getattr(self.mw, 'bfn_preview_widget', None)
        if not preview_widget:
            return

        all_bfn_fonts = getattr(self.mw, 'all_bfn_fonts', {})
        fonts_loaded = bool(all_bfn_fonts)

        toggle_action = getattr(self.mw, 'toggle_preview_action', None)
        
        if not fonts_loaded:
            preview_widget.hide()
            if toggle_action:
                toggle_action.setEnabled(False)
                toggle_action.setChecked(False)
        else:
            if toggle_action:
                toggle_action.setEnabled(True)
                if toggle_action.isChecked():
                    preview_widget.show()
                else:
                    preview_widget.hide()
