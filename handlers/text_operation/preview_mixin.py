from __future__ import annotations
from PyQt6.QtGui import QTextCursor
from utils.logging_utils import log_debug
from utils.utils import convert_dots_to_spaces_from_editor
from handlers.async_issue_scanner import AsyncIssueScanner, get_scanner_thread_pool

# Idle gap after the last keystroke before analysis/preview/render.
# The editor itself stays live; spellcheck, glossary, tags, warnings,
# BFN and the strings-list preview wait until typing has stopped.
PREVIEW_UPDATE_DELAY = 1500


class PreviewMixin:
    """Preview updates, editor debounce flush, and text_edited."""

    def _update_preview_content(self) -> None:
        """Internal helper to update the preview content."""
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
            target_key = current_string_idx
            if block_idx < 0:
                target_key = (self.mw.data_store.physical_block_idx, current_string_idx)
                
            try:
                if current_string_idx != -1 and target_indices and target_key in target_indices:
                    preview_idx = target_indices.index(target_key)
                    if isinstance(preview_idx, int) and 0 <= preview_idx < int(preview_edit.document().blockCount()):
                        can_do_partial_update = True
            except (TypeError, ValueError):
                can_do_partial_update = False

            if can_do_partial_update:
                # Update only the current edited line in the preview
                p_block_idx = self.mw.data_store.physical_block_idx
                text_for_preview_raw, _ = self.data_processor.get_current_string_text(p_block_idx, current_string_idx)
                preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                
                block = preview_edit.document().findBlockByNumber(preview_idx)
                try:
                    block_valid = block.isValid() and block.text() != preview_line_text
                except (TypeError, RuntimeError):
                    block_valid = False
                if block_valid:
                    try:
                        cursor = QTextCursor(block)
                    except TypeError:
                        cursor = None
                    if cursor is not None:
                        cursor.setPosition(block.position())
                        cursor.setPosition(block.position() + len(block.text()), QTextCursor.MoveMode.KeepAnchor)
                        cursor.insertText(preview_line_text)
                    
                    # Update cache
                    preview_updater = getattr(self.ui_updater, 'preview_updater', None)
                    if preview_updater and hasattr(preview_updater, '_preview_cache'):
                        preview_updater.update_cached_string(p_block_idx, current_string_idx, preview_line_text)
            else:
                # Fallback to full update
                preview_lines = []
                preview_updater = getattr(self.ui_updater, 'preview_updater', None)
                for line_idx, real_idx in enumerate(target_indices):
                    if real_idx == -1:
                        preview_line_text = getattr(preview_updater, '_placeholder_texts', {}).get(line_idx, "[Empty Lines]") if preview_updater else "[Empty Lines]"
                    else:
                        b_idx = block_idx
                        s_idx = real_idx
                        if isinstance(real_idx, tuple) and len(real_idx) == 2:
                            b_idx, s_idx = real_idx
                        
                        if 0 <= b_idx < len(self.mw.data_store.data) and 0 <= s_idx < len(self.mw.data_store.data[b_idx]):
                            text_for_preview_raw, _ = self.data_processor.get_current_string_text(b_idx, s_idx)
                            preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                        else:
                            preview_line_text = ""
                    preview_lines.append(preview_line_text)

                preview_full_text = "\n".join(preview_lines)

                if preview_edit.toPlainText() != preview_full_text:
                    preview_edit.setPlainText(preview_full_text)
                
                # Update cache
                preview_updater = getattr(self.ui_updater, 'preview_updater', None)
                if preview_updater and hasattr(preview_updater, '_preview_cache'):
                    cache_key = preview_updater.get_cache_key(block_idx, getattr(self.mw.data_store, 'current_category_name', None))
                    preview_updater._preview_cache[cache_key] = {
                        'lines': preview_lines,
                        'next_index': len(target_indices),
                        'target_indices': target_indices
                    }
        
        if hasattr(preview_edit, 'highlightManager'):
            preview_edit.highlightManager.clearAllProblemHighlights()
            self.ui_updater.preview_updater._apply_highlights_for_block(block_idx)

            target_to_select = current_string_idx if block_idx >= 0 else (self.mw.data_store.physical_block_idx, current_string_idx)
            try:
                if current_string_idx != -1 and target_indices and target_to_select in target_indices:
                    preview_idx_to_select = target_indices.index(target_to_select)
                    block_count = preview_edit.document().blockCount()
                    if isinstance(preview_idx_to_select, int) and isinstance(block_count, int) and 0 <= preview_idx_to_select < block_count:
                        preview_edit.set_selected_lines([preview_idx_to_select])
                    else:
                        preview_edit.clear_selection()
                else:
                    preview_edit.clear_selection()
            except TypeError:
                pass

        preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
        if hasattr(preview_edit, 'lineNumberArea'):
            preview_edit.lineNumberArea.update()

        main_window_ref.is_programmatically_changing_text = was_programmatically_changing

    def stop_and_flush_editor_changes(self) -> None:
        """Persist pending typing without running idle analysis on the old row."""
        if hasattr(self, 'preview_update_timer') and self.preview_update_timer.isActive():
            log_debug("Flushing pending editor changes synchronously before selection change.")
            self.preview_update_timer.stop()
            self._persist_editor_buffer()

    def _editor_shows_current_row(self) -> bool:
        """Whether the editor is actually displaying the current (block, string).

        The editor is filled by the view updater, which records the row it just
        rendered. Until that happens the editor still holds the previous row's
        text -- or nothing at all, right after a project loads. Attributing its
        contents to the current row then would save the wrong text, and an empty
        editor would wipe a real translation.
        """
        bound = getattr(self.mw.data_store, 'editor_bound_row', None)
        if bound is None:
            return False
        return bound == (
            self.mw.data_store.physical_block_idx,
            self.mw.data_store.current_string_idx,
        )

    def text_edited(self) -> None:
        """Text edited."""
        if self.mw.is_programmatically_changing_text:
            return
        # While data is loading the editor is emptied and refilled by the app, not
        # by the user. Treating that as an edit would schedule a save of the empty
        # editor over the string's real translation.
        if self.mw.is_loading_data:
            return
        if self.mw.data_store.physical_block_idx == -1 or self.mw.data_store.current_string_idx == -1:
            return
        if not self._editor_shows_current_row():
            return

        edited_edit = self.mw.edited_text_edit
        if not edited_edit:
            return

        highlighter = getattr(edited_edit, 'highlighter', None)
        if highlighter is not None:
            highlighter.set_typing_mode(True)
            # Drop stale async ranges so a previous scan cannot paint the
            # new text while the user is still typing.
            highlighter._async_glossary_matches = None
            highlighter._async_translation_matches = None
            highlighter._async_spellcheck_matches = None

        if self.current_scanner_thread is not None:
            self.current_scanner_thread.cancel()
            self.current_scanner_thread = None

        self._debounce_block_idx = self.mw.data_store.physical_block_idx
        self._debounce_string_idx = self.mw.data_store.current_string_idx
        self.preview_update_timer.start(PREVIEW_UPDATE_DELAY)

    def _on_preview_update_timer_timeout(self) -> None:
        """Internal helper to handle the preview update timer timeout event."""
        persisted = self._persist_editor_buffer()
        if persisted is None:
            return
        self._run_post_edit_analysis(*persisted)

    def _persist_editor_buffer(self):
        """Save the editor text for the bound row. No BFN, preview, or scanner."""
        block_idx = self._debounce_block_idx
        string_idx = self._debounce_string_idx

        if block_idx == -1 or string_idx == -1:
            block_idx = self.mw.data_store.physical_block_idx
            string_idx = self.mw.data_store.current_string_idx

        if block_idx == -1 or string_idx == -1:
            return None

        # Last line of defence: never persist editor content while loading. A
        # queued timeout can still fire after loading starts, and the editor may
        # be mid-refill, which would write an empty string over a real one.
        if self.mw.is_loading_data or self.mw.is_programmatically_changing_text:
            log_debug("Editor flush skipped: data is loading or text is being set programmatically.")
            return None

        if not self._editor_shows_current_row():
            log_debug(
                "Editor flush skipped: the editor is not displaying the current row yet "
                f"(bound={getattr(self.mw.data_store, 'editor_bound_row', None)}, "
                f"current={(block_idx, string_idx)})."
            )
            return None

        # SAFETY CHECK: If the selection has shifted before this timer could run/flush,
        # we MUST NOT read the current editor text and save it to the old indices!
        if block_idx != self.mw.data_store.physical_block_idx or string_idx != self.mw.data_store.current_string_idx:
            log_debug(f"Timer update ignored because selection shifted from ({block_idx}, {string_idx}) to ({self.mw.data_store.physical_block_idx}, {self.mw.data_store.current_string_idx})")
            return None

        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if not edited_edit or not self.mw.current_game_rules:
            return None

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
        return (block_idx, string_idx, current_text_raw)

    def _run_post_edit_analysis(self, block_idx, string_idx, current_text_raw) -> None:
        """Spellcheck/glossary scan, preview line, BFN, guidelines after typing pauses."""
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if not edited_edit:
            return

        if current_text_raw is not None:
            # Supersede any in-flight scan via cooperative cancellation. The
            # previous runnable will not emit finished_scan after cancel(),
            # so we don't need to disconnect its signal — and we don't have
            # to leak it into an orphaned-threads list.
            if self.current_scanner_thread is not None:
                self.current_scanner_thread.cancel()
                self.current_scanner_thread = None

            font_map_for_string = self.mw.helper.get_font_map_for_string(block_idx, string_idx)
            width_threshold_for_string, logical_hard_limit_for_string = self._get_string_thresholds(block_idx, string_idx)
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
                            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
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
            if getattr(self.mw, '_is_sync_scan', False) is True:
                self.current_scanner_thread.run()
            else:
                get_scanner_thread_pool().start(self.current_scanner_thread)

        # Typing has stopped: restore tag/glossary/spellcheck painting, then
        # refresh preview/BFN/guidelines. Do not call update_text_views — that
        # resets the editor. Scanner highlights arrive when the worker finishes.
        highlighter = getattr(edited_edit, 'highlighter', None)
        if highlighter is not None:
            highlighter.set_typing_mode(False, trigger_rehighlight=True)

        self._update_preview_content()
        bfn = getattr(self.mw, 'bfn_preview_widget', None)
        if (
            current_text_raw is not None
            and bfn is not None
            and getattr(self.mw, 'preview_enabled', True)
        ):
            original_raw = self.data_processor._get_string_from_source(
                block_idx, string_idx, self.mw.data_store.data, "original_data"
            )
            update_bfn = getattr(bfn, 'update_preview_text', None)
            if callable(update_bfn):
                update_bfn(str(current_text_raw), original=original_raw or "")
        self.mw.ui_updater.synchronize_original_cursor()
        if hasattr(edited_edit, 'recalculate_guidelines'):
            edited_edit.recalculate_guidelines()
        if hasattr(edited_edit, 'lineNumberArea'):
            edited_edit.lineNumberArea.update()
