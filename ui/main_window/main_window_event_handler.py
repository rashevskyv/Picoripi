from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt6.QtGui import QTextCursor, QKeyEvent
from PyQt6.QtCore import QTimer
from utils.logging_utils import log_debug, log_info, log_warning, log_error
from utils.utils import ALL_TAGS_PATTERN

if TYPE_CHECKING:
    from main import MainWindow

class MainWindowEventHandler:
    """Handler for main window event operations."""
    def __init__(self, main_window: MainWindow):
        """Initialize a new instance."""
        self.mw = main_window

    def _clear_speaker_commit_guard(self) -> None:
        combo = getattr(self.mw, 'speaker_combobox', None)
        if combo is not None:
            combo._speaker_commit_pending = False

    def _commit_speaker_selection(self, *_signal_args) -> None:
        """Commit one combo interaction once, despite Qt emitting duplicate signals."""
        combo = getattr(self.mw, 'speaker_combobox', None)
        if combo is None or getattr(combo, '_speaker_commit_pending', False):
            return
        combo._speaker_commit_pending = True
        value = combo.currentText().strip()
        folded_value = value.casefold()
        for index in range(combo.count()):
            candidate = combo.itemText(index).strip()
            if candidate.casefold() == folded_value:
                value = candidate
                if combo.currentText() != candidate:
                    combo.setCurrentText(candidate)
                break
        try:
            self.mw.list_selection_handler.save_speaker_for_current_string(value)
        finally:
            # Editable QComboBox can emit activated/returnPressed repeatedly for
            # one Enter key. Keep the guard until that complete event is over.
            QTimer.singleShot(0, self._clear_speaker_commit_guard)

    def _force_refresh_virtual_folders(self) -> None:
        """Rebuild the virtual folders from the current story data (⟳ button)."""
        updater = getattr(getattr(self.mw, "ui_updater", None), "block_list_updater", None)
        refresh = getattr(updater, "force_refresh_virtual_folders", None)
        if callable(refresh):
            refresh()

    def _connect_speaker_combobox(self) -> None:
        """Wire the speaker combo so only Enter commits.

        Clicking an autocomplete suggestion fires ``activated`` and merely fills
        the field; the user commits the speaker deliberately by pressing Enter.
        """
        combo = getattr(self.mw, 'speaker_combobox', None)
        if combo is None:
            return
        combo.lineEdit().returnPressed.connect(self._commit_speaker_selection)

    def connect_signals(self):
        """Connect signals."""
        if hasattr(self.mw, 'toggle_preview_action') and self.mw.toggle_preview_action:
            self.mw.toggle_preview_action.triggered.connect(self.mw.ui_updater.update_preview_visibility)
        if hasattr(self.mw, 'toggle_hide_tags_action') and self.mw.toggle_hide_tags_action:
            self.mw.toggle_hide_tags_action.triggered.connect(self.mw.list_selection_handler.toggle_hide_tags_global)
        if hasattr(self.mw, 'open_settings_action'): self.mw.open_settings_action.triggered.connect(self.mw.actions.open_settings_dialog)
        if hasattr(self.mw, 'run_external_script_action') and self.mw.run_external_script_action:
            self.mw.run_external_script_action.triggered.connect(self.mw.actions.run_external_script)
        if hasattr(self.mw, 'bfn_editor_action') and self.mw.bfn_editor_action:
            self.mw.bfn_editor_action.triggered.connect(self.mw.actions.open_bfn_editor_standalone)
        if hasattr(self.mw, 'script_markup_studio_action') and self.mw.script_markup_studio_action:
            self.mw.script_markup_studio_action.triggered.connect(self.mw.actions.open_script_markup_studio)
        if hasattr(self.mw, 'mempalace_builder_action') and self.mw.mempalace_builder_action:
            self.mw.mempalace_builder_action.triggered.connect(self.mw.actions.open_mempalace_builder)
        if hasattr(self.mw, 'inspect_story_context_action') and self.mw.inspect_story_context_action:
            self.mw.inspect_story_context_action.triggered.connect(self.mw.actions.inspect_story_context)
        if hasattr(self.mw, 'build_glossary_text_action') and self.mw.build_glossary_text_action:
            self.mw.build_glossary_text_action.triggered.connect(self.mw.actions.build_glossary_from_text)
        if hasattr(self.mw, 'mempalace_viewer_action') and self.mw.mempalace_viewer_action:
            self.mw.mempalace_viewer_action.triggered.connect(self.mw.actions.open_mempalace_viewer)
        if hasattr(self.mw, 'fix_all_strings_action') and self.mw.fix_all_strings_action:
            self.mw.fix_all_strings_action.triggered.connect(self.mw.editor_operation_handler.fix_all_strings)
        if hasattr(self.mw, 'export_bmg_json_action') and self.mw.export_bmg_json_action:
            self.mw.export_bmg_json_action.triggered.connect(self.mw.actions.export_current_bmg_to_json)
        if hasattr(self.mw, 'import_bmg_json_action') and self.mw.import_bmg_json_action:
            self.mw.import_bmg_json_action.triggered.connect(self.mw.actions.import_current_bmg_from_json)
        if hasattr(self.mw, 'help_shortcuts_action'): self.mw.help_shortcuts_action.triggered.connect(self.mw.actions.show_shortcuts_help)
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.currentItemChanged.connect(self.mw.list_selection_handler.block_selected)
            self.mw.block_list_widget.itemClicked.connect(self.mw.list_selection_handler.refresh_empty_virtual_view_on_click)
            self.mw.block_list_widget.itemDoubleClicked.connect(self.mw.list_selection_handler.rename_block)
            self.mw.block_list_widget.itemChanged.connect(self.mw.list_selection_handler.handle_block_item_text_changed)
        
        if hasattr(self.mw, 'preview_text_edit'):
            if hasattr(self.mw.preview_text_edit, 'lineClicked'):
                self.mw.preview_text_edit.lineClicked.connect(lambda idx: self.mw.list_selection_handler.string_selected_from_preview(idx, is_manual_click=True))
            self.mw.preview_text_edit.previewSelectionChanged.connect(self.mw.list_selection_handler.handle_preview_selection_changed)

        if hasattr(self.mw, 'edited_text_edit'):
            self.mw.edited_text_edit.textChanged.connect(self.mw.editor_operation_handler.text_edited)
            self.mw.edited_text_edit.cursorPositionChanged.connect(self.handle_edited_cursor_position_changed)
            self.mw.edited_text_edit.selectionChanged.connect(self.handle_edited_selection_changed)
            if hasattr(self.mw, 'undo_typing_action'):
                self.mw.undo_typing_action.triggered.connect(self.mw.undo_manager.undo)
            if hasattr(self.mw, 'redo_typing_action'):
                self.mw.redo_typing_action.triggered.connect(self.mw.undo_manager.redo)
            if hasattr(self.mw.edited_text_edit, 'addTagMappingRequest'):
                self.mw.edited_text_edit.addTagMappingRequest.connect(self.mw.actions.handle_add_tag_mapping_request)
        if hasattr(self.mw, 'paste_block_action'): self.mw.paste_block_action.triggered.connect(self.mw.editor_operation_handler.paste_block_text)

        # Project actions
        if hasattr(self.mw, 'new_project_action'):
            self.mw.new_project_action.triggered.connect(self.mw.project_action_handler.create_new_project_action)
        if hasattr(self.mw, 'open_project_action'):
            self.mw.open_project_action.triggered.connect(self.mw.project_action_handler.open_project_action)
        if hasattr(self.mw, 'close_project_action'):
            self.mw.close_project_action.triggered.connect(self.mw.project_action_handler.close_project_action)
        if hasattr(self.mw, 'import_block_action'):
            self.mw.import_block_action.triggered.connect(self.mw.project_action_handler.import_block_action)
        if hasattr(self.mw, 'import_directory_action'):
            self.mw.import_directory_action.triggered.connect(self.mw.project_action_handler.import_directory_action)
        if hasattr(self.mw, 'add_block_button'):
            self.mw.add_block_button.clicked.connect(self.mw.project_action_handler.import_block_action)

        # Block toolbar buttons
        if hasattr(self.mw, 'delete_block_button'):
            self.mw.delete_block_button.clicked.connect(self.mw.project_action_handler.delete_block_action)
        if hasattr(self.mw, 'rename_block_button'):
            self.mw.rename_block_button.clicked.connect(lambda: self.mw.list_selection_handler.rename_block(self.mw.block_list_widget.currentItem()))
        if hasattr(self.mw, 'move_block_up_button'):
            self.mw.move_block_up_button.clicked.connect(lambda: self.mw.project_action_handler.move_block_action(-1))
        if hasattr(self.mw, 'move_block_down_button'):
            self.mw.move_block_down_button.clicked.connect(lambda: self.mw.project_action_handler.move_block_action(1))
        if hasattr(self.mw, 'refresh_virtual_blocks_button'):
            self.mw.refresh_virtual_blocks_button.clicked.connect(self._force_refresh_virtual_folders)
        if hasattr(self.mw, 'add_folder_button'):
            self.mw.add_folder_button.clicked.connect(self.mw.project_action_handler.add_folder_action)
        
        if hasattr(self.mw, 'expand_all_button'):
            self.mw.expand_all_button.clicked.connect(self.mw.project_action_handler.expand_all_action)
        if hasattr(self.mw, 'collapse_all_button'):
            self.mw.collapse_all_button.clicked.connect(self.mw.project_action_handler.collapse_all_action)
        
        # Navigation connections
        if hasattr(self.mw, 'next_block_nav_action'):
            self.mw.next_block_nav_action.triggered.connect(lambda: (log_debug("TRIGGER: next_block_nav_action"), self.mw.list_selection_handler.navigate_between_blocks(True)))
        if hasattr(self.mw, 'prev_block_nav_action'):
            self.mw.prev_block_nav_action.triggered.connect(lambda: (log_debug("TRIGGER: prev_block_nav_action"), self.mw.list_selection_handler.navigate_between_blocks(False)))
        if hasattr(self.mw, 'next_folder_nav_action'):
            self.mw.next_folder_nav_action.triggered.connect(lambda: self.mw.list_selection_handler.navigate_between_folders(True))
        if hasattr(self.mw, 'prev_folder_nav_action'):
            self.mw.prev_folder_nav_action.triggered.connect(lambda: self.mw.list_selection_handler.navigate_between_folders(False))

        # File actions
        if hasattr(self.mw, 'save_action'):
            try:
                log_info(f"Connecting save_action: exists={self.mw.save_action is not None}", category="lifecycle")
                if self.mw.save_action:
                    self.mw.save_action.triggered.connect(self.mw.actions.trigger_save_action)
                    log_info("Successfully connected save_action.triggered to trigger_save_action", category="lifecycle")
                else:
                    log_warning("save_action is None, cannot connect triggered signal!", category="lifecycle")
            except Exception as conn_err:
                log_error(f"Error connecting save_action signal: {conn_err}", exc_info=True, category="lifecycle")
        if hasattr(self.mw, 'reload_action'): self.mw.reload_action.triggered.connect(self.mw.app_action_handler.reload_original_data_action)
        if hasattr(self.mw, 'save_as_action'): self.mw.save_as_action.triggered.connect(self.mw.app_action_handler.save_as_dialog_action)
        if hasattr(self.mw, 'revert_action'): self.mw.revert_action.triggered.connect(self.mw.actions.trigger_revert_action)
        if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.triggered.connect(self.mw.actions.trigger_undo_paste_action)
        if hasattr(self.mw, 'rescan_all_tags_action'): self.mw.rescan_all_tags_action.triggered.connect(self.mw.app_action_handler.rescan_all_tags)
        if hasattr(self.mw, 'recalculate_widths_action'):
            self.mw.recalculate_widths_action.triggered.connect(self.mw.actions.trigger_recalculate_widths)
        if hasattr(self.mw, 'reload_tag_mappings_action'):
            self.mw.reload_tag_mappings_action.triggered.connect(self.mw.actions.trigger_reload_tag_mappings)
        if hasattr(self.mw, 'find_action'):
            self.mw.find_action.triggered.connect(self.mw.helper.toggle_search_panel)
        if hasattr(self.mw, 'advanced_search_action') and self.mw.advanced_search_action:
            self.mw.advanced_search_action.triggered.connect(self.mw.helper.trigger_advanced_search)
        if hasattr(self.mw, 'add_bookmark_action') and self.mw.add_bookmark_action:
            self.mw.add_bookmark_action.triggered.connect(self.mw.bookmark_handler.add_bookmark)
        if hasattr(self.mw, 'clear_bookmarks_action') and self.mw.clear_bookmarks_action:
            self.mw.clear_bookmarks_action.triggered.connect(self.mw.bookmark_handler.clear_bookmarks)
        if hasattr(self.mw, 'open_ai_chat_action'):
            self.mw.open_ai_chat_action.triggered.connect(self.mw.ai_chat_handler.show_chat_window)
        if hasattr(self.mw, 'search_panel_widget'):
            self.mw.search_panel_widget.close_requested.connect(self.mw.helper.hide_search_panel)
            self.mw.search_panel_widget.find_next_requested.connect(self.mw.helper.handle_panel_find_next)
            self.mw.search_panel_widget.find_previous_requested.connect(self.mw.helper.handle_panel_find_previous)
            if hasattr(self.mw.search_panel_widget, 'advanced_search_requested'):
                self.mw.search_panel_widget.advanced_search_requested.connect(self.mw.helper.open_advanced_search)
        
        if hasattr(self.mw, 'restore_translation_button') and self.mw.restore_translation_button:
            self.mw.restore_translation_button.clicked.connect(self.mw.saved_translations_handler.restore_translation_action)
        if hasattr(self.mw, 'save_translated_action') and self.mw.save_translated_action:
            self.mw.save_translated_action.triggered.connect(self.mw.saved_translations_handler.save_translation_action)
        if hasattr(self.mw, 'restore_translated_action') and self.mw.restore_translated_action:
            self.mw.restore_translated_action.triggered.connect(self.mw.saved_translations_handler.restore_translation_action)
        if hasattr(self.mw, 'export_translations_action') and self.mw.export_translations_action:
            self.mw.export_translations_action.triggered.connect(self.mw.saved_translations_handler.export_translations_to_json_action)
        if hasattr(self.mw, 'export_original_action') and self.mw.export_original_action:
            self.mw.export_original_action.triggered.connect(self.mw.saved_translations_handler.export_original_to_json_action)
        if hasattr(self.mw, 'import_translations_action') and self.mw.import_translations_action:
            self.mw.import_translations_action.triggered.connect(self.mw.saved_translations_handler.import_translations_from_json_action)

        if hasattr(self.mw, 'ai_translate_button') and self.mw.ai_translate_button:
            self.mw.ai_translate_button.clicked.connect(self.mw.translation_handler.translate_current_string)
        if hasattr(self.mw, 'ai_variation_button') and self.mw.ai_variation_button:
            self.mw.ai_variation_button.clicked.connect(self.mw.translation_handler.generate_variation_for_current_string)
        if hasattr(self.mw, 'auto_fix_button') and self.mw.auto_fix_button:
            self.mw.auto_fix_button.clicked.connect(lambda checked=False: self.mw.editor_operation_handler.auto_fix_current_string(from_button=True))
        if hasattr(self.mw, 'auto_fix_action') and self.mw.auto_fix_action: 
            self.mw.auto_fix_action.triggered.connect(lambda checked=False: self.mw.editor_operation_handler.auto_fix_current_string(from_button=False))
            
        if hasattr(self.mw, 'navigate_up_button'):
            self.mw.navigate_up_button.clicked.connect(lambda: self.mw.list_selection_handler.navigate_to_problem_string(direction_down=False))
        if hasattr(self.mw, 'navigate_down_button'):
            self.mw.navigate_down_button.clicked.connect(lambda: self.mw.list_selection_handler.navigate_to_problem_string(direction_down=True))
        
        if hasattr(self.mw, 'revert_string_button'):
            self.mw.revert_string_button.clicked.connect(lambda: self.mw.data_processor.perform_revert_strings(self.mw.data_store.current_block_idx, [self.mw.data_store.current_string_idx]) if self.mw.data_store.current_block_idx != -1 and self.mw.data_store.current_string_idx != -1 else None)
        
        if hasattr(self.mw, 'inspect_story_context_button') and self.mw.inspect_story_context_button:
            self.mw.inspect_story_context_button.clicked.connect(self.mw.actions.inspect_story_context)
        
        
        if hasattr(self.mw, 'font_combobox'):
            self.mw.font_combobox.currentIndexChanged.connect(self.mw.string_settings_handler.on_font_changed)
        if hasattr(self.mw, 'width_spinbox'):
            self.mw.width_spinbox.valueChanged.connect(self.mw.string_settings_handler.on_width_changed)
        if hasattr(self.mw, 'apply_width_button'):
            self.mw.apply_width_button.clicked.connect(self.mw.string_settings_handler.apply_settings_change)
        if hasattr(self.mw, 'original_width_label'):
            self.mw.original_width_label.clicked.connect(
                self.mw.string_settings_handler.copy_original_width_to_editor
            )

        if hasattr(self.mw, 'highlight_categorized_checkbox'):
            self.mw.highlight_categorized_checkbox.toggled.connect(self.mw.list_selection_handler.toggle_highlight_categorized)
        if hasattr(self.mw, 'hide_categorized_checkbox'):
            self.mw.hide_categorized_checkbox.toggled.connect(self.mw.list_selection_handler.toggle_hide_categorized)
        if hasattr(self.mw, 'hide_empty_strings_checkbox'):
            self.mw.hide_empty_strings_checkbox.toggled.connect(self.mw.list_selection_handler.toggle_hide_empty_strings)
        if hasattr(self.mw, 'hide_translated_checkbox'):
            self.mw.hide_translated_checkbox.toggled.connect(self.mw.list_selection_handler.toggle_hide_translated)
        if hasattr(self.mw, 'show_overrides_only_checkbox'):
            self.mw.show_overrides_only_checkbox.toggled.connect(self.mw.list_selection_handler.toggle_show_overrides_only)
        if hasattr(self.mw, 'show_unsaved_only_checkbox'):
            self.mw.show_unsaved_only_checkbox.toggled.connect(self.mw.list_selection_handler.toggle_show_unsaved_only)
        if hasattr(self.mw, 'show_unsaved_blocks_checkbox'):
            self.mw.show_unsaved_blocks_checkbox.toggled.connect(self.mw.list_selection_handler.toggle_show_unsaved_blocks_only)
        if hasattr(self.mw, 'hide_original_tags_checkbox'):
            self.mw.hide_original_tags_checkbox.toggled.connect(self.mw.list_selection_handler.toggle_hide_original_tags)
        if hasattr(self.mw, 'hide_translation_tags_checkbox'):
            self.mw.hide_translation_tags_checkbox.toggled.connect(self.mw.list_selection_handler.toggle_hide_translation_tags)

        self._connect_speaker_combobox()
        if hasattr(self.mw, 'chapter_combobox') and self.mw.chapter_combobox is not None:
            self.mw.chapter_combobox.activated.connect(
                lambda: self.mw.list_selection_handler.save_chapter_for_current_string(
                    self.mw.chapter_combobox.currentData()
                )
            )
        speaker_label = getattr(self.mw, 'speaker_select_label', None)
        if speaker_label is not None:
            speaker_label.doubleClicked.connect(
                self.mw.list_selection_handler.navigate_to_current_story_role
            )
        window_label = getattr(self.mw, 'window_kind_label', None)
        if window_label is not None:
            window_label.doubleClicked.connect(
                self.mw.list_selection_handler.navigate_to_current_physical_block
            )
        chapter_label = getattr(self.mw, 'chapter_select_label', None)
        if chapter_label is not None:
            chapter_label.doubleClicked.connect(
                self.mw.list_selection_handler.navigate_to_current_story_structure
            )
        studio_button = getattr(self.mw, 'open_current_string_in_markup_studio_button', None)
        if studio_button is not None:
            studio_button.clicked.connect(
                self.mw.list_selection_handler.speaker_handler.open_current_string_in_markup_studio
            )
        if hasattr(self.mw, 'show_warnings_only_checkbox') and self.mw.show_warnings_only_checkbox:
            self.mw.show_warnings_only_checkbox.toggled.connect(self.mw.list_selection_handler.toggle_show_warnings_only)
        if hasattr(self.mw, 'warnings_filter_button') and self.mw.warnings_filter_button:
            self.mw.warnings_filter_button.clicked.connect(self.mw.list_selection_handler.open_warnings_filter_dialog)

    def keyPressEvent(self, event: QKeyEvent):
        """Keypressevent."""
        super(self.mw.__class__, self.mw).keyPressEvent(event)
        
    def closeEvent(self, event):
        """Closeevent."""
        log_info("Close event received.")
        if hasattr(self.mw, 'hotkey_manager'):
            self.mw.hotkey_manager.unregister()
        self.mw.helper.prepare_to_close()
        self.mw.app_action_handler.handle_close_event(event)
        
        if event.isAccepted():
            if hasattr(self.mw, 'list_selection_handler') and self.mw.list_selection_handler:
                try:
                    self.mw.list_selection_handler.cleanup()
                except Exception:
                    pass
            if hasattr(self.mw, 'data_processor') and self.mw.data_processor:
                self.mw.data_processor.finalize_clean_shutdown_checkpoint()
            self.disconnect_signals()
            if hasattr(self.mw, 'event_filter') and self.mw.event_filter:
                try:
                    from PyQt6.QtWidgets import QApplication
                    QApplication.instance().removeEventFilter(self.mw.event_filter)
                    self.mw.event_filter = None
                except Exception as e:
                    log_debug(f"Error removing event filter: {e}")
            # Always save user settings (geometry, last path, etc.) unless restarting
            if not self.mw.is_restart_in_progress:
                self.mw.settings_manager.save_settings()
            super(self.mw.__class__, self.mw).closeEvent(event)

    def disconnect_signals(self):
        """Disconnects all signals connected during initialization."""
        log_info("Disconnecting all event handler signals...")
        
        # Helper to safely disconnect a signal or slot
        def safe_disconnect(obj, signal_name):
            """Safe disconnect."""
            if hasattr(obj, signal_name):
                sig = getattr(obj, signal_name)
                try:
                    sig.disconnect()
                except (TypeError, RuntimeError):
                    pass # Signal was not connected or object already deleted

        mw = self.mw
        # Actions and Buttons
        safe_disconnect(mw, 'toggle_preview_action')
        if hasattr(mw, 'toggle_preview_action'): safe_disconnect(mw.toggle_preview_action, 'triggered')
        safe_disconnect(mw, 'toggle_hide_tags_action')
        if hasattr(mw, 'toggle_hide_tags_action'): safe_disconnect(mw.toggle_hide_tags_action, 'triggered')
        if hasattr(mw, 'open_settings_action'): safe_disconnect(mw.open_settings_action, 'triggered')
        if hasattr(mw, 'run_external_script_action'): safe_disconnect(mw.run_external_script_action, 'triggered')
        if hasattr(mw, 'bfn_editor_action'): safe_disconnect(mw.bfn_editor_action, 'triggered')
        if hasattr(mw, 'script_markup_studio_action'): safe_disconnect(mw.script_markup_studio_action, 'triggered')
        if hasattr(mw, 'mempalace_builder_action'): safe_disconnect(mw.mempalace_builder_action, 'triggered')
        if hasattr(mw, 'inspect_story_context_action'): safe_disconnect(mw.inspect_story_context_action, 'triggered')
        if hasattr(mw, 'build_glossary_text_action'): safe_disconnect(mw.build_glossary_text_action, 'triggered')
        if hasattr(mw, 'mempalace_viewer_action'): safe_disconnect(mw.mempalace_viewer_action, 'triggered')
        if hasattr(mw, 'fix_all_strings_action'): safe_disconnect(mw.fix_all_strings_action, 'triggered')
        if hasattr(mw, 'export_bmg_json_action'): safe_disconnect(mw.export_bmg_json_action, 'triggered')
        if hasattr(mw, 'import_bmg_json_action'): safe_disconnect(mw.import_bmg_json_action, 'triggered')
        if hasattr(mw, 'help_shortcuts_action'): safe_disconnect(mw.help_shortcuts_action, 'triggered')
        
        # Widgets
        if hasattr(mw, 'block_list_widget'):
            safe_disconnect(mw.block_list_widget, 'currentItemChanged')
            safe_disconnect(mw.block_list_widget, 'itemClicked')
            safe_disconnect(mw.block_list_widget, 'itemDoubleClicked')
            safe_disconnect(mw.block_list_widget, 'itemChanged')
            
        if hasattr(mw, 'preview_text_edit'):
            safe_disconnect(mw.preview_text_edit, 'lineClicked')
            safe_disconnect(mw.preview_text_edit, 'previewSelectionChanged')

        if hasattr(mw, 'edited_text_edit'):
            safe_disconnect(mw.edited_text_edit, 'textChanged')
            safe_disconnect(mw.edited_text_edit, 'cursorPositionChanged')
            safe_disconnect(mw.edited_text_edit, 'selectionChanged')
            safe_disconnect(mw.edited_text_edit, 'addTagMappingRequest')

        if hasattr(mw, 'undo_typing_action'): safe_disconnect(mw.undo_typing_action, 'triggered')
        if hasattr(mw, 'redo_typing_action'): safe_disconnect(mw.redo_typing_action, 'triggered')
        if hasattr(mw, 'paste_block_action'): safe_disconnect(mw.paste_block_action, 'triggered')

        # Project actions
        if hasattr(mw, 'new_project_action'): safe_disconnect(mw.new_project_action, 'triggered')
        if hasattr(mw, 'open_project_action'): safe_disconnect(mw.open_project_action, 'triggered')
        if hasattr(mw, 'close_project_action'): safe_disconnect(mw.close_project_action, 'triggered')
        if hasattr(mw, 'import_block_action'): safe_disconnect(mw.import_block_action, 'triggered')
        if hasattr(mw, 'import_directory_action'): safe_disconnect(mw.import_directory_action, 'triggered')
        if hasattr(mw, 'add_block_button'): safe_disconnect(mw.add_block_button, 'clicked')
        if hasattr(mw, 'delete_block_button'): safe_disconnect(mw.delete_block_button, 'clicked')
        if hasattr(mw, 'rename_block_button'): safe_disconnect(mw.rename_block_button, 'clicked')
        if hasattr(mw, 'move_block_up_button'): safe_disconnect(mw.move_block_up_button, 'clicked')
        if hasattr(mw, 'move_block_down_button'): safe_disconnect(mw.move_block_down_button, 'clicked')
        if hasattr(mw, 'refresh_virtual_blocks_button'): safe_disconnect(mw.refresh_virtual_blocks_button, 'clicked')
        if hasattr(mw, 'add_folder_button'): safe_disconnect(mw.add_folder_button, 'clicked')
        if hasattr(mw, 'expand_all_button'): safe_disconnect(mw.expand_all_button, 'clicked')
        if hasattr(mw, 'collapse_all_button'): safe_disconnect(mw.collapse_all_button, 'clicked')

        # Navigation
        if hasattr(mw, 'next_block_nav_action'): safe_disconnect(mw.next_block_nav_action, 'triggered')
        if hasattr(mw, 'prev_block_nav_action'): safe_disconnect(mw.prev_block_nav_action, 'triggered')
        if hasattr(mw, 'next_folder_nav_action'): safe_disconnect(mw.next_folder_nav_action, 'triggered')
        if hasattr(mw, 'prev_folder_nav_action'): safe_disconnect(mw.prev_folder_nav_action, 'triggered')

        # File actions
        if hasattr(mw, 'save_action'): safe_disconnect(mw.save_action, 'triggered')
        if hasattr(mw, 'reload_action'): safe_disconnect(mw.reload_action, 'triggered')
        if hasattr(mw, 'save_as_action'): safe_disconnect(mw.save_as_action, 'triggered')
        if hasattr(mw, 'revert_action'): safe_disconnect(mw.revert_action, 'triggered')
        if hasattr(mw, 'undo_paste_action'): safe_disconnect(mw.undo_paste_action, 'triggered')
        if hasattr(mw, 'rescan_all_tags_action'): safe_disconnect(mw.rescan_all_tags_action, 'triggered')
        if hasattr(mw, 'recalculate_widths_action'): safe_disconnect(mw.recalculate_widths_action, 'triggered')
        if hasattr(mw, 'reload_tag_mappings_action'): safe_disconnect(mw.reload_tag_mappings_action, 'triggered')
        if hasattr(mw, 'find_action'): safe_disconnect(mw.find_action, 'triggered')
        if hasattr(mw, 'advanced_search_action'): safe_disconnect(mw.advanced_search_action, 'triggered')
        if hasattr(mw, 'add_bookmark_action'): safe_disconnect(mw.add_bookmark_action, 'triggered')
        if hasattr(mw, 'clear_bookmarks_action'): safe_disconnect(mw.clear_bookmarks_action, 'triggered')
        if hasattr(mw, 'open_ai_chat_action'): safe_disconnect(mw.open_ai_chat_action, 'triggered')

        # Widgets and Custom Panels
        if hasattr(mw, 'search_panel_widget') and mw.search_panel_widget:
            safe_disconnect(mw.search_panel_widget, 'close_requested')
            safe_disconnect(mw.search_panel_widget, 'find_next_requested')
            safe_disconnect(mw.search_panel_widget, 'find_previous_requested')
            safe_disconnect(mw.search_panel_widget, 'advanced_search_requested')

        if hasattr(mw, 'restore_translation_button'): safe_disconnect(mw.restore_translation_button, 'clicked')
        if hasattr(mw, 'save_translated_action'): safe_disconnect(mw.save_translated_action, 'triggered')
        if hasattr(mw, 'restore_translated_action'): safe_disconnect(mw.restore_translated_action, 'triggered')
        if hasattr(mw, 'export_translations_action'): safe_disconnect(mw.export_translations_action, 'triggered')
        if hasattr(mw, 'export_original_action'): safe_disconnect(mw.export_original_action, 'triggered')
        if hasattr(mw, 'import_translations_action'): safe_disconnect(mw.import_translations_action, 'triggered')

        if hasattr(mw, 'ai_translate_button'): safe_disconnect(mw.ai_translate_button, 'clicked')
        if hasattr(mw, 'ai_variation_button'): safe_disconnect(mw.ai_variation_button, 'clicked')
        if hasattr(mw, 'auto_fix_button'): safe_disconnect(mw.auto_fix_button, 'clicked')
        if hasattr(mw, 'auto_fix_action'): safe_disconnect(mw.auto_fix_action, 'triggered')
        if hasattr(mw, 'navigate_up_button'): safe_disconnect(mw.navigate_up_button, 'clicked')
        if hasattr(mw, 'navigate_down_button'): safe_disconnect(mw.navigate_down_button, 'clicked')
        if hasattr(mw, 'revert_string_button'): safe_disconnect(mw.revert_string_button, 'clicked')
        if hasattr(mw, 'inspect_story_context_button'): safe_disconnect(mw.inspect_story_context_button, 'clicked')

        if hasattr(mw, 'font_combobox'): safe_disconnect(mw.font_combobox, 'currentIndexChanged')
        if hasattr(mw, 'width_spinbox'): safe_disconnect(mw.width_spinbox, 'valueChanged')
        if hasattr(mw, 'apply_width_button'): safe_disconnect(mw.apply_width_button, 'clicked')
        if hasattr(mw, 'original_width_label'): safe_disconnect(mw.original_width_label, 'clicked')

        # Checkboxes
        if hasattr(mw, 'highlight_categorized_checkbox'): safe_disconnect(mw.highlight_categorized_checkbox, 'toggled')
        if hasattr(mw, 'hide_categorized_checkbox'): safe_disconnect(mw.hide_categorized_checkbox, 'toggled')
        if hasattr(mw, 'hide_empty_strings_checkbox'): safe_disconnect(mw.hide_empty_strings_checkbox, 'toggled')
        if hasattr(mw, 'hide_translated_checkbox'): safe_disconnect(mw.hide_translated_checkbox, 'toggled')
        if hasattr(mw, 'show_overrides_only_checkbox'): safe_disconnect(mw.show_overrides_only_checkbox, 'toggled')
        if hasattr(mw, 'show_unsaved_only_checkbox'): safe_disconnect(mw.show_unsaved_only_checkbox, 'toggled')
        if hasattr(mw, 'show_unsaved_blocks_checkbox'): safe_disconnect(mw.show_unsaved_blocks_checkbox, 'toggled')
        if hasattr(mw, 'hide_original_tags_checkbox'): safe_disconnect(mw.hide_original_tags_checkbox, 'toggled')
        if hasattr(mw, 'hide_translation_tags_checkbox'): safe_disconnect(mw.hide_translation_tags_checkbox, 'toggled')

        if hasattr(mw, 'speaker_combobox') and mw.speaker_combobox is not None:
            if mw.speaker_combobox.lineEdit():
                safe_disconnect(mw.speaker_combobox.lineEdit(), 'returnPressed')
            safe_disconnect(mw.speaker_combobox, 'activated')
        if hasattr(mw, 'chapter_combobox') and mw.chapter_combobox is not None:
            safe_disconnect(mw.chapter_combobox, 'activated')
        if hasattr(mw, 'speaker_select_label') and mw.speaker_select_label is not None:
            safe_disconnect(mw.speaker_select_label, 'doubleClicked')
        if hasattr(mw, 'window_kind_label') and mw.window_kind_label is not None:
            safe_disconnect(mw.window_kind_label, 'doubleClicked')
        if hasattr(mw, 'chapter_select_label') and mw.chapter_select_label is not None:
            safe_disconnect(mw.chapter_select_label, 'doubleClicked')
        studio_button = getattr(mw, 'open_current_string_in_markup_studio_button', None)
        if studio_button is not None:
            safe_disconnect(studio_button, 'clicked')
        if hasattr(mw, 'show_warnings_only_checkbox'):
            safe_disconnect(mw.show_warnings_only_checkbox, 'toggled')
        if hasattr(mw, 'warnings_filter_button'):
            safe_disconnect(mw.warnings_filter_button, 'clicked')

    def handle_edited_cursor_position_changed(self):
        """Handle edited cursor position changed."""
        if self.mw.is_adjusting_cursor or self.mw.is_programmatically_changing_text:
            return

        editor = self.mw.edited_text_edit
        cursor = editor.textCursor()
        current_pos = cursor.position()
        last_pos = self.mw.previous_cursor_pos
        moved_right = current_pos > last_pos

        if not cursor.hasSelection():
            self.mw.is_adjusting_cursor = True
            
            current_block = cursor.block()
            pos_in_block = cursor.positionInBlock()
            block_text = current_block.text()
            
            for match in ALL_TAGS_PATTERN.finditer(block_text):
                tag_start, tag_end = match.span()
                if tag_start < pos_in_block < tag_end:
                    if moved_right or abs(current_pos - last_pos) > 1: # Moved right or jumped (e.g., click)
                        new_cursor_pos_abs = current_block.position() + tag_end
                    else: # Moved left
                        new_cursor_pos_abs = current_block.position() + tag_start
                    
                    cursor.setPosition(new_cursor_pos_abs)
                    editor.setTextCursor(cursor)
                    break 
            self.mw.is_adjusting_cursor = False
        
        self.mw.previous_cursor_pos = editor.textCursor().position()
        self.mw.ui_updater.update_status_bar()

    def handle_edited_selection_changed(self):
        """Handle edited selection changed."""
        if self.mw.is_adjusting_selection or self.mw.is_programmatically_changing_text:
            self.mw.ui_updater.update_status_bar_selection() 
            return

        editor = self.mw.edited_text_edit
        cursor = editor.textCursor()

        if not cursor.hasSelection():
            self.mw.ui_updater.update_status_bar_selection() 
            return

        self.mw.is_adjusting_selection = True
        
        doc = editor.document()
        anchor_abs = cursor.anchor()
        position_abs = cursor.position()
        
        anchor_block = doc.findBlock(anchor_abs)
        position_block = doc.findBlock(position_abs)

        if anchor_block.blockNumber() != position_block.blockNumber():
            self.mw.is_adjusting_selection = False
            self.mw.ui_updater.update_status_bar_selection()
            return
            
        current_block = anchor_block
        block_text = current_block.text()
        
        original_anchor_rel = anchor_abs - current_block.position()
        original_position_rel = position_abs - current_block.position()
        
        current_sel_start_rel = min(original_anchor_rel, original_position_rel)
        current_sel_end_rel = max(original_anchor_rel, original_position_rel)

        new_sel_start_rel = current_sel_start_rel
        new_sel_end_rel = current_sel_end_rel
        
        adjusted = False

        for match in ALL_TAGS_PATTERN.finditer(block_text):
            tag_start, tag_end = match.span()
            
            if tag_start < current_sel_start_rel < tag_end:
                new_sel_start_rel = min(new_sel_start_rel, tag_start)
                adjusted = True
            
            if tag_start < current_sel_end_rel < tag_end:
                new_sel_end_rel = max(new_sel_end_rel, tag_end)
                adjusted = True
        
        if new_sel_start_rel > new_sel_end_rel :
            new_sel_start_rel = current_sel_start_rel
            new_sel_end_rel = current_sel_end_rel
            adjusted = False


        if adjusted and (new_sel_start_rel != current_sel_start_rel or new_sel_end_rel != current_sel_end_rel):
            new_cursor = QTextCursor(current_block)
            
            final_anchor_abs = current_block.position() + (new_sel_start_rel if original_anchor_rel == current_sel_start_rel else new_sel_end_rel)
            final_position_abs = current_block.position() + (new_sel_end_rel if original_anchor_rel == current_sel_start_rel else new_sel_start_rel)

            new_cursor.setPosition(final_anchor_abs)
            new_cursor.setPosition(final_position_abs, QTextCursor.MoveMode.KeepAnchor)
            
            editor.setTextCursor(new_cursor)
        
        self.mw.is_adjusting_selection = False
        self.mw.ui_updater.update_status_bar_selection()
