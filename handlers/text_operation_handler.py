import re
from typing import Any, Optional, List, Dict, Tuple, Set, Union
from PyQt5.QtWidgets import QMessageBox, QApplication, QPlainTextEdit
from PyQt5.QtGui import QTextCursor, QTextBlock
from PyQt5.QtCore import QTimer, Qt
from .base_handler import BaseHandler
from utils.logging_utils import log_debug, log_info
from utils.utils import convert_dots_to_spaces_from_editor, convert_spaces_to_dots_for_display, calculate_string_width, remove_all_tags, SPACE_DOT_SYMBOL, ALL_TAGS_PATTERN
from .async_issue_scanner import AsyncIssueScanner, get_scanner_thread_pool

PREVIEW_UPDATE_DELAY = 250

class TextOperationHandler(BaseHandler):
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        super().__init__(main_window, data_processor, ui_updater)
        self.preview_update_timer = QTimer()
        self.preview_update_timer.setSingleShot(True)
        self.preview_update_timer.timeout.connect(self._on_preview_update_timer_timeout)
        self._debounce_block_idx = -1
        self._debounce_string_idx = -1
        # current_scanner is an AsyncIssueScanner (QRunnable) — kept around so
        # we can cooperatively cancel it when a newer scan supersedes it.
        self.current_scanner_thread: Optional[AsyncIssueScanner] = None

    def _rescan_issues_for_current_string(self, block_idx: int, string_idx: int, new_text: str) -> None:
        if not self.mw.current_game_rules:
            return

        keys_to_remove = [k for k in self.mw.data_store.problems_per_subline if k[0] == block_idx and k[1] == string_idx]
        for key in keys_to_remove:
            del self.mw.data_store.problems_per_subline[key]
            
        # Use problem_analyzer if it exists, otherwise use the game rules object itself
        analyzer = getattr(self.mw.current_game_rules, 'problem_analyzer', self.mw.current_game_rules)
        sublines = new_text.split('\n')
        
        font_map_for_string = self.mw.helper.get_font_map_for_string(block_idx, string_idx)
        
        string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
        width_threshold_for_string = string_meta.get("width", getattr(self.mw, 'line_width_warning_threshold_pixels', 200))
        logical_hard_limit_for_string = string_meta.get("width", getattr(self.mw, 'game_dialog_max_width_pixels', 200))
        
        problems_in_string = []
        if hasattr(analyzer, 'analyze_data_string'):
            problems_in_string = analyzer.analyze_data_string(new_text, font_map_for_string, width_threshold_for_string, logical_hard_limit_for_string)
        elif hasattr(analyzer, 'analyze_subline'):
            for i, subline in enumerate(sublines):
                next_subline = sublines[i+1] if i + 1 < len(sublines) else None
                problems = analyzer.analyze_subline(
                    text=subline, next_text=next_subline, subline_number_in_data_string=i, qtextblock_number_in_editor=i,
                    is_last_subline_in_data_string=(i == len(sublines) - 1), editor_font_map=font_map_for_string,
                    editor_line_width_threshold=width_threshold_for_string,
                    full_data_string_text_for_logical_check=new_text,
                    logical_hard_limit=logical_hard_limit_for_string
                )
                problems_in_string.append(problems)

        for i, problem_set in enumerate(problems_in_string):
             if problem_set:
                 self.mw.data_store.problems_per_subline[(block_idx, string_idx, i)] = problem_set


    def _log_undo_state(self, editor, context_message):
        pass

    def _update_preview_content(self) -> None:
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit or self.mw.data_store.current_block_idx == -1:
            return

        block_idx = self.mw.data_store.current_block_idx
        old_scrollbar_value = preview_edit.verticalScrollBar().value()
        
        main_window_ref = self.mw
        was_programmatically_changing = main_window_ref.is_programmatically_changing_text
        main_window_ref.is_programmatically_changing_text = True
        
        if self.mw.current_game_rules:
            # USE displayed_string_indices to respect categories/filters
            target_indices = getattr(self.mw.data_store, 'displayed_string_indices', [])
            if not target_indices:
                if 0 <= block_idx < len(self.mw.data_store.data) and isinstance(self.mw.data_store.data[block_idx], list):
                    target_indices = list(range(len(self.mw.data_store.data[block_idx])))
                else:
                    target_indices = []

            current_string_idx = self.mw.data_store.current_string_idx
            
            # Check if we can perform a partial (single-line) update
            can_do_partial_update = False
            preview_idx = -1
            if current_string_idx != -1 and target_indices and current_string_idx in target_indices:
                preview_idx = target_indices.index(current_string_idx)
                if 0 <= preview_idx < preview_edit.document().blockCount():
                    can_do_partial_update = True

            if can_do_partial_update:
                # Update only the current edited line in the preview
                text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, current_string_idx)
                preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                
                block = preview_edit.document().findBlockByNumber(preview_idx)
                if block.isValid() and block.text() != preview_line_text:
                    cursor = QTextCursor(block)
                    cursor.setPosition(block.position())
                    cursor.setPosition(block.position() + len(block.text()), QTextCursor.KeepAnchor)
                    cursor.insertText(preview_line_text)
                    
                    # Update cache
                    preview_updater = getattr(self.ui_updater, 'preview_updater', None)
                    if preview_updater and hasattr(preview_updater, '_preview_cache'):
                        cache_key = (block_idx, getattr(self.mw.data_store, 'current_category_name', None))
                        if cache_key in preview_updater._preview_cache:
                            cache = preview_updater._preview_cache[cache_key]
                            if 0 <= preview_idx < len(cache['lines']):
                                cache['lines'][preview_idx] = preview_line_text
            else:
                # Fallback to full update (same as before)
                preview_lines = []
                for real_idx in target_indices:
                    if 0 <= real_idx < len(self.mw.data_store.data[block_idx]):
                        text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, real_idx)
                        preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                        preview_lines.append(preview_line_text)

                preview_full_text = "\n".join(preview_lines)
                if preview_edit.toPlainText() != preview_full_text:
                    preview_edit.setPlainText(preview_full_text)
                
                # Update cache
                preview_updater = getattr(self.ui_updater, 'preview_updater', None)
                if preview_updater and hasattr(preview_updater, '_preview_cache'):
                    cache_key = (block_idx, getattr(self.mw.data_store, 'current_category_name', None))
                    preview_updater._preview_cache[cache_key] = {
                        'lines': preview_lines,
                        'next_index': len(target_indices),
                        'target_indices': target_indices
                    }
        
        if hasattr(preview_edit, 'highlightManager'):
            preview_edit.highlightManager.clearAllProblemHighlights()
            self.ui_updater._apply_highlights_for_block(block_idx)

            if self.mw.data_store.current_string_idx != -1 and target_indices and self.mw.data_store.current_string_idx in target_indices:
                preview_idx_to_select = target_indices.index(self.mw.data_store.current_string_idx)
                if 0 <= preview_idx_to_select < preview_edit.document().blockCount():
                    preview_edit.set_selected_lines([preview_idx_to_select])
                else:
                    preview_edit.clear_selection()
            else:
                preview_edit.clear_selection()

        preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
        if hasattr(preview_edit, 'lineNumberArea'):
            preview_edit.lineNumberArea.update()

        main_window_ref.is_programmatically_changing_text = was_programmatically_changing
        
    def stop_and_flush_editor_changes(self) -> None:
        if hasattr(self, 'preview_update_timer') and self.preview_update_timer.isActive():
            log_debug("Flushing pending editor changes synchronously before selection change.")
            self.preview_update_timer.stop()
            self._on_preview_update_timer_timeout()

    def text_edited(self) -> None:
        if self.mw.is_programmatically_changing_text:
            return
            
        if self.mw.data_store.current_block_idx == -1 or self.mw.data_store.current_string_idx == -1:
            return
            
        edited_edit = self.mw.edited_text_edit
        if not edited_edit:
            return

        if hasattr(edited_edit, 'highlighter') and edited_edit.highlighter:
            edited_edit.highlighter.set_typing_mode(True)

        # Queue ALL heavy operations (data updates, title, cursors, issue scanning, preview) using debounce
        self._debounce_block_idx = self.mw.data_store.current_block_idx
        self._debounce_string_idx = self.mw.data_store.current_string_idx
        self.preview_update_timer.start(PREVIEW_UPDATE_DELAY)

    def _on_preview_update_timer_timeout(self) -> None:
        block_idx = self._debounce_block_idx
        string_idx = self._debounce_string_idx
        
        if block_idx == -1 or string_idx == -1:
            block_idx = self.mw.data_store.current_block_idx
            string_idx = self.mw.data_store.current_string_idx
            
        if block_idx == -1 or string_idx == -1:
            return

        # SAFETY CHECK: If the selection has shifted before this timer could run/flush,
        # we MUST NOT read the current editor text and save it to the old indices!
        if block_idx != self.mw.data_store.current_block_idx or string_idx != self.mw.data_store.current_string_idx:
            log_debug(f"Timer update ignored because selection shifted from ({block_idx}, {string_idx}) to ({self.mw.data_store.current_block_idx}, {self.mw.data_store.current_string_idx})")
            return
            
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if not edited_edit or not self.mw.current_game_rules:
            return

        # 1. Get the current text and convert it to data format
        text_from_editor = edited_edit.toPlainText()
        actual_text = self.mw.current_game_rules.convert_editor_text_to_data(text_from_editor)
        actual_text_with_spaces = convert_dots_to_spaces_from_editor(actual_text)

        # 2. Determine which sublines differ from the saved baseline
        text_from_saved_file = self.data_processor._get_string_from_source(block_idx, string_idx, self.mw.data_store.edited_file_data, "edited_file_data")
        if text_from_saved_file is None:
            text_from_saved_file = self.data_processor._get_string_from_source(block_idx, string_idx, self.mw.data_store.data, "original_data")
        if text_from_saved_file is None:
            text_from_saved_file = ""
            
        saved_lines = str(text_from_saved_file).split('\n')
        curr_lines = actual_text_with_spaces.split('\n')
        
        self.mw.data_store.edited_sublines.clear()
        for i, curr_line in enumerate(curr_lines):
            if i >= len(saved_lines) or curr_line != saved_lines[i]:
                self.mw.data_store.edited_sublines.add(i)

        # 3. Save the data
        needs_title_update = self.data_processor.update_edited_data(block_idx, string_idx, actual_text_with_spaces)
        if needs_title_update: 
            self.mw.ui_updater.update_title()
            
        current_text_raw, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        if current_text_raw is not None:
            # Supersede any in-flight scan via cooperative cancellation. The
            # previous runnable will not emit finished_scan after cancel(),
            # so we don't need to disconnect its signal — and we don't have
            # to leak it into an orphaned-threads list.
            if self.current_scanner_thread is not None:
                self.current_scanner_thread.cancel()
                self.current_scanner_thread = None

            font_map_for_string = self.mw.helper.get_font_map_for_string(block_idx, string_idx)
            string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
            width_threshold_for_string = string_meta.get("width", getattr(self.mw, 'line_width_warning_threshold_pixels', 200))
            logical_hard_limit_for_string = string_meta.get("width", getattr(self.mw, 'game_dialog_max_width_pixels', 200))
            analyzer = getattr(self.mw.current_game_rules, 'problem_analyzer', self.mw.current_game_rules)

            # Start background async scanner
            source_text = ""
            if hasattr(self.mw, 'original_text_edit') and self.mw.original_text_edit:
                source_text = self.mw.original_text_edit.toPlainText()

            active_word = ""
            if edited_edit:
                try:
                    cursor = edited_edit.textCursor()
                    pos = cursor.position()
                    if isinstance(pos, int) and pos > 0:
                        text = edited_edit.toPlainText()
                        if isinstance(text, str) and pos - 1 < len(text) and text[pos - 1] not in " \n\t.,!?;:·":
                            cursor.select(QTextCursor.WordUnderCursor)
                            active_word = cursor.selectedText().strip("'·").lower()
                except BaseException:
                    pass

            editor_text = str(current_text_raw)
            if self.mw.current_game_rules and hasattr(self.mw.current_game_rules, 'get_text_representation_for_editor'):
                editor_text = str(self.mw.current_game_rules.get_text_representation_for_editor(editor_text))

            self.current_scanner_thread = AsyncIssueScanner(
                block_idx=block_idx,
                string_idx=string_idx,
                text=str(current_text_raw),
                font_map=dict(font_map_for_string),
                width_threshold=width_threshold_for_string,
                analyzer=analyzer,
                glossary_manager=getattr(getattr(edited_edit, 'highlighter', None), '_glossary_manager', None),
                spellchecker_manager=getattr(self.mw, 'spellchecker_manager', None),
                source_text=source_text,
                active_word=active_word,
                warnings_enabled=getattr(self.mw, 'warnings_enabled', True),
                glossary_enabled=getattr(self.mw, 'glossary_enabled', True),
                editor_text=editor_text,
                logical_hard_limit=logical_hard_limit_for_string
            )
            self.current_scanner_thread.finished_scan.connect(self._on_issue_scan_finished)
            get_scanner_thread_pool().start(self.current_scanner_thread)

        # 5. Synchronize original cursor and update lineNumberArea
        self.mw.ui_updater.synchronize_original_cursor()
        if hasattr(edited_edit, 'recalculate_guidelines'):
            edited_edit.recalculate_guidelines()
        if hasattr(edited_edit, 'lineNumberArea'):
            edited_edit.lineNumberArea.update()

    def _on_issue_scan_finished(self, block_idx: int, string_idx: int, text: str, problems_in_string: list,
                                 glossary_matches: list, translation_matches: list, spellcheck_matches: list) -> None:
        # Check if the block/string selection has changed while scanning
        if block_idx != self.mw.data_store.current_block_idx or string_idx != self.mw.data_store.current_string_idx:
            return

        # Clear existing problems for this string
        keys_to_remove = [k for k in self.mw.data_store.problems_per_subline if k[0] == block_idx and k[1] == string_idx]
        for key in keys_to_remove:
            del self.mw.data_store.problems_per_subline[key]

        # Apply newly found problems
        for i, problem_set in enumerate(problems_in_string):
            if problem_set:
                self.mw.data_store.problems_per_subline[(block_idx, string_idx, i)] = problem_set

        # 1. Update highlighter matches FIRST so they are ready for any text updates
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if edited_edit:
            if hasattr(edited_edit, 'highlighter') and edited_edit.highlighter:
                edited_edit.highlighter._async_glossary_matches = glossary_matches
                edited_edit.highlighter._async_translation_matches = translation_matches
                edited_edit.highlighter._async_spellcheck_matches = spellcheck_matches
                edited_edit.highlighter.set_typing_mode(False, trigger_rehighlight=False)

        # 2. Update UI components smoothly (including text views which might reset the editor text)
        self.ui_updater.update_block_item_text_with_problem_count(block_idx)
        self.ui_updater.update_text_views()
        self.mw.ui_updater.update_status_bar()
        
        # 3. Apply highlights to editor and trigger rehighlight to ensure everything is perfectly updated
        if edited_edit:
            self.mw.ui_updater._apply_highlights_to_editor(edited_edit, block_idx, string_idx)
            if hasattr(edited_edit, 'highlighter') and edited_edit.highlighter:
                edited_edit.highlighter.rehighlight()
            if hasattr(edited_edit, 'lineNumberArea'):
                edited_edit.lineNumberArea.update()

    def sync_subline_asterisks(self, block_idx: int, string_idx: int, current_text: str) -> None:
        """
        Compares the current text of a string with its original version from the file 
        and updates mw.data_store.edited_sublines to show asterisks (*) on modified sublines in the editor.
        """
        if not hasattr(self.mw, 'data_store') or not hasattr(self.mw.data_store, 'edited_sublines'):
            return

        # Determine the baseline (original) text for comparison
        text_from_saved_file = self.data_processor._get_string_from_source(
            block_idx, string_idx, self.mw.data_store.edited_file_data, "edited_file_data"
        )
        if text_from_saved_file is None:
            text_from_saved_file = self.data_processor._get_string_from_source(
                block_idx, string_idx, self.mw.data_store.data, "original_data"
            )
        
        if text_from_saved_file is None:
            self.mw.data_store.edited_sublines.clear()
            return

        saved_lines = str(text_from_saved_file).split('\n')
        curr_lines = str(current_text).split('\n')
        
        self.mw.data_store.edited_sublines.clear()
        for i, curr_line in enumerate(curr_lines):
            # If current line differs OR it's a new line (beyond saved lines), mark as edited
            if i >= len(saved_lines) or curr_line != saved_lines[i]:
                self.mw.data_store.edited_sublines.add(i)

    def paste_block_text(self) -> None:
        log_debug(f"--> TextOperationHandler: paste_block_text triggered.")
        if self.mw.data_store.current_block_idx == -1:
            QMessageBox.warning(self.mw, "Paste Error", "Please select a block.")
            return
        if not self.mw.current_game_rules:
            QMessageBox.warning(self.mw, "Paste Error", "Game rules not loaded.")
            return
            
        block_idx: int = self.mw.data_store.current_block_idx
        
        self.mw.before_paste_edited_data_snapshot = {
            k: v for k,v in self.mw.data_store.edited_data.items() if k[0] == block_idx
        }
        self.mw.before_paste_block_idx_affected = block_idx
        
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'highlightManager'):
            preview_edit.highlightManager.clearAllProblemHighlights() 
        
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if edited_edit and hasattr(edited_edit, 'highlightManager'):
            edited_edit.highlightManager.clearAllProblemHighlights()
        
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.begin_group()
            
        self.ui_updater.update_block_item_text_with_problem_count(block_idx)

            
        start_string_idx = self.mw.data_store.current_string_idx if self.mw.data_store.current_string_idx != -1 else 0
        pasted_text_raw = QApplication.clipboard().text()
        if not pasted_text_raw: QMessageBox.information(self.mw, "Paste", "Clipboard empty."); return
        
        segments_from_clipboard_raw = re.split(r'\{END\}\r?\n', pasted_text_raw)
        parsed_strings = []
        num_raw_segments = len(segments_from_clipboard_raw)
        for i, segment in enumerate(segments_from_clipboard_raw):
            cleaned_segment = segment
            if i > 0 and segment.startswith('\n'): cleaned_segment = segment[1:]
            if cleaned_segment or i < num_raw_segments - 1: parsed_strings.append(cleaned_segment)
        
        if parsed_strings and not parsed_strings[-1] and num_raw_segments > 1 and segments_from_clipboard_raw[-1] == '':
            parsed_strings.pop()
            
        if not parsed_strings: QMessageBox.information(self.mw, "Paste", "No valid segments found."); return
        
        original_block_len = len(self.mw.data_store.data[block_idx])
        successfully_processed_count = 0
        any_change_applied_to_data = False
        
        for i, segment_to_insert_raw in enumerate(parsed_strings):
            current_target_string_idx = start_string_idx + i
            if current_target_string_idx >= original_block_len:
                if i == 0:
                    QMessageBox.warning(self.mw, "Paste Error", f"Cannot paste starting at line {start_string_idx + 1}. Block has {original_block_len} lines.")
                break
            
            original_text_for_tags = self.mw.data_store.data[block_idx][current_target_string_idx]
            
            processed_text, _, _ = self.mw.current_game_rules.process_pasted_segment(
                segment_to_insert_raw, original_text_for_tags, self.mw.EDITOR_PLAYER_TAG
            )
            final_text_to_apply = processed_text.rstrip('\n')
            
            if self.data_processor.update_edited_data(block_idx, current_target_string_idx, final_text_to_apply):
                if hasattr(self.mw, 'title_status_bar_updater'):
                    self.mw.title_status_bar_updater.update_title()
                elif hasattr(self.ui_updater, 'update_title'): 
                    self.ui_updater.update_title()
            
            # Rescan issues for this pasted string so warnings update immediately
            self._rescan_issues_for_current_string(block_idx, current_target_string_idx, final_text_to_apply)
            
            old_text_for_this_line = self.mw.before_paste_edited_data_snapshot.get((block_idx, current_target_string_idx), original_text_for_tags)
            if final_text_to_apply != old_text_for_this_line:
                 any_change_applied_to_data = True
            successfully_processed_count += 1
        
        # Smoothly update problem counts in block list instead of full rebuild
        self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)
        self.mw.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, force=True)
        self.mw.ui_updater.update_text_views()
        

        if any_change_applied_to_data:
            self.mw.can_undo_paste = True
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(True)
        else:
            self.mw.can_undo_paste = False;
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(False)
            
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.end_group("PASTE")
            
        log_debug("<-- TextOperationHandler: paste_block_text finished.")


    def revert_single_line(self, line_index: int) -> None:
        block_idx = self.mw.data_store.current_block_idx
        if block_idx == -1:
             return
             
        original_text = self.data_processor._get_string_from_source(block_idx, line_index, self.mw.data_store.data, "original_for_revert")
        
        if original_text is None:
            QMessageBox.warning(self.mw, "Revert Error", f"Could not find original text for data line {line_index + 1}.")
            return

        current_text, _ = self.data_processor.get_current_string_text(block_idx, line_index)
        
        if current_text == original_text:
             return
        
        if self.data_processor.update_edited_data(block_idx, line_index, original_text, action_type="REVERT"):
            if hasattr(self.mw, 'title_status_bar_updater'):
                self.mw.title_status_bar_updater.update_title()
            elif hasattr(self.ui_updater, 'update_title'): 
                self.ui_updater.update_title()

        # Update problem analysis for this reverted string immediately
        self._rescan_issues_for_current_string(block_idx, line_index, original_text)

        # Update block list tree counts smoothly without rebuilding the tree or resetting focus/selection
        self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)
        
        # Update strings preview list with force=True to ensure it regenerates cached values
        self.mw.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, force=True)
        self.mw.ui_updater.update_text_views()
        

        if hasattr(self.mw, 'statusBar'):
             self.mw.statusBar.showMessage(f"Data line {line_index + 1} reverted to original.", 2000)
        
        if self.mw.data_store.current_string_idx == line_index:
            original_edit = getattr(self.mw, 'original_text_edit', None)
            edited_edit = getattr(self.mw, 'edited_text_edit', None)
            if original_edit and hasattr(original_edit, 'lineNumberArea'): original_edit.lineNumberArea.update()
            if edited_edit and hasattr(edited_edit, 'lineNumberArea'): edited_edit.lineNumberArea.update()


    def calculate_width_for_data_line_action(self, data_line_idx: int) -> None:
        if self.mw.data_store.current_block_idx == -1 or data_line_idx < 0:
            QMessageBox.warning(self.mw, "Calculate Width Error", "No block or data line selected.")
            return

        current_text_data_line, source = self.data_processor.get_current_string_text(self.mw.data_store.current_block_idx, data_line_idx)
        original_text_data_line = self.data_processor._get_string_from_source(self.mw.data_store.current_block_idx, data_line_idx, self.mw.data_store.data, "width_calc_original_data_line")

        if current_text_data_line is None and original_text_data_line is None:
            QMessageBox.warning(self.mw, "Calculate Width Error", f"Could not retrieve text for data line {data_line_idx + 1}.")
            return
        
        if not self.mw.font_map:
             QMessageBox.warning(self.mw, "Calculate Width Error", "Font map is not loaded. Cannot calculate width.")
             return
        if not self.mw.current_game_rules:
            QMessageBox.warning(self.mw, "Calculate Width Error", "Game rules plugin not loaded.")
            return

        string_meta = self.mw.string_metadata.get((self.mw.data_store.current_block_idx, data_line_idx), {})
        warning_threshold = string_meta.get("width", self.mw.line_width_warning_threshold_pixels)
        logical_hard_limit = string_meta.get("width", self.mw.game_dialog_max_width_pixels)
        max_allowed_width = logical_hard_limit

        font_map_for_string = self.mw.helper.get_font_map_for_string(self.mw.data_store.current_block_idx, data_line_idx)
        
        info_parts = [f"Data Line {data_line_idx + 1} (Block {self.mw.data_store.current_block_idx}):\nMax Allowed Width (Game Dialog Limit): {logical_hard_limit}px\nWidth Guideline Threshold: {warning_threshold}px\n"]
        
        problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        
        # Use problem_analyzer if it exists, otherwise use the game rules object itself
        analyzer = getattr(self.mw.current_game_rules, 'problem_analyzer', self.mw.current_game_rules)

        sources_to_check = [
            ("Current", str(current_text_data_line), source),
            ("Original", str(original_text_data_line), "original_data")
        ]

        for title_prefix, text_to_analyze, text_source_info in sources_to_check:
            info_parts.append(f"--- {title_prefix} Text (Source: {text_source_info}) ---")
            
            game_like_text_no_newlines_rstripped = remove_all_tags(text_to_analyze.replace('\n','')).rstrip()
            total_game_width = calculate_string_width(game_like_text_no_newlines_rstripped, font_map_for_string)
            game_status = "OK"
            if total_game_width > logical_hard_limit:
                game_status = f"EXCEEDS GAME DIALOG LIMIT ({total_game_width - logical_hard_limit}px)"
            info_parts.append(f"Total (game-like, no newlines): {total_game_width}px ({game_status})")

            logical_sublines = []
            if hasattr(analyzer, '_get_sublines_from_data_string'):
                logical_sublines = analyzer._get_sublines_from_data_string(text_to_analyze)
            else:
                logical_sublines = text_to_analyze.split('\n')

            for subline_idx, sub_line_text in enumerate(logical_sublines):
                sub_line_no_tags_rstripped = remove_all_tags(sub_line_text).rstrip()
                width_px = calculate_string_width(sub_line_no_tags_rstripped, font_map_for_string)
                
                current_subline_problems = set()
                if hasattr(analyzer, 'analyze_data_string'):
                    problems_per_subline_list = analyzer.analyze_data_string(text_to_analyze, font_map_for_string, warning_threshold, logical_hard_limit)
                    current_subline_problems = problems_per_subline_list[subline_idx] if subline_idx < len(problems_per_subline_list) else set()
                elif hasattr(analyzer, 'analyze_subline'):
                    next_original_subline = logical_sublines[subline_idx + 1] if subline_idx + 1 < len(logical_sublines) else None
                    current_subline_problems = analyzer.analyze_subline(
                        text=sub_line_text,
                        next_text=next_original_subline,
                        subline_number_in_data_string=subline_idx,
                        qtextblock_number_in_editor=subline_idx, 
                        is_last_subline_in_data_string=(subline_idx == len(logical_sublines) - 1),
                        editor_font_map=font_map_for_string,
                        editor_line_width_threshold=warning_threshold,
                        full_data_string_text_for_logical_check=text_to_analyze,
                        logical_hard_limit=logical_hard_limit
                    )
                
                statuses = []
                for prob_id in current_subline_problems:
                    if prob_id in problem_definitions:
                        statuses.append(problem_definitions[prob_id]['name'])
                
                status_str = ", ".join(statuses) if statuses else "OK"
                info_parts.append(f"  Sub-line {subline_idx+1} (rstripped): {width_px}px ({status_str}) '{sub_line_no_tags_rstripped[:30]}...'")
            if title_prefix == "Current": info_parts.append("") 
        
        result_dialog = QMessageBox(self.mw)
        result_dialog.setWindowTitle(f"Width Analysis for Data Line {data_line_idx + 1}")
        result_dialog.setTextFormat(Qt.PlainText)
        result_dialog.setText("\n".join(info_parts))
        result_dialog.setIcon(QMessageBox.Information)
        result_dialog.setStandardButtons(QMessageBox.Ok)
        text_edit_for_size = result_dialog.findChild(QPlainTextEdit)
        if text_edit_for_size:
            text_edit_for_size.setMinimumWidth(700)
            text_edit_for_size.setMinimumHeight(500)
        result_dialog.exec_()
        
    def auto_fix_current_string(self) -> None:
        self._auto_fix_current_string_impl()

    def _auto_fix_current_string_impl(self) -> None:
        if self.mw.data_store.current_block_idx == -1 or self.mw.data_store.current_string_idx == -1:
            QMessageBox.information(self.mw, "Auto-fix", "No string selected to fix.")
            return
        if not self.mw.current_game_rules:
            QMessageBox.warning(self.mw, "Auto-fix Error", "Game rules plugin not loaded.")
            return

        edited_text_edit = self.mw.edited_text_edit
        raw_text = edited_text_edit.toPlainText()
        text_with_spaces = convert_dots_to_spaces_from_editor(raw_text)
        data_to_fix = self.mw.current_game_rules.convert_editor_text_to_data(text_with_spaces)
        
        font_map_for_string = self.mw.helper.get_font_map_for_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
        
        string_meta = self.mw.string_metadata.get((self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx), {})
        width_threshold_for_string = string_meta.get("width", self.mw.line_width_warning_threshold_pixels)
        
        fixed_data, changed = self.mw.current_game_rules.autofix_data_string(
            data_to_fix, 
            font_map_for_string, 
            width_threshold_for_string
        )
        
        if changed:
            block_idx = self.mw.data_store.current_block_idx
            string_idx = self.mw.data_store.current_string_idx
            visual_text_for_editor = self.mw.current_game_rules.get_text_representation_for_editor(fixed_data)
            
            # Save cursor position
            original_cursor_pos = edited_text_edit.textCursor().position()
            
            # 1. Save fixed data to edited_data FIRST (synchronously), before any UI update.
            #    This is critical: update_text_views() reads from edited_data, so it must be
            #    updated before calling it, otherwise it restores the old text.
            if hasattr(self.mw, 'undo_manager'):
                self.mw.undo_manager.begin_group()
            self.data_processor.update_edited_data(block_idx, string_idx, fixed_data, action_type="AUTOFIX")
            if hasattr(self.mw, 'undo_manager'):
                self.mw.undo_manager.end_group("AUTOFIX")

            # 1.1 Rescan issues for the fixed text so that UI updates with correct highlights immediately
            self._rescan_issues_for_current_string(block_idx, string_idx, fixed_data)

            # 2. Cancel any pending debounce timer so it doesn't overwrite
            #    the just-saved data with the pre-fix editor text.
            if self.preview_update_timer.isActive():
                self.preview_update_timer.stop()

            # 3. Update the editor widget to show the fixed text (programmatically).
            self.mw.is_programmatically_changing_text = True
            cursor = edited_text_edit.textCursor()
            cursor.beginEditBlock()
            cursor.select(QTextCursor.Document)
            cursor.insertText(visual_text_for_editor)
            cursor.endEditBlock()
            self.mw.is_programmatically_changing_text = False

            # Restore cursor position
            new_doc_len = edited_text_edit.document().characterCount() - 1
            final_cursor_pos = min(original_cursor_pos, new_doc_len if new_doc_len >= 0 else 0)
            restored_cursor = edited_text_edit.textCursor()
            restored_cursor.setPosition(final_cursor_pos)
            edited_text_edit.setTextCursor(restored_cursor)

            # 4. Refresh UI: preview list and text views.
            self.mw.ui_updater.populate_strings_for_block(block_idx)
            self.mw.ui_updater.update_text_views()

            if hasattr(self.mw, 'statusBar'):
                self.mw.statusBar.showMessage("Auto-fix applied.", 2000)
        else:
            if hasattr(self.mw, 'statusBar'):
                self.mw.statusBar.showMessage("Auto-fix: No changes made.", 2000)