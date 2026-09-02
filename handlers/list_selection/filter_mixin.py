"""Preview/tree filter toggles and category helpers."""
from __future__ import annotations


class FilterMixin:
    """Preview/tree filter toggles and category helpers."""

    def move_selection_to_category(self) -> None:
        """Move selected strings to a virtual block (Category)."""
        self.category_handler.move_selection_to_category()

    def rename_category(self, block_idx: int, old_name: str) -> None:
        """Rename a virtual block."""
        self.category_handler.rename_category(block_idx, old_name)

    def delete_category(self, block_idx: int, category_name: str) -> None:
        """Remove a virtual block (the strings remain in the block)."""
        self.category_handler.delete_category(block_idx, category_name)

    def toggle_highlight_categorized(self, checked: bool) -> None:
        """Toggle highlighting of categorized strings in parent block."""
        self.mw.data_store.highlight_categorized = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_current_view()
        self.data_processor.schedule_autosave()

    def toggle_hide_categorized(self, checked: bool) -> None:
        """Toggle hiding of categorized strings in parent block."""
        self.mw.data_store.hide_categorized = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_current_view()
        self.data_processor.schedule_autosave()

    def toggle_hide_empty_strings(self, checked: bool) -> None:
        """Toggle hiding of empty strings in preview list."""
        self.mw.data_store.hide_empty_strings = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_current_view()
        self.data_processor.schedule_autosave()

    def toggle_hide_translated(self, checked: bool) -> None:
        """Toggle hiding of translated strings in preview list."""
        self.mw.data_store.hide_translated = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_current_view()
        self.data_processor.schedule_autosave()

    def toggle_show_overrides_only(self, checked: bool) -> None:
        """Toggle showing only strings with layout overrides in preview list."""
        if checked:
            self._saved_scrollbar_value = self.mw.preview_text_edit.verticalScrollBar().value() if hasattr(self.mw, 'preview_text_edit') and self.mw.preview_text_edit else 0
            self._saved_string_idx = self.mw.data_store.current_string_idx
            if hasattr(self.mw, 'preview_text_edit') and self.mw.preview_text_edit:
                line_height = self.mw.preview_text_edit.cursorRect().height() or 20
                self._saved_approx_visible_lines = int(self._saved_scrollbar_value / line_height) + 50
            else:
                self._saved_approx_visible_lines = 0
        self.mw.data_store.show_overrides_only = checked

        preview_updater = getattr(self.ui_updater, 'preview_updater', None)
        if preview_updater:
            preview_updater._keep_progress_dialog_open = True
            preview_updater._load_fully_synchronously = True

        try:
            if self.mw.data_store.current_block_idx != -1:
                self.ui_updater.populate_current_view()
        finally:
            if preview_updater:
                preview_updater._load_fully_synchronously = False

        if not checked:
            current_idx = self.mw.data_store.current_string_idx
            saved_idx = getattr(self, '_saved_string_idx', -1)

            if current_idx == saved_idx:
                if hasattr(self.mw, 'preview_text_edit') and self.mw.preview_text_edit:
                    rel_idx = -1
                    displayed_indices = self._get_displayed_indices()
                    if current_idx in displayed_indices:
                        rel_idx = displayed_indices.index(current_idx)
                    if rel_idx != -1 and hasattr(self.mw.preview_text_edit, 'set_selected_lines'):
                        self.mw.preview_text_edit.set_selected_lines([rel_idx])

                    saved_val = getattr(self, '_saved_scrollbar_value', 0)
                    self.mw.preview_text_edit.verticalScrollBar().setValue(saved_val)
            else:
                if current_idx != -1:
                    self.scroll_to_current_string_in_preview()

            self._saved_approx_visible_lines = 0

        # Close progress dialog after layout and scrolling are fully completed
        if preview_updater:
            preview_updater._keep_progress_dialog_open = False
            if hasattr(preview_updater, '_active_progress_dialog') and preview_updater._active_progress_dialog:
                preview_updater._active_progress_dialog.close()
                preview_updater._active_progress_dialog = None
        self.data_processor.schedule_autosave()

    def toggle_hide_original_tags(self, checked: bool) -> None:
        """Toggle hiding of tags in every text panel from the single UI control."""
        self.mw.data_store.hide_original_tags = checked
        self.mw.data_store.hide_translation_tags = checked
        if hasattr(self.mw, 'helper') and hasattr(self.mw.helper, 'reconfigure_all_highlighters'):
            self.mw.helper.reconfigure_all_highlighters()
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_current_view()
        self.data_processor.schedule_autosave()

    def toggle_hide_translation_tags(self, checked: bool) -> None:
        """Toggle hiding of tags in the translation and preview text edits."""
        self.mw.data_store.hide_translation_tags = checked
        if hasattr(self.mw, 'helper') and hasattr(self.mw.helper, 'reconfigure_all_highlighters'):
            self.mw.helper.reconfigure_all_highlighters()
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_current_view()
        self.data_processor.schedule_autosave()

    def toggle_hide_tags_global(self) -> None:
        """Toggle hiding of tags globally for both original and translation."""
        checkbox = getattr(self.mw, 'hide_original_tags_checkbox', None)
        current_state = checkbox.isChecked() if checkbox else self.mw.data_store.hide_original_tags
        target_state = not current_state

        if checkbox:
            checkbox.setChecked(target_state)
        else:
            self.mw.data_store.hide_original_tags = target_state
            self.mw.data_store.hide_translation_tags = target_state
            if hasattr(self.mw, 'helper') and hasattr(self.mw.helper, 'reconfigure_all_highlighters'):
                self.mw.helper.reconfigure_all_highlighters()
            if self.mw.data_store.current_block_idx != -1:
                self.ui_updater.populate_current_view()
        self.data_processor.schedule_autosave()

    def toggle_show_unsaved_only(self, checked: bool) -> None:
        """Toggle showing only unsaved strings in preview list."""
        self.mw.data_store.show_unsaved_only = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_current_view()
        self.data_processor.schedule_autosave()

    def toggle_show_unsaved_blocks_only(self, checked: bool) -> None:
        """Toggle showing only unsaved blocks in the tree."""
        self.mw.data_store.show_unsaved_blocks_only = checked
        self.ui_updater.block_list_updater.populate_blocks()
        self.data_processor.schedule_autosave()

    def toggle_show_warnings_only(self, checked: bool) -> None:
        """Toggle showing only strings matching active warning filters."""
        self.mw.data_store.show_warnings_only = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_current_view()
        self.data_processor.schedule_autosave()

    def warnings_filter_changed(self, active_warnings: list) -> None:
        """Handle change in active warning filters selection."""
        self.mw.data_store.active_warning_filters = active_warnings
        if self.mw.data_store.current_block_idx != -1 and getattr(self.mw.data_store, 'show_warnings_only', False):
            self.ui_updater.populate_current_view()
        self.data_processor.schedule_autosave()

    def open_warnings_filter_dialog(self) -> None:
        """Open the WarningsFilterDialog to select warning filters."""
        from ui.warnings_filter_dialog import WarningsFilterDialog

        defs = self.mw.current_game_rules.get_problem_definitions() if self.mw.current_game_rules else {}
        detection_enabled = getattr(self.mw, 'detection_enabled', {})
        active_pids = [pid for pid in defs.keys() if detection_enabled.get(pid, True)]
        selected_pids = getattr(self.mw.data_store, 'active_warning_filters', [])

        dialog = WarningsFilterDialog(defs, active_pids, selected_pids, self.mw)
        if dialog.exec():
            new_selected = dialog.get_selected_pids()
            self.warnings_filter_changed(new_selected)
            if hasattr(self.mw, 'plugin_handler') and self.mw.plugin_handler:
                self.mw.plugin_handler.update_warnings_filter_button()
