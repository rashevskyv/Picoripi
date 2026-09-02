from __future__ import annotations
import copy
from typing import Optional, Set
from PyQt6.QtWidgets import QMessageBox, QApplication, QProgressDialog, QDialog
from PyQt6.QtGui import QTextCursor
from PyQt6.QtCore import Qt
from ui.autofix_selection_dialog import AutofixSelectionDialog
from utils.utils import convert_dots_to_spaces_from_editor
from handlers.autofix_worker import AutofixWorker
from core.tag_utils import iter_all_strings
from core.i18n import tr


class AutofixMixin:
    """Auto-fix current string and fix-all worker lifecycle."""

    def auto_fix_current_string(self, from_button: bool = False) -> None:
        """Auto fix current string."""
        modifiers = QApplication.keyboardModifiers()
        # Shift+AutoFix (page-local mode) only applies when using the button directly.
        # When triggered via keyboard shortcut (Ctrl+Shift+A), Shift is part of the
        # shortcut itself and must NOT activate page_local mode.
        is_shift_pressed = from_button and bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if from_button and (modifiers & Qt.KeyboardModifier.ControlModifier):
            if not self.mw.current_game_rules:
                return
            problem_definitions = self.mw.current_game_rules.get_problem_definitions()
            if not problem_definitions:
                return
            autofix_settings = getattr(self.mw, 'autofix_enabled', {})
            dialog = AutofixSelectionDialog(problem_definitions, autofix_settings, self.mw)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_problems = dialog.get_selected_problems()
                self._auto_fix_current_string_impl(allowed_problems=selected_problems, page_local=is_shift_pressed)
        else:
            # Build allowed_problems the same way the dialog does:
            # use current autofix_enabled with True as default for any unset problem IDs.
            # This guarantees identical behaviour between direct AutoFix and Ctrl+AutoFix→Fix All.
            allowed_problems: Optional[Set[str]] = None
            if self.mw.current_game_rules:
                problem_definitions = self.mw.current_game_rules.get_problem_definitions()
                if problem_definitions:
                    autofix_settings = getattr(self.mw, 'autofix_enabled', {})
                    allowed_problems = {
                        pid for pid in problem_definitions
                        if autofix_settings.get(pid, True)
                    }
            from utils.logging_utils import log_debug
            log_debug(
                f"[AutoFix] Simple button: prevent_empty={getattr(self.mw, 'prevent_empty_lines_in_autofix', False)}, "
                f"align={getattr(self.mw, 'align_sentences_to_original_pages', False)}, "
                f"allowed_problems={allowed_problems}"
            )
            self._auto_fix_current_string_impl(allowed_problems=allowed_problems, page_local=is_shift_pressed)

    def _auto_fix_current_string_impl(self, allowed_problems: Optional[Set[str]] = None, page_local: bool = False) -> None:
        """Internal helper to auto fix current string impl."""
        if self.mw.data_store.physical_block_idx == -1 or self.mw.data_store.current_string_idx == -1:
            QMessageBox.information(self.mw, tr('Auto-fix'), tr('No string selected to fix.'))
            return
        if not self.mw.current_game_rules:
            QMessageBox.warning(self.mw, tr('Auto-fix Error'), tr('Game rules plugin not loaded.'))
            return
 
        # Cancel any in-flight async scanner BEFORE AutoFix. If the old scanner
        # finishes after the sync rescan below, it would overwrite the correct
        # problems_per_subline with stale results based on the pre-fix text.
        if self.current_scanner_thread is not None:
            self.current_scanner_thread.cancel()
            self.current_scanner_thread = None
 
        edited_text_edit = self.mw.edited_text_edit
        raw_text = edited_text_edit.toPlainText()
        text_with_spaces = convert_dots_to_spaces_from_editor(raw_text)
        data_to_fix = self.mw.current_game_rules.convert_editor_text_to_data(text_with_spaces)
        
        block_idx = self.mw.data_store.physical_block_idx
        string_idx = self.mw.data_store.current_string_idx
        font_map_for_string = self.mw.helper.get_font_map_for_string(block_idx, string_idx)
        width_threshold_for_string, logical_hard_limit_for_string = self._get_string_thresholds(block_idx, string_idx)
        
        current_iter_text = data_to_fix
        any_changed = False
        max_iterations = 5
        for _ in range(max_iterations):
            fixed_data, changed = self.mw.current_game_rules.autofix_data_string(
                current_iter_text, 
                font_map_for_string, 
                width_threshold_for_string,
                logical_hard_limit=logical_hard_limit_for_string,
                allowed_problems=allowed_problems,
                block_idx=self.mw.data_store.physical_block_idx,
                string_idx=self.mw.data_store.current_string_idx,
                page_local=page_local
            )
            if not changed or fixed_data == current_iter_text:
                break
            current_iter_text = fixed_data
            any_changed = True
        
        fixed_data = current_iter_text
        changed = any_changed
        if changed:
            block_idx = self.mw.data_store.physical_block_idx
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
 
            # 1.1 Sync rescan: compute correct problems for the fixed text immediately
            #     so that UI updates show correct highlights without waiting for async.
            self._rescan_issues_for_current_string(block_idx, string_idx, fixed_data)
 
            # 1.2 Launch a new async scan for glossary/spellcheck highlights on the fixed text.
            #     Do NOT use the debounce timer path — start the scanner directly so it
            #     runs in the background while the rest of the UI updates proceed.
            self._launch_async_scanner_for_fixed_text(
                block_idx, string_idx, fixed_data, font_map_for_string,
                width_threshold_for_string, logical_hard_limit_for_string
            )
 
            # 2. Cancel any pending debounce timer so it doesn't overwrite
            #    the just-saved data with the pre-fix editor text.
            if self.preview_update_timer.isActive():
                self.preview_update_timer.stop()
 
            # 3. Update the editor widget to show the fixed text (programmatically).
            self.mw.is_programmatically_changing_text = True
            cursor = edited_text_edit.textCursor()
            cursor.beginEditBlock()
            cursor.select(QTextCursor.SelectionType.Document)
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
            self.mw.ui_updater.populate_current_view()
            self.mw.ui_updater.update_text_views()
 
            if hasattr(self.mw, 'statusBar'):
                self.mw.statusBar.showMessage("Auto-fix applied.", 2000)
        else:
            # No text changes were made. Still re-confirm warnings by doing a sync rescan.
            # This prevents stale async scans that started before AutoFix (and may finish
            # after this point) from silently clearing any existing problem highlights.
            self._rescan_issues_for_current_string(block_idx, string_idx, fixed_data)
            self.mw.ui_updater.update_text_views()
            if hasattr(self.mw, 'statusBar'):
                self.mw.statusBar.showMessage("Auto-fix: No changes made.", 2000)

    def fix_all_strings(self, target_strings: list = None) -> None:
        """Fix all strings using AutofixWorker in a background thread."""
        modifiers = QApplication.keyboardModifiers()
        is_shift_pressed = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        if isinstance(target_strings, bool):
            target_strings = None

        if not self.mw.current_game_rules:
            QMessageBox.warning(self.mw, tr('Auto-fix Error'), tr('Game rules plugin not loaded.'))
            return

        problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        if not problem_definitions:
            QMessageBox.information(self.mw, tr('Auto-fix'), tr('No problems are defined for this plugin.'))
            return

        # Fetch current autofix enabled settings as default checkbox states
        autofix_settings = getattr(self.mw, 'autofix_enabled', {})
        dialog = AutofixSelectionDialog(problem_definitions, autofix_settings, self.mw)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected_problems = dialog.get_selected_problems()
        if not selected_problems:
            QMessageBox.information(self.mw, tr('Auto-fix'), tr('No problems selected to fix.'))
            return

        # Count total strings
        if target_strings is not None:
            total_strings = len(target_strings)
        else:
            total_strings = sum(1 for _ in iter_all_strings(self.mw.data_store.data))

        if total_strings == 0:
            QMessageBox.information(self.mw, tr('Auto-fix'), tr('No strings to fix.'))
            return

        # Prepare deep copies of required data structures for thread-safety
        data_copy = copy.deepcopy(self.mw.data_store.data)
        edited_data_copy = dict(self.mw.data_store.edited_data)
        edited_file_data_copy = copy.deepcopy(self.mw.data_store.edited_file_data)
        string_metadata_copy = copy.deepcopy(self.mw.string_metadata)
        all_font_maps_copy = copy.deepcopy(self.mw.all_font_maps)
        font_map_copy = dict(self.mw.font_map) if self.mw.font_map else {}

        warning_threshold = getattr(self.mw, 'line_width_warning_threshold_pixels', 280)
        logical_hard_limit = getattr(self.mw, 'game_dialog_max_width_pixels', 300)

        # Show progress dialog
        progress_msg = "Applying auto-fix across selected strings..." if target_strings is not None else "Applying auto-fix across all strings..."
        progress = QProgressDialog(progress_msg, "Cancel", 0, total_strings, self.mw)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        # Create worker
        self._active_autofix_worker = AutofixWorker(
            game_rules=self.mw.current_game_rules,
            target_strings=target_strings,
            data=data_copy,
            edited_data=edited_data_copy,
            edited_file_data=edited_file_data_copy,
            string_metadata=string_metadata_copy,
            all_font_maps=all_font_maps_copy,
            font_map=font_map_copy,
            warning_threshold=warning_threshold,
            logical_hard_limit=logical_hard_limit,
            allowed_problems=selected_problems,
            page_local=is_shift_pressed
        )
        self._active_autofix_progress = progress

        # Connect signals
        self._active_autofix_worker.progress.connect(progress.setValue)
        self._active_autofix_worker.completed.connect(self._on_autofix_finished)
        self._active_autofix_worker.cancelled.connect(self._on_autofix_cancelled)
        self._active_autofix_worker.error.connect(self._on_autofix_error)
        self._active_autofix_worker.finished.connect(self._cleanup_active_autofix)
        progress.canceled.connect(self._cancel_active_autofix)

        # Start worker
        self._active_autofix_worker.start()

    def _cancel_active_autofix(self) -> None:
        """Cancel the active autofix worker."""
        if self._active_autofix_worker:
            self._active_autofix_worker.cancel()

    def _cleanup_active_autofix(self) -> None:
        """Clean up references and delete progress dialog."""
        if self._active_autofix_progress:
            self._active_autofix_progress.deleteLater()
            self._active_autofix_progress = None
        
        worker = self._active_autofix_worker
        self._active_autofix_worker = None
        
        if worker:
            try:
                worker.finished.disconnect(self._cleanup_active_autofix)
            except Exception:
                pass
            if worker.isRunning():
                worker.cancel()
                from utils.logging_utils import log_warning
                if not worker.wait(2000):
                    log_warning("AutofixWorker thread did not stop within timeout, forcing delete.")
            worker.deleteLater()

    def _on_autofix_finished(self, results: list) -> None:
        """Called when AutofixWorker successfully finishes."""
        if not results:
            if hasattr(self.mw, 'statusBar'):
                self.mw.statusBar.showMessage("Auto-fix: No changes made to any string.", 3000)
            return

        # Begin undo group
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.begin_group()

        try:
            for block_idx, string_idx, _, fixed_text in results:
                self.data_processor.update_edited_data(block_idx, string_idx, fixed_text, action_type="AUTOFIX", skip_ui_refresh=True)
                self._rescan_issues_for_current_string(block_idx, string_idx, fixed_text)
        finally:
            if hasattr(self.mw, 'undo_manager'):
                self.mw.undo_manager.end_group("FIX_ALL")

        # UI Refresh
        affected_blocks = set(b_idx for b_idx, _, _, _ in results)
        if hasattr(self.mw, 'ui_updater'):
            for b_idx in affected_blocks:
                self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)

        if self.preview_update_timer.isActive():
            self.preview_update_timer.stop()

        curr_block_idx = self.mw.data_store.physical_block_idx
        curr_string_idx = self.mw.data_store.current_string_idx

        current_string_changed = False
        for b_idx, s_idx, _, _ in results:
            if b_idx == curr_block_idx and s_idx == curr_string_idx:
                current_string_changed = True
                break

        if curr_block_idx != -1 and curr_string_idx != -1 and current_string_changed:
            fixed_current, _ = self.data_processor.get_current_string_text(curr_block_idx, curr_string_idx)
            visual_text_for_editor = self.mw.current_game_rules.get_text_representation_for_editor(fixed_current)
            
            edited_text_edit = self.mw.edited_text_edit
            if edited_text_edit:
                original_cursor_pos = edited_text_edit.textCursor().position()
                self.mw.is_programmatically_changing_text = True
                cursor = edited_text_edit.textCursor()
                cursor.beginEditBlock()
                cursor.select(QTextCursor.SelectionType.Document)
                cursor.insertText(visual_text_for_editor)
                cursor.endEditBlock()
                self.mw.is_programmatically_changing_text = False

                new_doc_len = edited_text_edit.document().characterCount() - 1
                final_cursor_pos = min(original_cursor_pos, new_doc_len if new_doc_len >= 0 else 0)
                restored_cursor = edited_text_edit.textCursor()
                restored_cursor.setPosition(final_cursor_pos)
                edited_text_edit.setTextCursor(restored_cursor)

        if self.mw.data_store.current_block_idx != -1:
            self.mw.ui_updater.populate_current_view()
        self.mw.ui_updater.update_text_views()

        if hasattr(self.mw, 'statusBar'):
            msg = f"Auto-fix applied to {len(results)} string(s)."
            self.mw.statusBar.showMessage(msg, 3000)

    def _on_autofix_cancelled(self) -> None:
        """Called when AutofixWorker is cancelled."""
        if hasattr(self.mw, 'statusBar'):
            self.mw.statusBar.showMessage("Auto-fix canceled. No changes applied.", 3000)

    def _on_autofix_error(self, err_msg: str) -> None:
        """Called when AutofixWorker encounters an error."""
        QMessageBox.critical(self.mw, tr('Auto-fix Error'), f"An error occurred during auto-fix:\n{err_msg}")
