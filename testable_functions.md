# Повний список функцій для тестування

Нижче наведено перелік усіх функцій та методів класів у проекті Picoripi, згрупованих за відповідними файлами. Усі ці компоненти (як великі, так і малі) потенційно можна покрити модульними або інтеграційними тестами.

### Файл: components\ai_chat_dialog.py
- _ChatInputEventFilter.__init__
- _ChatInputEventFilter.eventFilter
- _ChatTab.__init__
- _ChatTab.populate_models
- AIChatDialog.__init__
- AIChatDialog._set_theme_styles
- AIChatDialog.eventFilter
- AIChatDialog.add_new_tab
- AIChatDialog.remove_tab
- AIChatDialog._emit_message_sent
- AIChatDialog.append_to_history
- AIChatDialog.set_input_enabled

### Файл: components\ai_status_dialog.py
- AIStatusDialog.__init__
- AIStatusDialog.on_cancel
- AIStatusDialog.closeEvent
- AIStatusDialog.setup_progress_bar
- AIStatusDialog.update_progress
- AIStatusDialog.showEvent
- AIStatusDialog.hideEvent
- AIStatusDialog.start
- AIStatusDialog.finish
- AIStatusDialog._set_model_name
- AIStatusDialog.update_step
- AIStatusDialog._update_label_style

### Файл: components\custom_list_item_delegate.py
- CustomListItemDelegate.__init__
- CustomListItemDelegate._get_current_number_area_width
- CustomListItemDelegate._get_problem_indicator_zone_width
- CustomListItemDelegate._get_color_marker_zone_width
- CustomListItemDelegate.sizeHint
- CustomListItemDelegate.paint
- CustomListItemDelegate.handle_tooltip
- CustomListItemDelegate._get_problems_tooltip_text
- CustomListItemDelegate.helpEvent
- CustomListItemDelegate.updateEditorGeometry

### Файл: components\custom_list_widget.py
- CustomListWidget.__init__
- CustomListWidget._create_color_icon
- CustomListWidget.create_item
- CustomListWidget.show_context_menu
- CustomListWidget.viewportEvent
- CustomListWidget._open_spellcheck_for_block

### Файл: components\custom_tree_widget.py
- CustomTreeWidget.__init__
- CustomTreeWidget.mousePressEvent
- CustomTreeWidget.keyPressEvent
- CustomTreeWidget.wheelEvent
- CustomTreeWidget.navigate_blocks
- CustomTreeWidget.navigate_folders
- CustomTreeWidget._create_color_icon
- CustomTreeWidget.create_item
- CustomTreeWidget.select_block_by_index
- CustomTreeWidget.show_context_menu
- CustomTreeWidget._revert_blocks_to_original
- CustomTreeWidget._handle_item_changed
- CustomTreeWidget._create_folder_at_cursor
- CustomTreeWidget._rename_folder
- CustomTreeWidget._rename_folder_by_id
- CustomTreeWidget._delete_folder_by_id
- CustomTreeWidget._create_subfolder_by_id
- CustomTreeWidget._delete_folder
- CustomTreeWidget._create_subfolder
- CustomTreeWidget.startDrag
- CustomTreeWidget.dragMoveEvent
- CustomTreeWidget.dragLeaveEvent
- CustomTreeWidget.paintEvent
- CustomTreeWidget.dropEvent
- CustomTreeWidget.sync_tree_to_project_manager
- CustomTreeWidget._handle_item_state_changed
- CustomTreeWidget._get_next_unnamed_name
- CustomTreeWidget.move_current_item_up
- CustomTreeWidget.move_current_item_down
- CustomTreeWidget.event
- CustomTreeWidget.viewportEvent
- CustomTreeWidget._reveal_in_explorer
- CustomTreeWidget._open_explorer_at_path
- CustomTreeWidget._open_spellcheck_for_block

### Файл: components\dictionary_manager_dialog.py
- DownloadThread.__init__
- DownloadThread.run
- DictionaryManagerDialog.__init__
- DictionaryManagerDialog._get_lang_name
- DictionaryManagerDialog.load_dictionaries
- DictionaryManagerDialog.refresh_list
- DictionaryManagerDialog.update_button_state
- DictionaryManagerDialog.download_selected
- DictionaryManagerDialog.on_download_progress
- DictionaryManagerDialog.on_download_finished

### Файл: components\editor\highlight_interface.py
- LNETHighlightInterface.__init__
- LNETHighlightInterface._momentary_highlight_tag
- LNETHighlightInterface._apply_all_extra_selections
- LNETHighlightInterface.addCriticalProblemHighlight
- LNETHighlightInterface.removeCriticalProblemHighlight
- LNETHighlightInterface.clearCriticalProblemHighlights
- LNETHighlightInterface.hasCriticalProblemHighlight
- LNETHighlightInterface.addWarningLineHighlight
- LNETHighlightInterface.removeWarningLineHighlight
- LNETHighlightInterface.clearWarningLineHighlights
- LNETHighlightInterface.hasWarningLineHighlight
- LNETHighlightInterface.addWidthExceededHighlight
- LNETHighlightInterface.removeWidthExceededHighlight
- LNETHighlightInterface.clearWidthExceededHighlights
- LNETHighlightInterface.hasWidthExceededHighlight
- LNETHighlightInterface.addShortLineHighlight
- LNETHighlightInterface.removeShortLineHighlight
- LNETHighlightInterface.clearShortLineHighlights
- LNETHighlightInterface.hasShortLineHighlight
- LNETHighlightInterface.addEmptyOddSublineHighlight
- LNETHighlightInterface.removeEmptyOddSublineHighlight
- LNETHighlightInterface.clearEmptyOddSublineHighlights
- LNETHighlightInterface.hasEmptyOddSublineHighlight
- LNETHighlightInterface.setPreviewSelectedLineHighlight
- LNETHighlightInterface.clearPreviewSelectedLineHighlight
- LNETHighlightInterface.setLinkedCursorPosition
- LNETHighlightInterface.applyQueuedHighlights
- LNETHighlightInterface.clearAllProblemTypeHighlights
- LNETHighlightInterface.addProblemLineHighlight
- LNETHighlightInterface.removeProblemLineHighlight
- LNETHighlightInterface.clearProblemLineHighlights
- LNETHighlightInterface.hasProblemHighlight

### Файл: components\editor\line_number_area.py
- LineNumberArea.__init__
- LineNumberArea.sizeHint
- LineNumberArea.paintEvent
- LineNumberArea.mousePressEvent
- LineNumberArea.mouseMoveEvent
- LineNumberArea.leaveEvent

### Файл: components\editor\line_number_area_paint_logic.py
- LNETLineNumberAreaPaintLogic.__init__
- LNETLineNumberAreaPaintLogic.execute_paint_event

### Файл: components\editor\line_numbered_text_edit.py
- LineNumberedTextEdit.__init__
- LineNumberedTextEdit.handle_line_number_click
- LineNumberedTextEdit.set_glossary_manager
- LineNumberedTextEdit._replace_word_at_cursor
- LineNumberedTextEdit._open_spellcheck_dialog_for_selection
- LineNumberedTextEdit._apply_corrected_text_to_editor
- LineNumberedTextEdit.mouseMoveEvent
- LineNumberedTextEdit.setPlainText
- LineNumberedTextEdit.reset_selection_state
- LineNumberedTextEdit.handle_line_number_area_mouse_move
- LineNumberedTextEdit.get_selected_lines
- LineNumberedTextEdit.set_selected_lines
- LineNumberedTextEdit.clear_selection
- LineNumberedTextEdit._update_selection_highlight
- LineNumberedTextEdit._emit_selection_changed
- LineNumberedTextEdit.leaveEvent
- LineNumberedTextEdit._find_glossary_entry_at
- LineNumberedTextEdit._find_warning_tooltip_at
- LineNumberedTextEdit._set_theme_colors
- LineNumberedTextEdit._create_tag_button
- LineNumberedTextEdit.populateContextMenu
- LineNumberedTextEdit._update_auxiliary_widths
- LineNumberedTextEdit.setFont
- LineNumberedTextEdit.wheelEvent
- LineNumberedTextEdit.keyPressEvent
- LineNumberedTextEdit.setReadOnly
- LineNumberedTextEdit.lineNumberAreaWidth
- LineNumberedTextEdit.updateLineNumberAreaWidth
- LineNumberedTextEdit.updateLineNumberArea
- LineNumberedTextEdit.resizeEvent
- LineNumberedTextEdit.paintEvent
- LineNumberedTextEdit.lineNumberAreaPaintEvent
- LineNumberedTextEdit.mousePressEvent
- LineNumberedTextEdit.super_mousePressEvent
- LineNumberedTextEdit.mouseReleaseEvent
- LineNumberedTextEdit.super_mouseReleaseEvent
- LineNumberedTextEdit._get_icon_sequences
- LineNumberedTextEdit._find_icon_sequence_in_block
- LineNumberedTextEdit._snap_cursor_out_of_icon_sequences
- LineNumberedTextEdit._momentary_highlight_tag
- LineNumberedTextEdit._apply_all_extra_selections
- LineNumberedTextEdit.addCriticalProblemHighlight
- LineNumberedTextEdit.removeCriticalProblemHighlight
- LineNumberedTextEdit.clearCriticalProblemHighlights
- LineNumberedTextEdit.hasCriticalProblemHighlight
- LineNumberedTextEdit.addWarningLineHighlight
- LineNumberedTextEdit.removeWarningLineHighlight
- LineNumberedTextEdit.clearWarningLineHighlights
- LineNumberedTextEdit.hasWarningLineHighlight
- LineNumberedTextEdit.addWidthExceededHighlight
- LineNumberedTextEdit.removeWidthExceededHighlight
- LineNumberedTextEdit.clearWidthExceededHighlights
- LineNumberedTextEdit.hasWidthExceededHighlight
- LineNumberedTextEdit.addShortLineHighlight
- LineNumberedTextEdit.removeShortLineHighlight
- LineNumberedTextEdit.clearShortLineHighlights
- LineNumberedTextEdit.hasShortLineHighlight
- LineNumberedTextEdit.addEmptyOddSublineHighlight
- LineNumberedTextEdit.removeEmptyOddSublineHighlight
- LineNumberedTextEdit.clearEmptyOddSublineHighlights
- LineNumberedTextEdit.hasEmptyOddSublineHighlight
- LineNumberedTextEdit.clearPreviewSelectedLineHighlight
- LineNumberedTextEdit.setLinkedCursorPosition
- LineNumberedTextEdit.applyQueuedHighlights
- LineNumberedTextEdit.clearAllProblemTypeHighlights
- LineNumberedTextEdit.addProblemLineHighlight
- LineNumberedTextEdit.removeProblemLineHighlight
- LineNumberedTextEdit.clearProblemLineHighlights
- LineNumberedTextEdit.hasProblemHighlight
- LineNumberedTextEdit.handle_mass_set_font
- LineNumberedTextEdit.handle_mass_set_width

### Файл: components\editor\lnet_context_menu_logic.py
- LNETContextMenuLogic.__init__
- LNETContextMenuLogic.populate

### Файл: components\editor\lnet_dialogs.py
- MassFontDialog.__init__
- MassFontDialog.populate_fonts
- MassFontDialog.get_selected_font
- MassWidthDialog.__init__
- MassWidthDialog.get_width
- MassWidthDialog.set_default_width

### Файл: components\editor\lnet_editor_setup.py
- set_theme_colors
- create_tag_button
- update_auxiliary_widths

### Файл: components\editor\lnet_highlight_wrappers.py
- LNETHighlightWrappers.__init__
- LNETHighlightWrappers.addCriticalProblemHighlight
- LNETHighlightWrappers.removeCriticalProblemHighlight
- LNETHighlightWrappers.clearCriticalProblemHighlights
- LNETHighlightWrappers.hasCriticalProblemHighlight
- LNETHighlightWrappers.addWarningLineHighlight
- LNETHighlightWrappers.removeWarningLineHighlight
- LNETHighlightWrappers.clearWarningLineHighlights
- LNETHighlightWrappers.hasWarningLineHighlight
- LNETHighlightWrappers.addWidthExceededHighlight
- LNETHighlightWrappers.removeWidthExceededHighlight
- LNETHighlightWrappers.clearWidthExceededHighlights
- LNETHighlightWrappers.hasWidthExceededHighlight
- LNETHighlightWrappers.addShortLineHighlight
- LNETHighlightWrappers.removeShortLineHighlight
- LNETHighlightWrappers.clearShortLineHighlights
- LNETHighlightWrappers.hasShortLineHighlight
- LNETHighlightWrappers.addEmptyOddSublineHighlight
- LNETHighlightWrappers.removeEmptyOddSublineHighlight
- LNETHighlightWrappers.clearEmptyOddSublineHighlights
- LNETHighlightWrappers.hasEmptyOddSublineHighlight

### Файл: components\editor\lnet_keyboard_handler.py
- LNETKeyboardHandler.__init__
- LNETKeyboardHandler.handle_key_press

### Файл: components\editor\lnet_spellcheck_logic.py
- LNETSpellcheckLogic.__init__
- LNETSpellcheckLogic.open_dialog_for_selection
- LNETSpellcheckLogic.apply_corrected_text

### Файл: components\editor\lnet_tag_helpers.py
- LNETTagHelpers.__init__
- LNETTagHelpers.find_icon_sequence_in_block
- LNETTagHelpers.snap_cursor_out_of_icon_sequences

### Файл: components\editor\lnet_tooltips.py
- LNETTooltipLogic.__init__
- LNETTooltipLogic.find_warning_tooltip_at

### Файл: components\editor\mouse_handlers.py
- LNETMouseHandlers.__init__
- LNETMouseHandlers._get_icon_sequences
- LNETMouseHandlers._find_icon_sequence_hit
- LNETMouseHandlers._move_cursor_to_icon_sequence_end
- LNETMouseHandlers._wrap_selection_with_color
- LNETMouseHandlers.insert_single_tag
- LNETMouseHandlers.wrap_selection_with_custom_tags
- LNETMouseHandlers.copy_tag_to_clipboard
- LNETMouseHandlers.get_tag_at_cursor
- LNETMouseHandlers.showContextMenu
- LNETMouseHandlers.mouseReleaseEvent
- LNETMouseHandlers.handle_line_number_click
- LNETMouseHandlers.handle_line_number_area_mouse_move
- LNETMouseHandlers._get_line_index_from_y
- LNETMouseHandlers.mousePressEvent

### Файл: components\editor\paint_event_logic.py
- LNETPaintEventLogic.__init__
- LNETPaintEventLogic.execute_paint_event

### Файл: components\editor\paint_handlers.py
- LNETPaintHandlers.__init__
- LNETPaintHandlers.paintEvent
- LNETPaintHandlers.lineNumberAreaPaintEvent

### Файл: components\editor\paint_helpers.py
- LNETPaintHelpers.__init__
- LNETPaintHelpers._map_no_tag_index_to_raw_text_index

### Файл: components\editor\text_highlight_manager.py
- TextHighlightManager.__init__
- TextHighlightManager._create_block_background_selection
- TextHighlightManager._create_search_match_selection
- TextHighlightManager.applyHighlights
- TextHighlightManager.updateCurrentLineHighlight
- TextHighlightManager.clearCurrentLineHighlight
- TextHighlightManager.setLinkedCursorPosition
- TextHighlightManager.clearLinkedCursorPosition
- TextHighlightManager.setPreviewSelectedLineHighlight
- TextHighlightManager.set_background_for_lines
- TextHighlightManager.clearPreviewSelectedLineHighlight
- TextHighlightManager.setCategorizedLineHighlights
- TextHighlightManager.clearCategorizedLineHighlights
- TextHighlightManager.addProblemLineHighlight
- TextHighlightManager.addCriticalProblemHighlight
- TextHighlightManager.removeCriticalProblemHighlight
- TextHighlightManager.clearCriticalProblemHighlights
- TextHighlightManager.hasCriticalProblemHighlight
- TextHighlightManager.addWarningLineHighlight
- TextHighlightManager.removeWarningLineHighlight
- TextHighlightManager.clearWarningLineHighlights
- TextHighlightManager.hasWarningLineHighlight
- TextHighlightManager.momentaryHighlightTag
- TextHighlightManager.clearTagInteractionHighlight
- TextHighlightManager.add_search_match_highlight
- TextHighlightManager.clear_search_match_highlights
- TextHighlightManager.add_width_exceed_char_highlight
- TextHighlightManager.clear_width_exceed_char_highlights
- TextHighlightManager.addEmptyOddSublineHighlight
- TextHighlightManager.removeEmptyOddSublineHighlight
- TextHighlightManager.clearEmptyOddSublineHighlights
- TextHighlightManager.hasEmptyOddSublineHighlight
- TextHighlightManager.clearAllProblemHighlights
- TextHighlightManager.clearAllHighlights
- TextHighlightManager.update_zebra_stripes

### Файл: components\folder_delete_dialog.py
- FolderDeleteDialog.__init__
- FolderDeleteDialog._setup_ui
- FolderDeleteDialog._on_keep_clicked
- FolderDeleteDialog._on_delete_all_clicked

### Файл: components\glossary_dialog.py
- _RichTextItemDelegate.paint
- _RichTextItemDelegate.sizeHint
- GlossaryDialog.__init__
- GlossaryDialog._populate_entries
- GlossaryDialog._select_initial_term
- GlossaryDialog._show_entry_for_row
- GlossaryDialog._on_entry_current_changed
- GlossaryDialog._on_entry_selected
- GlossaryDialog._on_entry_edited
- GlossaryDialog._activate_selected_occurrence
- GlossaryDialog._set_notes_variation_busy
- GlossaryDialog.apply_notes_variation
- GlossaryDialog._on_notes_variation_clicked
- GlossaryDialog._on_editor_content_changed
- GlossaryDialog._mark_editor_dirty
- GlossaryDialog._update_editor_enabled_state
- GlossaryDialog._save_editor_changes
- GlossaryDialog._attempt_entry_update
- GlossaryDialog._attempt_entry_delete
- GlossaryDialog._on_entry_context_menu
- GlossaryDialog._load_dialog_state
- GlossaryDialog._save_dialog_state
- GlossaryDialog._read_settings_file
- GlossaryDialog._write_settings_file
- GlossaryDialog._geometry_to_dict
- GlossaryDialog.showEvent
- GlossaryDialog.closeEvent
- GlossaryDialog._update_occurrences
- GlossaryDialog._entry_for_row
- GlossaryDialog._populate_entry_details
- GlossaryDialog._clear_entry_details
- GlossaryDialog._apply_filter

### Файл: components\glossary_edit_dialog.py
- ReturnToAcceptFilter.__init__
- ReturnToAcceptFilter.eventFilter
- GlossaryEditDialog.__init__
- GlossaryEditDialog.set_values
- GlossaryEditDialog.get_values
- GlossaryEditDialog.set_ai_busy

### Файл: components\glossary_translation_update_dialog.py
- GlossaryTranslationUpdateDialog.__init__
- GlossaryTranslationUpdateDialog._build_ui
- GlossaryTranslationUpdateDialog._populate_occurrences
- GlossaryTranslationUpdateDialog._format_occurrence_label
- GlossaryTranslationUpdateDialog._refresh_occurrence_item
- GlossaryTranslationUpdateDialog._load_occurrence
- GlossaryTranslationUpdateDialog._current_occurrence
- GlossaryTranslationUpdateDialog._suggest_translation
- GlossaryTranslationUpdateDialog._apply_current
- GlossaryTranslationUpdateDialog._update_text_highlights
- GlossaryTranslationUpdateDialog._skip_current
- GlossaryTranslationUpdateDialog._select_next
- GlossaryTranslationUpdateDialog._run_ai_for_current
- GlossaryTranslationUpdateDialog._run_ai_for_all
- GlossaryTranslationUpdateDialog.set_ai_busy
- GlossaryTranslationUpdateDialog.set_batch_active
- GlossaryTranslationUpdateDialog.on_ai_result
- GlossaryTranslationUpdateDialog.on_ai_error

### Файл: components\help_dialog.py
- HelpShortcutsDialog.__init__
- show_shortcuts_dialog

### Файл: components\labeled_spinbox.py
- LabeledSpinBox.__init__
- LabeledSpinBox.value
- LabeledSpinBox.setValue

### Файл: components\original_text_analysis_dialog.py
- _BarItem.__init__
- _AnalysisBarView.__init__
- _AnalysisBarView.wheelEvent
- _AnalysisBarView.mousePressEvent
- _AnalysisBarView.mouseMoveEvent
- _AnalysisBarView.mouseReleaseEvent
- _AnalysisBarView._scroll
- _AnalysisBarView.resizeEvent
- _AnalysisBarView.set_entries
- _AnalysisBarView.highlight_bar
- _AnalysisBarView._fit_view_to_scene
- OriginalTextAnalysisDialog.__init__
- OriginalTextAnalysisDialog.show_entries
- OriginalTextAnalysisDialog._apply_font
- OriginalTextAnalysisDialog._render_entries
- OriginalTextAnalysisDialog._handle_bar_selected
- OriginalTextAnalysisDialog._handle_table_selection
- OriginalTextAnalysisDialog._handle_table_double_click
- OriginalTextAnalysisDialog._on_font_changed

### Файл: components\project_dialogs.py
- NewProjectDialog.__init__
- NewProjectDialog._setup_ui
- NewProjectDialog._populate_plugins
- NewProjectDialog._scan_plugins
- NewProjectDialog._on_mode_changed
- NewProjectDialog._on_auto_create_toggled
- NewProjectDialog._get_start_dir
- NewProjectDialog._update_last_dir
- NewProjectDialog._browse_directory
- NewProjectDialog._browse_source
- NewProjectDialog._browse_translation
- NewProjectDialog._validate_and_accept
- NewProjectDialog.get_project_info
- OpenProjectDialog.__init__
- OpenProjectDialog._setup_ui
- OpenProjectDialog._browse_file
- OpenProjectDialog._validate_and_accept
- OpenProjectDialog.get_project_path
- ImportBlockDialog.__init__
- ImportBlockDialog._setup_ui
- ImportBlockDialog._browse_source_file
- ImportBlockDialog._browse_translation_file
- ImportBlockDialog._on_source_file_selected
- ImportBlockDialog._validate_and_accept
- ImportBlockDialog.get_block_info
- MoveToFolderDialog.__init__
- MoveToFolderDialog._setup_ui
- MoveToFolderDialog._populate_tree
- MoveToFolderDialog._add_folders_recursive
- MoveToFolderDialog._create_new_folder
- MoveToFolderDialog._select_by_id
- MoveToFolderDialog._validate_and_accept
- MoveToFolderDialog.get_selected_folder_id

### Файл: components\prompt_editor_dialog.py
- PromptEditorDialog.__init__
- PromptEditorDialog.get_text

### Файл: components\search_panel.py
- SearchPanelWidget.__init__
- SearchPanelWidget._on_find_next_from_combobox_activation
- SearchPanelWidget._add_to_history
- SearchPanelWidget._update_combobox_items
- SearchPanelWidget.load_history
- SearchPanelWidget.get_history
- SearchPanelWidget._on_find_next
- SearchPanelWidget._on_find_previous
- SearchPanelWidget.get_search_parameters
- SearchPanelWidget.set_search_options
- SearchPanelWidget.set_status_message
- SearchPanelWidget.focus_search_input
- SearchPanelWidget.clear_status
- SearchPanelWidget.get_query
- SearchPanelWidget.set_query

### Файл: components\session_bootstrap_dialog.py
- SessionBootstrapDialog.__init__
- SessionBootstrapDialog.get_instructions

### Файл: components\translation_variations_dialog.py
- TranslationVariationsDialog.__init__
- TranslationVariationsDialog._populate_variations
- TranslationVariationsDialog._update_preview
- TranslationVariationsDialog._apply_current_selection

### Файл: core\context.py
- UIProvider.statusBar
- UIProvider.force_focus
- UIProvider.preview_text_edit
- UIProvider.original_text_edit
- UIProvider.edited_text_edit
- UIProvider.block_list_widget
- ProjectContext.project_manager
- ProjectContext.settings_manager
- ProjectContext.state
- ProjectContext.data_processor
- ProjectContext.ui_updater
- ProjectContext.ui_provider
- ProjectContext.data
- ProjectContext.edited_file_data
- ProjectContext.edited_data
- ProjectContext.current_block_idx
- ProjectContext.current_string_idx
- ProjectContext.current_game_rules
- ProjectContext.unsaved_changes
- ProjectContext.unsaved_changes
- ProjectContext.update_title

### Файл: core\data_manager.py
- load_json_file
- save_json_file
- load_text_file
- save_text_file

### Файл: core\data_state_processor.py
- DataStateProcessor.__init__
- DataStateProcessor._get_string_from_source
- DataStateProcessor.get_current_string_text
- DataStateProcessor.get_block_texts
- DataStateProcessor.update_edited_data
- DataStateProcessor.revert_strings_to_original
- DataStateProcessor.perform_revert_strings
- DataStateProcessor.revert_blocks_to_original
- DataStateProcessor.save_current_edits
- DataStateProcessor.revert_edited_file_to_original

### Файл: core\data_store.py
- AppDataStore.clear
- AppDataStore.mark_dirty
- AppDataStore.mark_clean

### Файл: core\glossary_manager.py
- GlossaryEntry.is_valid
- GlossaryManager.__init__
- GlossaryManager.normalize_term
- GlossaryManager.load_from_text
- GlossaryManager.refresh_from_disk
- GlossaryManager.get_raw_text
- GlossaryManager.get_entries
- GlossaryManager.get_entry
- GlossaryManager.get_entries_sorted_by_length
- GlossaryManager.get_compiled_pattern
- GlossaryManager.iter_compiled
- GlossaryManager.find_matches
- GlossaryManager.build_occurrence_index
- GlossaryManager.get_occurrences_for
- GlossaryManager.get_occurrence_map
- GlossaryManager.get_relevant_terms
- GlossaryManager.get_session_changes
- GlossaryManager.clear_session_changes
- GlossaryManager.add_entry
- GlossaryManager.update_entry
- GlossaryManager.delete_entry
- GlossaryManager.save_to_disk
- GlossaryManager._parse_markdown
- GlossaryManager._table_lines
- GlossaryManager._generate_markdown
- GlossaryManager._persist
- GlossaryManager._build_pattern_cache
- GlossaryManager._build_regex

### Файл: core\project_manager.py
- ProjectManager.__init__
- ProjectManager.create_new_project
- ProjectManager.load
- ProjectManager.save
- ProjectManager.add_block
- ProjectManager.sync_project_files
- ProjectManager.import_directory
- ProjectManager.get_uncategorized_lines
- ProjectManager.get_absolute_path
- ProjectManager.get_relative_path
- ProjectManager.save_settings_to_project
- ProjectManager.load_settings_from_project
- ProjectManager.current_project
- ProjectManager._migrate_file_structure_to_virtual_folders
- ProjectManager.create_virtual_folder
- ProjectManager.move_strings_to_category
- ProjectManager.merge_folders
- ProjectManager.find_virtual_folder
- ProjectManager.is_descendant_of
- ProjectManager.move_folder_to_folder
- ProjectManager.move_block_to_folder
- ProjectManager._remove_block_id_from_any_folder
- ProjectManager.get_all_block_indices_under_folder
- ProjectManager._remove_folder_from_anywhere

### Файл: core\project_models.py
- Category.to_dict
- Category.from_dict
- Category.add_child
- Category.remove_child
- Category.find_category
- VirtualFolder.to_dict
- VirtualFolder.from_dict
- Block.to_dict
- Block.from_dict
- Block.add_category
- Block.remove_category
- Block.find_category
- Block.get_all_categories_flat
- Block._get_children_recursive
- Block.get_categorized_line_indices
- Project.to_dict
- Project.from_dict
- Project.add_block
- Project.remove_block
- Project.find_block
- Project.find_block_by_name

### Файл: core\settings\font_map_loader.py
- FontMapLoader.__init__
- FontMapLoader.load_all_font_maps
- FontMapLoader._parse_new_font_format
- FontMapLoader._load_font_overrides
- FontMapLoader._apply_font_overrides
- FontMapLoader.refresh_icon_highlighting
- FontMapLoader.update_icon_sequences_cache

### Файл: core\settings\global_settings.py
- GlobalSettings.__init__
- GlobalSettings._get_defaults
- GlobalSettings.load
- GlobalSettings.save

### Файл: core\settings\plugin_settings.py
- PluginSettings.__init__
- PluginSettings._get_plugin_config_path
- PluginSettings._substitute_env_vars
- PluginSettings.load
- PluginSettings._migrate_legacy_styles
- PluginSettings.save
- PluginSettings.save_block_names

### Файл: core\settings\recent_projects_manager.py
- RecentProjectsManager.__init__
- RecentProjectsManager.add_recent_project
- RecentProjectsManager.remove_recent_project
- RecentProjectsManager.clear_recent_projects

### Файл: core\settings\session_state_manager.py
- SessionStateManager.__init__
- SessionStateManager.load
- SessionStateManager.save
- SessionStateManager.get_state_for_file
- SessionStateManager.set_state_for_file
- SessionStateManager.cleanup_old_states

### Файл: core\settings_manager.py
- SettingsManager.__init__
- SettingsManager.get
- SettingsManager.set
- SettingsManager.load_settings
- SettingsManager.save_settings
- SettingsManager.load_unsaved_session
- SettingsManager.load_all_font_maps
- SettingsManager.add_recent_project
- SettingsManager.remove_recent_project
- SettingsManager.clear_recent_projects
- SettingsManager.save_block_names
- SettingsManager._update_icon_sequences_cache
- SettingsManager._refresh_icon_highlighting

### Файл: core\spellchecker_manager.py
- SpellcheckerManager.__init__
- SpellcheckerManager._initialize_spellchecker
- SpellcheckerManager.reload_dictionary
- SpellcheckerManager.set_enabled
- SpellcheckerManager.scan_local_dictionaries
- SpellcheckerManager._load_user_dictionary
- SpellcheckerManager.reload_glossary_words
- SpellcheckerManager._load_glossary_words
- SpellcheckerManager.add_to_custom_dictionary
- SpellcheckerManager.is_misspelled
- SpellcheckerManager.get_suggestions

### Файл: core\state_manager.py
- StateManager.__init__
- StateManager.enter
- StateManager.is_active
- StateManager.any_of
- StateManager.set_active
- StateManager.clear

### Файл: core\tag_utils.py
- apply_default_mappings_only

### Файл: core\translation\config.py
- merge_translation_config
- build_default_translation_config

### Файл: core\translation\providers.py
- BaseTranslationProvider.__init__
- BaseTranslationProvider.translate
- BaseTranslationProvider.translate_stream
- OpenAIChatProvider.__init__
- OpenAIChatProvider._prepare_body
- OpenAIChatProvider.translate
- OpenAIChatProvider.translate_stream
- OpenAIResponsesProvider.__init__
- OpenAIResponsesProvider.translate
- OllamaChatProvider.__init__
- OllamaChatProvider.translate
- OllamaChatProvider.translate_stream
- ChatMockProvider._prepare_body
- DeepLProvider.translate
- GeminiProvider.__init__
- GeminiProvider.start_new_chat_session
- GeminiProvider.translate
- GeminiProvider.translate_stream
- GeminiProvider._translate_via_openai_compat
- GeminiProvider._translate_via_native_api
- GeminiProvider._translate_via_native_stream
- create_translation_provider
- get_provider_for_config

### Файл: core\translation\session_manager.py
- TranslationSessionState.set_instructions
- TranslationSessionState.prepare_request
- TranslationSessionState.record_exchange
- TranslationSessionManager.__init__
- TranslationSessionManager.reset
- TranslationSessionManager.ensure_session
- TranslationSessionManager.get_state

### Файл: core\undo_manager.py
- UndoManager.__init__
- UndoManager.begin_group
- UndoManager.end_group
- UndoManager._is_word_char
- UndoManager.record_action
- UndoManager.get_project_snapshot
- UndoManager.record_structural_action
- UndoManager._apply_project_snapshot
- UndoManager.record_navigation
- UndoManager.undo
- UndoManager.redo
- UndoManager._get_item_location
- UndoManager._navigate_to
- UndoManager._apply_data
- UndoManager.clear

### Файл: dialogs\spellcheck_dialog.py
- SpellcheckDialog.__init__
- SpellcheckDialog.setup_ui
- SpellcheckDialog._process_text_spacing_and_line_numbers
- SpellcheckDialog._apply_zebra_striping
- SpellcheckDialog._load_content
- SpellcheckDialog.find_misspelled_words
- SpellcheckDialog._find_main_window
- SpellcheckDialog.pre_highlight_all_misspelled_words
- SpellcheckDialog.show_current_word
- SpellcheckDialog.go_to_previous_word
- SpellcheckDialog.go_to_next_word
- SpellcheckDialog.clear_current_word_highlight
- SpellcheckDialog.jump_to_word_from_list
- SpellcheckDialog.ignore_word
- SpellcheckDialog.ignore_all_word
- SpellcheckDialog.replace_word
- SpellcheckDialog.replace_with_suggestion
- SpellcheckDialog.add_to_dictionary
- SpellcheckDialog.get_corrected_text
- SpellcheckDialog._navigate_to_string_in_main_window
- SpellcheckDialog._on_list_double_click
- SpellcheckDialog._on_text_double_click

### Файл: font_tool\font_generator.py
- find_glyphs
- crop_black_vertical
- load_all_glyphs
- ocr_glyph
- save_glyph_bmp
- save_json
- update_info
- show_glyph
- save_current_glyph_to_json
- on_entry
- on_canvas_click
- go_prev
- go_next
- go_left
- go_right
- go_down
- go_up
- main

### Файл: gemini\ai_chat_dialog.py
- _ChatInputEventFilter.__init__
- _ChatInputEventFilter.eventFilter
- _ChatTab.__init__
- _ChatTab.populate_models
- AIChatDialog.__init__
- AIChatDialog._set_theme_styles
- AIChatDialog.eventFilter
- AIChatDialog.add_new_tab
- AIChatDialog.remove_tab
- AIChatDialog._emit_message_sent
- AIChatDialog.append_to_history
- AIChatDialog.set_input_enabled

### Файл: gemini\ai_chat_handler.py
- AIChatHandler.__init__
- AIChatHandler._get_available_providers
- AIChatHandler.show_chat_window
- AIChatHandler._add_new_chat_session
- AIChatHandler._handle_tab_closed
- AIChatHandler._handle_send_message
- AIChatHandler._process_annotations
- AIChatHandler._format_ai_response_for_display
- AIChatHandler._on_ai_chunk_received
- AIChatHandler._on_ai_stream_finished
- AIChatHandler._on_ai_chat_success
- AIChatHandler._on_ai_error
- AIChatHandler._cleanup_worker

### Файл: gemini\ai_prompt_composer.py
- AIPromptComposer.prepare_text_for_translation
- AIPromptComposer.restore_placeholders
- AIPromptComposer.compose_batch_request
- AIPromptComposer.compose_variation_request
- AIPromptComposer.compose_messages
- AIPromptComposer.compose_glossary_occurrence_update_request
- AIPromptComposer.compose_glossary_occurrence_batch_request
- AIPromptComposer.compose_glossary_request
- AIPromptComposer._glossary_entries_to_text
- AIPromptComposer._prepare_glossary_for_prompt

### Файл: gemini\ai_status_dialog.py
- AIStatusDialog.__init__
- AIStatusDialog.on_cancel
- AIStatusDialog.closeEvent
- AIStatusDialog.setup_progress_bar
- AIStatusDialog.update_progress
- AIStatusDialog.showEvent
- AIStatusDialog.hideEvent
- AIStatusDialog.start
- AIStatusDialog.finish
- AIStatusDialog._set_model_name
- AIStatusDialog.update_step
- AIStatusDialog._update_label_style

### Файл: gemini\ai_worker.py
- AIWorker.__init__
- AIWorker.cancel
- AIWorker._clean_json_response
- AIWorker.run

### Файл: gemini\app_action_handler.py
- AppActionHandler.__init__
- AppActionHandler._perform_issues_scan_for_block
- AppActionHandler._perform_initial_silent_scan_all_issues
- AppActionHandler.rescan_issues_for_single_block
- AppActionHandler.rescan_all_tags
- AppActionHandler.handle_close_event
- AppActionHandler._derive_edited_path
- AppActionHandler.open_file_dialog_action
- AppActionHandler.open_changes_file_dialog_action
- AppActionHandler.save_as_dialog_action
- AppActionHandler.load_all_data_for_path
- AppActionHandler.reload_original_data_action
- AppActionHandler.calculate_widths_for_block_action
- AppActionHandler.create_new_project_action
- AppActionHandler.open_project_action
- AppActionHandler.close_project_action
- AppActionHandler.import_block_action
- AppActionHandler._populate_blocks_from_project
- AppActionHandler.delete_block_action
- AppActionHandler.move_block_up_action
- AppActionHandler.move_block_down_action
- AppActionHandler._update_recent_projects_menu
- AppActionHandler._open_recent_project
- AppActionHandler._clear_recent_projects

### Файл: gemini\base_game_rules.py
- BaseGameRules.__init__
- BaseGameRules.load_data_from_json_obj
- BaseGameRules.save_data_to_json_obj
- BaseGameRules.get_enter_char
- BaseGameRules.get_shift_enter_char
- BaseGameRules.get_ctrl_enter_char
- BaseGameRules.convert_editor_text_to_data
- BaseGameRules.get_display_name
- BaseGameRules.get_problem_definitions
- BaseGameRules.analyze_subline
- BaseGameRules.autofix_data_string
- BaseGameRules.process_pasted_segment
- BaseGameRules.get_base_game_rules_class
- BaseGameRules.get_default_tag_mappings
- BaseGameRules.get_tag_checker_handler
- BaseGameRules.get_short_problem_name
- BaseGameRules.get_plugin_actions
- BaseGameRules.get_text_representation_for_editor
- BaseGameRules.get_text_representation_for_preview
- BaseGameRules.get_syntax_highlighting_rules
- BaseGameRules.get_legitimate_tags
- BaseGameRules.get_context_menu_actions
- BaseGameRules.calculate_string_width_override
- BaseGameRules.get_editor_page_size

### Файл: gemini\base_handler.py
- BaseHandler.__init__

### Файл: gemini\base_import_rules.py
- BaseImportRules.__init__
- BaseImportRules.parse_clipboard_text
- BaseImportRules.process_segment_for_insertion
- BaseImportRules.apply_mappings_to_text

### Файл: gemini\base_translation_handler.py
- BaseTranslationHandler.__init__

### Файл: gemini\base_ui_updater.py
- BaseUIUpdater.__init__

### Файл: gemini\block_list_updater.py
- BlockListUpdater.__init__
- BlockListUpdater.populate_blocks
- BlockListUpdater.update_block_item_text_with_problem_count
- BlockListUpdater.clear_all_problem_block_highlights_and_text

### Файл: gemini\cleanup_project.py
- git_commit
- delete_files
- move_files
- fix_imports
- main

### Файл: gemini\config.py
- merge_translation_config
- build_default_translation_config

### Файл: gemini\custom_list_item_delegate.py
- CustomListItemDelegate.__init__
- CustomListItemDelegate._get_current_number_area_width
- CustomListItemDelegate._get_problem_indicator_zone_width
- CustomListItemDelegate._get_color_marker_zone_width
- CustomListItemDelegate.sizeHint
- CustomListItemDelegate.paint

### Файл: gemini\custom_list_widget.py
- CustomListWidget.__init__
- CustomListWidget._create_color_icon
- CustomListWidget.create_item
- CustomListWidget.show_context_menu
- CustomListWidget._open_spellcheck_for_block

### Файл: gemini\data_manager.py
- load_json_file
- save_json_file
- load_text_file
- save_text_file

### Файл: gemini\data_state_processor.py
- DataStateProcessor.__init__
- DataStateProcessor._get_string_from_source
- DataStateProcessor.get_current_string_text
- DataStateProcessor.get_block_texts
- DataStateProcessor.update_edited_data
- DataStateProcessor.save_current_edits
- DataStateProcessor.revert_edited_file_to_original

### Файл: gemini\demo_project.py
- demo_scenario_1
- demo_scenario_2
- demo_scenario_3
- demo_uncategorized_handling
- main

### Файл: gemini\dictionary_manager_dialog.py
- DownloadThread.__init__
- DownloadThread.run
- DictionaryManagerDialog.__init__
- DictionaryManagerDialog._get_lang_name
- DictionaryManagerDialog.load_dictionaries
- DictionaryManagerDialog.refresh_list
- DictionaryManagerDialog.update_button_state
- DictionaryManagerDialog.download_selected
- DictionaryManagerDialog.on_download_progress
- DictionaryManagerDialog.on_download_finished
- DownloadThread.__init__
- DownloadThread.run
- DictionaryManagerDialog.__init__
- DictionaryManagerDialog._get_lang_name
- DictionaryManagerDialog.load_dictionaries
- DictionaryManagerDialog.refresh_list
- DictionaryManagerDialog.update_button_state
- DictionaryManagerDialog.download_selected
- DictionaryManagerDialog.on_download_progress
- DictionaryManagerDialog.on_download_finished

### Файл: gemini\glossary_builder_handler.py
- GlossaryBuilderHandler.__init__
- GlossaryBuilderHandler._load_prompts
- GlossaryBuilderHandler._split_text_into_chunks
- GlossaryBuilderHandler._mask_tags_for_ai
- GlossaryBuilderHandler._clean_json_response
- GlossaryBuilderHandler._resolve_translation_credentials
- GlossaryBuilderHandler.build_glossary_for_block
- GlossaryBuilderHandler._start_async_glossary_task
- GlossaryBuilderHandler._on_glossary_success
- GlossaryBuilderHandler._on_glossary_error
- GlossaryBuilderHandler._on_glossary_cancelled
- GlossaryBuilderHandler._cleanup_worker

### Файл: gemini\glossary_dialog.py
- _RichTextItemDelegate.paint
- _RichTextItemDelegate.sizeHint
- GlossaryDialog.__init__
- GlossaryDialog._populate_entries
- GlossaryDialog._select_initial_term
- GlossaryDialog._show_entry_for_row
- GlossaryDialog._on_entry_current_changed
- GlossaryDialog._on_entry_selected
- GlossaryDialog._on_entry_edited
- GlossaryDialog._activate_selected_occurrence
- GlossaryDialog._set_notes_variation_busy
- GlossaryDialog.apply_notes_variation
- GlossaryDialog._on_notes_variation_clicked
- GlossaryDialog._on_editor_content_changed
- GlossaryDialog._mark_editor_dirty
- GlossaryDialog._update_editor_enabled_state
- GlossaryDialog._save_editor_changes
- GlossaryDialog._attempt_entry_update
- GlossaryDialog._attempt_entry_delete
- GlossaryDialog._on_entry_context_menu
- GlossaryDialog._load_dialog_state
- GlossaryDialog._save_dialog_state
- GlossaryDialog._read_settings_file
- GlossaryDialog._write_settings_file
- GlossaryDialog._geometry_to_dict
- GlossaryDialog.showEvent
- GlossaryDialog.closeEvent
- GlossaryDialog._update_occurrences
- GlossaryDialog._entry_for_row
- GlossaryDialog._populate_entry_details
- GlossaryDialog._clear_entry_details
- GlossaryDialog._apply_filter

### Файл: gemini\glossary_handler.py
- _ReturnToAcceptFilter.__init__
- _ReturnToAcceptFilter.eventFilter
- _EditEntryDialog.__init__
- _EditEntryDialog.set_values
- _EditEntryDialog.get_values
- _EditEntryDialog.set_ai_busy
- GlossaryHandler.__init__
- GlossaryHandler.install_menu_actions
- GlossaryHandler.initialize_glossary_highlighting
- GlossaryHandler._on_glossary_dialog_closed
- GlossaryHandler.show_glossary_dialog
- GlossaryHandler.add_glossary_entry
- GlossaryHandler.edit_glossary_entry
- GlossaryHandler._create_edit_dialog
- GlossaryHandler._ai_fill_glossary_entry
- GlossaryHandler._set_notes_dialog_busy
- GlossaryHandler._start_glossary_notes_variation
- GlossaryHandler._handle_notes_variation_from_dialog
- GlossaryHandler._handle_ai_fill_success
- GlossaryHandler._handle_ai_fill_error
- GlossaryHandler.load_prompts
- GlossaryHandler._extract_glossary_prompt
- GlossaryHandler._extract_system_prompt
- GlossaryHandler._ensure_glossary_loaded
- GlossaryHandler._update_glossary_highlighting
- GlossaryHandler._get_glossary_prompt_template
- GlossaryHandler._get_original_string
- GlossaryHandler._get_original_block
- GlossaryHandler._resolve_selection_from_original
- GlossaryHandler._resolve_selection_from_preview
- GlossaryHandler._jump_to_occurrence
- GlossaryHandler._handle_glossary_entry_update
- GlossaryHandler._show_translation_update_dialog
- GlossaryHandler._on_translation_update_dialog_closed
- GlossaryHandler.save_prompt_section
- GlossaryHandler._get_occurrence_original_text
- GlossaryHandler._get_occurrence_translation_text
- GlossaryHandler._apply_occurrence_translation
- GlossaryHandler._request_ai_occurrence_update
- GlossaryHandler._start_ai_occurrence_batch
- GlossaryHandler._resume_ai_occurrence_batch
- GlossaryHandler._handle_occurrence_ai_result
- GlossaryHandler._handle_occurrence_batch_success
- GlossaryHandler._handle_occurrence_ai_error
- GlossaryHandler._handle_glossary_entry_delete
- _ReturnToAcceptFilter.__init__
- _ReturnToAcceptFilter.eventFilter
- _EditEntryDialog.__init__
- _EditEntryDialog.set_values
- _EditEntryDialog.get_values
- _EditEntryDialog.set_ai_busy
- GlossaryHandler.__init__
- GlossaryHandler.install_menu_actions
- GlossaryHandler.initialize_glossary_highlighting
- GlossaryHandler._on_glossary_dialog_closed
- GlossaryHandler.show_glossary_dialog
- GlossaryHandler.add_glossary_entry
- GlossaryHandler.edit_glossary_entry
- GlossaryHandler._create_edit_dialog
- GlossaryHandler._ai_fill_glossary_entry
- GlossaryHandler._set_notes_dialog_busy
- GlossaryHandler._start_glossary_notes_variation
- GlossaryHandler._handle_notes_variation_from_dialog
- GlossaryHandler._handle_ai_fill_success
- GlossaryHandler._handle_ai_fill_error
- GlossaryHandler.load_prompts
- GlossaryHandler._extract_glossary_prompt
- GlossaryHandler._extract_system_prompt
- GlossaryHandler._ensure_glossary_loaded
- GlossaryHandler._update_glossary_highlighting
- GlossaryHandler._get_glossary_prompt_template
- GlossaryHandler._get_original_string
- GlossaryHandler._get_original_block
- GlossaryHandler._resolve_selection_from_original
- GlossaryHandler._resolve_selection_from_preview
- GlossaryHandler._jump_to_occurrence
- GlossaryHandler._handle_glossary_entry_update
- GlossaryHandler._show_translation_update_dialog
- GlossaryHandler._on_translation_update_dialog_closed
- GlossaryHandler.save_prompt_section
- GlossaryHandler._get_occurrence_original_text
- GlossaryHandler._get_occurrence_translation_text
- GlossaryHandler._apply_occurrence_translation
- GlossaryHandler._request_ai_occurrence_update
- GlossaryHandler._start_ai_occurrence_batch
- GlossaryHandler._resume_ai_occurrence_batch
- GlossaryHandler._handle_occurrence_ai_result
- GlossaryHandler._handle_occurrence_batch_success
- GlossaryHandler._handle_occurrence_ai_error
- GlossaryHandler._handle_glossary_entry_delete

### Файл: gemini\glossary_manager.py
- GlossaryEntry.is_valid
- GlossaryManager.__init__
- GlossaryManager.normalize_term
- GlossaryManager.load_from_text
- GlossaryManager.refresh_from_disk
- GlossaryManager.get_raw_text
- GlossaryManager.get_entries
- GlossaryManager.get_entry
- GlossaryManager.get_entries_sorted_by_length
- GlossaryManager.get_compiled_pattern
- GlossaryManager.iter_compiled
- GlossaryManager.find_matches
- GlossaryManager.build_occurrence_index
- GlossaryManager.get_occurrences_for
- GlossaryManager.get_occurrence_map
- GlossaryManager.get_relevant_terms
- GlossaryManager.get_session_changes
- GlossaryManager.clear_session_changes
- GlossaryManager.add_entry
- GlossaryManager.update_entry
- GlossaryManager.delete_entry
- GlossaryManager.save_to_disk
- GlossaryManager._parse_markdown
- GlossaryManager._table_lines
- GlossaryManager._generate_markdown
- GlossaryManager._persist
- GlossaryManager._build_pattern_cache
- GlossaryManager._build_regex

### Файл: gemini\glossary_translation_update_dialog.py
- GlossaryTranslationUpdateDialog.__init__
- GlossaryTranslationUpdateDialog._build_ui
- GlossaryTranslationUpdateDialog._populate_occurrences
- GlossaryTranslationUpdateDialog._format_occurrence_label
- GlossaryTranslationUpdateDialog._refresh_occurrence_item
- GlossaryTranslationUpdateDialog._load_occurrence
- GlossaryTranslationUpdateDialog._current_occurrence
- GlossaryTranslationUpdateDialog._suggest_translation
- GlossaryTranslationUpdateDialog._apply_current
- GlossaryTranslationUpdateDialog._skip_current
- GlossaryTranslationUpdateDialog._select_next
- GlossaryTranslationUpdateDialog._run_ai_for_current
- GlossaryTranslationUpdateDialog._run_ai_for_all
- GlossaryTranslationUpdateDialog.set_ai_busy
- GlossaryTranslationUpdateDialog.set_batch_active
- GlossaryTranslationUpdateDialog.on_ai_result
- GlossaryTranslationUpdateDialog.on_ai_error

### Файл: gemini\highlight_interface.py
- LNETHighlightInterface.__init__
- LNETHighlightInterface._momentary_highlight_tag
- LNETHighlightInterface._apply_all_extra_selections
- LNETHighlightInterface.addCriticalProblemHighlight
- LNETHighlightInterface.removeCriticalProblemHighlight
- LNETHighlightInterface.clearCriticalProblemHighlights
- LNETHighlightInterface.hasCriticalProblemHighlight
- LNETHighlightInterface.addWarningLineHighlight
- LNETHighlightInterface.removeWarningLineHighlight
- LNETHighlightInterface.clearWarningLineHighlights
- LNETHighlightInterface.hasWarningLineHighlight
- LNETHighlightInterface.addWidthExceededHighlight
- LNETHighlightInterface.removeWidthExceededHighlight
- LNETHighlightInterface.clearWidthExceededHighlights
- LNETHighlightInterface.hasWidthExceededHighlight
- LNETHighlightInterface.addShortLineHighlight
- LNETHighlightInterface.removeShortLineHighlight
- LNETHighlightInterface.clearShortLineHighlights
- LNETHighlightInterface.hasShortLineHighlight
- LNETHighlightInterface.addEmptyOddSublineHighlight
- LNETHighlightInterface.removeEmptyOddSublineHighlight
- LNETHighlightInterface.clearEmptyOddSublineHighlights
- LNETHighlightInterface.hasEmptyOddSublineHighlight
- LNETHighlightInterface.setPreviewSelectedLineHighlight
- LNETHighlightInterface.clearPreviewSelectedLineHighlight
- LNETHighlightInterface.setLinkedCursorPosition
- LNETHighlightInterface.applyQueuedHighlights
- LNETHighlightInterface.clearAllProblemTypeHighlights
- LNETHighlightInterface.addProblemLineHighlight
- LNETHighlightInterface.removeProblemLineHighlight
- LNETHighlightInterface.clearProblemLineHighlights
- LNETHighlightInterface.hasProblemHighlight

### Файл: gemini\issue_scan_handler.py
- IssueScanHandler.__init__
- IssueScanHandler._perform_issues_scan_for_block
- IssueScanHandler._perform_initial_silent_scan_all_issues
- IssueScanHandler.rescan_issues_for_single_block
- IssueScanHandler.rescan_all_tags

### Файл: gemini\labeled_spinbox.py
- LabeledSpinBox.__init__
- LabeledSpinBox.value
- LabeledSpinBox.setValue

### Файл: gemini\line_number_area.py
- LineNumberArea.__init__
- LineNumberArea.sizeHint
- LineNumberArea.paintEvent
- LineNumberArea.mousePressEvent

### Файл: gemini\line_number_area_paint_logic.py
- LNETLineNumberAreaPaintLogic.__init__
- LNETLineNumberAreaPaintLogic.execute_paint_event

### Файл: gemini\line_numbered_text_edit.py
- LineNumberedTextEdit.__init__
- LineNumberedTextEdit.handle_line_number_click
- LineNumberedTextEdit.set_glossary_manager
- LineNumberedTextEdit._replace_word_at_cursor
- LineNumberedTextEdit._open_spellcheck_dialog_for_selection
- LineNumberedTextEdit._apply_corrected_text_to_editor
- LineNumberedTextEdit.mouseMoveEvent
- LineNumberedTextEdit.get_selected_lines
- LineNumberedTextEdit.set_selected_lines
- LineNumberedTextEdit.clear_selection
- LineNumberedTextEdit._update_selection_highlight
- LineNumberedTextEdit._emit_selection_changed
- LineNumberedTextEdit.leaveEvent
- LineNumberedTextEdit._find_glossary_entry_at
- LineNumberedTextEdit._set_theme_colors
- LineNumberedTextEdit._create_color_button
- LineNumberedTextEdit.populateContextMenu
- LineNumberedTextEdit._update_auxiliary_widths
- LineNumberedTextEdit.setFont
- LineNumberedTextEdit.keyPressEvent
- LineNumberedTextEdit.setReadOnly
- LineNumberedTextEdit.lineNumberAreaWidth
- LineNumberedTextEdit.updateLineNumberAreaWidth
- LineNumberedTextEdit.updateLineNumberArea
- LineNumberedTextEdit.resizeEvent
- LineNumberedTextEdit.paintEvent
- LineNumberedTextEdit.lineNumberAreaPaintEvent
- LineNumberedTextEdit.mousePressEvent
- LineNumberedTextEdit.super_mousePressEvent
- LineNumberedTextEdit.mouseReleaseEvent
- LineNumberedTextEdit.super_mouseReleaseEvent
- LineNumberedTextEdit._get_icon_sequences
- LineNumberedTextEdit._find_icon_sequence_in_block
- LineNumberedTextEdit._snap_cursor_out_of_icon_sequences
- LineNumberedTextEdit._momentary_highlight_tag
- LineNumberedTextEdit._apply_all_extra_selections
- LineNumberedTextEdit.addCriticalProblemHighlight
- LineNumberedTextEdit.removeCriticalProblemHighlight
- LineNumberedTextEdit.clearCriticalProblemHighlights
- LineNumberedTextEdit.hasCriticalProblemHighlight
- LineNumberedTextEdit.addWarningLineHighlight
- LineNumberedTextEdit.removeWarningLineHighlight
- LineNumberedTextEdit.clearWarningLineHighlights
- LineNumberedTextEdit.hasWarningLineHighlight
- LineNumberedTextEdit.addWidthExceededHighlight
- LineNumberedTextEdit.removeWidthExceededHighlight
- LineNumberedTextEdit.clearWidthExceededHighlights
- LineNumberedTextEdit.hasWidthExceededHighlight
- LineNumberedTextEdit.addShortLineHighlight
- LineNumberedTextEdit.removeShortLineHighlight
- LineNumberedTextEdit.clearShortLineHighlights
- LineNumberedTextEdit.hasShortLineHighlight
- LineNumberedTextEdit.addEmptyOddSublineHighlight
- LineNumberedTextEdit.removeEmptyOddSublineHighlight
- LineNumberedTextEdit.clearEmptyOddSublineHighlights
- LineNumberedTextEdit.hasEmptyOddSublineHighlight
- LineNumberedTextEdit.clearPreviewSelectedLineHighlight
- LineNumberedTextEdit.setLinkedCursorPosition
- LineNumberedTextEdit.applyQueuedHighlights
- LineNumberedTextEdit.clearAllProblemTypeHighlights
- LineNumberedTextEdit.addProblemLineHighlight
- LineNumberedTextEdit.removeProblemLineHighlight
- LineNumberedTextEdit.clearProblemLineHighlights
- LineNumberedTextEdit.hasProblemHighlight
- LineNumberedTextEdit.handle_mass_set_font
- LineNumberedTextEdit.handle_mass_set_width
- MassFontDialog.__init__
- MassFontDialog.populate_fonts
- MassFontDialog.get_selected_font
- MassWidthDialog.__init__
- MassWidthDialog.get_width
- MassWidthDialog.set_default_width

### Файл: gemini\list_selection_handler.py
- ListSelectionHandler.__init__
- ListSelectionHandler.block_selected
- ListSelectionHandler._restore_block_selection
- ListSelectionHandler._update_block_toolbar_button_states
- ListSelectionHandler.string_selected_from_preview
- ListSelectionHandler.rename_block
- ListSelectionHandler._data_string_has_any_problem
- ListSelectionHandler.navigate_to_problem_string
- ListSelectionHandler.handle_preview_selection_changed

### Файл: gemini\logging_utils.py
- DuplicateFilter.__init__
- DuplicateFilter.filter
- log_debug
- log_info
- log_warning
- log_error

### Файл: gemini\main.py
- MainWindow.__init__
- MainWindow.force_focus
- MainWindow.setup_plugin_ui
- MainWindow.load_game_plugin
- MainWindow.get_block_color_markers
- MainWindow.toggle_block_color_marker
- MainWindow._rebuild_unsaved_block_indices
- MainWindow.keyPressEvent
- MainWindow.execute_find_next_shortcut
- MainWindow.execute_find_previous_shortcut
- MainWindow.trigger_check_tags_action
- MainWindow.handle_edited_cursor_position_changed
- MainWindow.handle_edited_selection_changed
- MainWindow.connect_signals
- MainWindow.apply_font_size
- MainWindow.handle_panel_find_next
- MainWindow.handle_panel_find_previous
- MainWindow.toggle_search_panel
- MainWindow.hide_search_panel
- MainWindow.current_font_size
- MainWindow.current_font_size
- MainWindow.active_game_plugin
- MainWindow.active_game_plugin
- MainWindow.show_multiple_spaces_as_dots
- MainWindow.show_multiple_spaces_as_dots
- MainWindow.theme
- MainWindow.theme
- MainWindow.restore_unsaved_on_startup
- MainWindow.restore_unsaved_on_startup
- MainWindow.game_dialog_max_width_pixels
- MainWindow.game_dialog_max_width_pixels
- MainWindow.line_width_warning_threshold_pixels
- MainWindow.line_width_warning_threshold_pixels
- MainWindow.load_all_data_for_path
- MainWindow._apply_text_wrap_settings
- MainWindow._reconfigure_all_highlighters
- MainWindow.closeEvent
- MainWindow.build_glossary_with_ai

### Файл: gemini\main_window_actions.py
- MainWindowActions.__init__
- MainWindowActions.open_settings_dialog
- MainWindowActions.trigger_save_action
- MainWindowActions.trigger_revert_action
- MainWindowActions.trigger_undo_paste_action
- MainWindowActions.trigger_reload_tag_mappings
- MainWindowActions.handle_add_tag_mapping_request

### Файл: gemini\main_window_block_handler.py
- MainWindowBlockHandler.__init__
- MainWindowBlockHandler.get_block_color_markers
- MainWindowBlockHandler.toggle_block_color_marker
- MainWindowBlockHandler.rebuild_unsaved_block_indices

### Файл: gemini\main_window_event_handler.py
- MainWindowEventHandler.__init__
- MainWindowEventHandler.connect_signals
- MainWindowEventHandler.keyPressEvent
- MainWindowEventHandler.closeEvent
- MainWindowEventHandler.handle_edited_cursor_position_changed
- MainWindowEventHandler.handle_edited_selection_changed

### Файл: gemini\main_window_helper.py
- MainWindowHelper.__init__
- MainWindowHelper.get_font_map_for_string
- MainWindowHelper.restart_application
- MainWindowHelper.rebuild_unsaved_block_indices
- MainWindowHelper.execute_find_next_shortcut
- MainWindowHelper.execute_find_previous_shortcut
- MainWindowHelper.handle_panel_find_next
- MainWindowHelper.handle_panel_find_previous
- MainWindowHelper.toggle_search_panel
- MainWindowHelper.hide_search_panel
- MainWindowHelper.load_all_data_for_path
- MainWindowHelper.apply_text_wrap_settings
- MainWindowHelper.reconfigure_all_highlighters
- MainWindowHelper.prepare_to_close
- MainWindowHelper.restore_state_after_settings_load

### Файл: gemini\main_window_plugin_handler.py
- MainWindowPluginHandler.__init__
- MainWindowPluginHandler.setup_plugin_ui
- MainWindowPluginHandler.load_game_plugin
- MainWindowPluginHandler._load_fallback_rules
- MainWindowPluginHandler.trigger_check_tags_action

### Файл: gemini\main_window_ui_handler.py
- MainWindowUIHandler.__init__
- MainWindowUIHandler.update_editor_rules_properties
- MainWindowUIHandler.apply_font_size
- MainWindowUIHandler.apply_text_wrap_settings
- MainWindowUIHandler.reconfigure_all_highlighters
- MainWindowUIHandler.force_focus
- MainWindowUIHandler.apply_theme

### Файл: gemini\mouse_handlers.py
- LNETMouseHandlers.__init__
- LNETMouseHandlers._get_icon_sequences
- LNETMouseHandlers._find_icon_sequence_hit
- LNETMouseHandlers._move_cursor_to_icon_sequence_end
- LNETMouseHandlers._wrap_selection_with_color
- LNETMouseHandlers.copy_tag_to_clipboard
- LNETMouseHandlers.get_tag_at_cursor
- LNETMouseHandlers.showContextMenu
- LNETMouseHandlers.mouseReleaseEvent
- LNETMouseHandlers.mousePressEvent

### Файл: gemini\original_text_analysis_dialog.py
- _BarItem.__init__
- _AnalysisBarView.__init__
- _AnalysisBarView.wheelEvent
- _AnalysisBarView.mousePressEvent
- _AnalysisBarView.mouseMoveEvent
- _AnalysisBarView.mouseReleaseEvent
- _AnalysisBarView._scroll
- _AnalysisBarView.resizeEvent
- _AnalysisBarView.set_entries
- _AnalysisBarView.highlight_bar
- _AnalysisBarView._fit_view_to_scene
- OriginalTextAnalysisDialog.__init__
- OriginalTextAnalysisDialog.show_entries
- OriginalTextAnalysisDialog._apply_font
- OriginalTextAnalysisDialog._render_entries
- OriginalTextAnalysisDialog._handle_bar_selected
- OriginalTextAnalysisDialog._handle_table_selection
- OriginalTextAnalysisDialog._handle_table_double_click
- OriginalTextAnalysisDialog._on_font_changed

### Файл: gemini\paint_event_logic.py
- LNETPaintEventLogic.__init__
- LNETPaintEventLogic.execute_paint_event

### Файл: gemini\paint_handlers.py
- LNETPaintHandlers.__init__
- LNETPaintHandlers.paintEvent
- LNETPaintHandlers.lineNumberAreaPaintEvent

### Файл: gemini\paint_helpers.py
- LNETPaintHelpers.__init__
- LNETPaintHelpers._map_no_tag_index_to_raw_text_index

### Файл: gemini\plugins_plain_text_problem_analyzer.py
- ProblemAnalyzer.__init__
- ProblemAnalyzer._ends_with_sentence_punctuation_zww
- ProblemAnalyzer._check_short_line_zww
- ProblemAnalyzer.check_for_empty_first_line_of_page
- ProblemAnalyzer.analyze_data_string
- ProblemAnalyzer.analyze_subline

### Файл: gemini\plugins_plain_text_rules.py
- GameRules.__init__
- GameRules.get_display_name
- GameRules.get_default_tag_mappings
- GameRules.load_data_from_json_obj
- GameRules.save_data_to_json_obj
- GameRules.get_tag_pattern
- GameRules.get_text_representation_for_preview
- GameRules.get_text_representation_for_editor
- GameRules.convert_editor_text_to_data
- GameRules.get_syntax_highlighting_rules
- GameRules.get_legitimate_tags
- GameRules.is_tag_legitimate
- GameRules.get_problem_definitions
- GameRules.get_short_problem_name
- GameRules.calculate_string_width_override
- GameRules.analyze_subline
- GameRules.autofix_data_string
- GameRules.process_pasted_segment

### Файл: gemini\plugins_plain_text_tag_manager.py
- TagManager.__init__
- TagManager.get_syntax_highlighting_rules
- TagManager.get_legitimate_tags
- TagManager.is_tag_legitimate

### Файл: gemini\plugins_plain_text_text_fixer.py
- TextFixer.__init__
- TextFixer._fix_empty_odd_sublines_zww
- TextFixer._fix_short_lines_zww
- TextFixer._cleanup_spaces_around_tags_zww
- TextFixer.fix_empty_first_line_of_page
- TextFixer.autofix_data_string

### Файл: gemini\plugins_pokemon_fr_problem_analyzer.py
- ProblemAnalyzer.__init__
- ProblemAnalyzer._get_sublines_from_data_string
- ProblemAnalyzer._ends_with_sentence_punctuation
- ProblemAnalyzer._check_short_line
- ProblemAnalyzer.analyze_data_string
- ProblemAnalyzer.analyze_subline

### Файл: gemini\plugins_pokemon_fr_rules.py
- GameRules.__init__
- GameRules.load_data_from_json_obj
- GameRules.save_data_to_json_obj
- GameRules.get_text_representation_for_preview
- GameRules.get_enter_char
- GameRules.get_shift_enter_char
- GameRules.get_ctrl_enter_char
- GameRules.get_text_representation_for_editor
- GameRules.convert_editor_text_to_data
- GameRules.get_syntax_highlighting_rules
- GameRules.get_display_name
- GameRules.get_problem_definitions
- GameRules.get_default_tag_mappings
- GameRules.analyze_subline
- GameRules.autofix_data_string
- GameRules.process_pasted_segment

### Файл: gemini\plugins_pokemon_fr_tag_manager.py
- TagManager.__init__
- TagManager.get_syntax_highlighting_rules
- TagManager.get_legitimate_tags
- TagManager.is_tag_legitimate

### Файл: gemini\plugins_pokemon_fr_text_fixer.py
- TextFixer.__init__
- TextFixer._get_sublines_with_tags
- TextFixer._reassemble_data_string
- TextFixer._fix_width_exceeded
- TextFixer._fix_short_lines
- TextFixer._fix_empty_sublines
- TextFixer.autofix_data_string

### Файл: gemini\plugins_zelda_mc_problem_analyzer.py
- ProblemAnalyzer.__init__
- ProblemAnalyzer._ends_with_sentence_punctuation_zmc
- ProblemAnalyzer._check_short_line_zmc
- ProblemAnalyzer._check_empty_odd_subline_display_zmc
- ProblemAnalyzer.analyze_subline

### Файл: gemini\plugins_zelda_mc_rules.py
- GameRules.__init__
- GameRules.load_data_from_json_obj
- GameRules.save_data_to_json_obj
- GameRules.get_display_name
- GameRules.get_default_tag_mappings
- GameRules.get_tag_checker_handler
- GameRules.get_syntax_highlighting_rules
- GameRules.get_legitimate_tags
- GameRules.is_tag_legitimate
- GameRules.get_problem_definitions
- GameRules.get_short_problem_name
- GameRules.get_plugin_actions
- GameRules.get_text_representation_for_preview
- GameRules.get_text_representation_for_editor
- GameRules.convert_editor_text_to_data
- GameRules.analyze_subline
- GameRules.autofix_data_string
- GameRules.process_pasted_segment
- GameRules.get_base_game_rules_class

### Файл: gemini\plugins_zelda_mc_tag_logic.py
- analyze_tags_for_issues_zmc
- process_segment_tags_aggressively_zmc

### Файл: gemini\plugins_zelda_mc_tag_manager.py
- TagManager.__init__
- TagManager.reconfigure_styles
- TagManager.get_syntax_highlighting_rules
- TagManager._ensure_exact_tags_loaded
- TagManager.get_legitimate_tags
- TagManager.is_tag_legitimate

### Файл: gemini\plugins_zelda_mc_text_fixer.py
- TextFixer.__init__
- TextFixer._fix_empty_odd_sublines_zmc
- TextFixer._fix_short_lines_zmc
- TextFixer._fix_blue_sublines_zmc
- TextFixer._fix_leading_spaces_in_sublines_zmc
- TextFixer._cleanup_spaces_around_tags_zmc
- TextFixer.autofix_data_string

### Файл: gemini\plugins_zelda_ww_problem_analyzer.py
- ProblemAnalyzer.__init__
- ProblemAnalyzer._ends_with_sentence_punctuation_zww
- ProblemAnalyzer._check_short_line_zww
- ProblemAnalyzer.check_for_empty_first_line_of_page
- ProblemAnalyzer.analyze_data_string
- ProblemAnalyzer.analyze_subline

### Файл: gemini\plugins_zelda_ww_rules.py
- GameRules.__init__
- GameRules.load_data_from_json_obj
- GameRules.save_data_to_json_obj
- GameRules.get_display_name
- GameRules.get_problem_definitions
- GameRules.get_syntax_highlighting_rules
- GameRules.get_legitimate_tags
- GameRules.is_tag_legitimate
- GameRules.analyze_subline
- GameRules.autofix_data_string
- GameRules.process_pasted_segment
- GameRules.calculate_string_width_override
- GameRules.get_short_problem_name
- GameRules.get_text_representation_for_preview
- GameRules.get_text_representation_for_editor
- GameRules.convert_editor_text_to_data
- GameRules.get_enter_char
- GameRules.get_shift_enter_char
- GameRules.get_ctrl_enter_char
- GameRules.get_editor_page_size

### Файл: gemini\plugins_zelda_ww_tag_logic.py
- _analyze_tags_for_issues_zww
- process_segment_tags_aggressively_zww

### Файл: gemini\plugins_zelda_ww_tag_manager.py
- TagManager.__init__
- TagManager.reconfigure_styles
- TagManager.get_syntax_highlighting_rules
- TagManager.get_legitimate_tags
- TagManager.is_tag_legitimate

### Файл: gemini\plugins_zelda_ww_text_fixer.py
- TextFixer.__init__
- TextFixer._fix_empty_odd_sublines_zww
- TextFixer._fix_short_lines_zww
- TextFixer._cleanup_spaces_around_tags_zww
- TextFixer.fix_empty_first_line_of_page
- TextFixer.autofix_data_string

### Файл: gemini\preview_updater.py
- PreviewUpdater.__init__
- PreviewUpdater.populate_strings_for_block

### Файл: gemini\problem_analyzer.py
- GenericProblemAnalyzer.__init__
- GenericProblemAnalyzer._check_single_word_subline_generic
- GenericProblemAnalyzer.analyze_subline

### Файл: gemini\project_action_handler.py
- ProjectActionHandler.__init__
- ProjectActionHandler.create_new_project_action
- ProjectActionHandler.open_project_action
- ProjectActionHandler.close_project_action
- ProjectActionHandler.import_block_action
- ProjectActionHandler.delete_block_action
- ProjectActionHandler.move_block_up_action
- ProjectActionHandler.move_block_down_action
- ProjectActionHandler._populate_blocks_from_project
- ProjectActionHandler._update_recent_projects_menu
- ProjectActionHandler._open_recent_project
- ProjectActionHandler._clear_recent_projects

### Файл: gemini\project_dialogs.py
- NewProjectDialog.__init__
- NewProjectDialog._setup_ui
- NewProjectDialog._populate_plugins
- NewProjectDialog._scan_plugins
- NewProjectDialog._browse_directory
- NewProjectDialog._validate_and_accept
- NewProjectDialog.get_project_info
- OpenProjectDialog.__init__
- OpenProjectDialog._setup_ui
- OpenProjectDialog._browse_file
- OpenProjectDialog._validate_and_accept
- OpenProjectDialog.get_project_path
- ImportBlockDialog.__init__
- ImportBlockDialog._setup_ui
- ImportBlockDialog._browse_source_file
- ImportBlockDialog._browse_translation_file
- ImportBlockDialog._on_source_file_selected
- ImportBlockDialog._validate_and_accept
- ImportBlockDialog.get_block_info

### Файл: gemini\project_manager.py
- ProjectManager.__init__
- ProjectManager.create_new_project
- ProjectManager.load
- ProjectManager.save
- ProjectManager.add_block
- ProjectManager.get_uncategorized_lines
- ProjectManager.get_absolute_path
- ProjectManager.get_relative_path
- ProjectManager.save_settings_to_project
- ProjectManager.load_settings_from_project
- ProjectManager.current_project

### Файл: gemini\project_models.py
- Category.to_dict
- Category.from_dict
- Category.add_child
- Category.remove_child
- Category.find_category
- Block.to_dict
- Block.from_dict
- Block.add_category
- Block.remove_category
- Block.find_category
- Block.get_all_categories_flat
- Block._get_children_recursive
- Block.get_categorized_line_indices
- Project.to_dict
- Project.from_dict
- Project.add_block
- Project.remove_block
- Project.find_block
- Project.find_block_by_name

### Файл: gemini\prompt_editor_dialog.py
- PromptEditorDialog.__init__
- PromptEditorDialog.get_text

### Файл: gemini\providers.py
- BaseTranslationProvider.__init__
- BaseTranslationProvider.translate
- BaseTranslationProvider.translate_stream
- OpenAIChatProvider.__init__
- OpenAIChatProvider._prepare_body
- OpenAIChatProvider.translate
- OpenAIChatProvider.translate_stream
- OpenAIResponsesProvider.__init__
- OpenAIResponsesProvider.translate
- OllamaChatProvider.__init__
- OllamaChatProvider.translate
- OllamaChatProvider.translate_stream
- ChatMockProvider._prepare_body
- DeepLProvider.translate
- GeminiProvider.__init__
- GeminiProvider.start_new_chat_session
- GeminiProvider.translate
- GeminiProvider.translate_stream
- GeminiProvider._translate_via_openai_compat
- GeminiProvider._translate_via_native_api
- GeminiProvider._translate_via_native_stream
- create_translation_provider
- get_provider_for_config

### Файл: gemini\rules.py
- _analyze_tags_for_issues_kruptar
- ImportRules.parse_clipboard_text
- ImportRules.process_segment_for_insertion

### Файл: gemini\search_handler.py
- SearchHandler.__init__
- SearchHandler.get_current_search_params
- SearchHandler._get_text_for_search
- SearchHandler.reset_search
- SearchHandler._find_in_text
- SearchHandler.find_next
- SearchHandler.find_previous
- SearchHandler._find_nth_occurrence_in_display_text
- SearchHandler._calculate_qtextblock_and_pos_in_block
- SearchHandler._navigate_to_match
- SearchHandler.clear_all_search_highlights

### Файл: gemini\search_panel.py
- SearchPanelWidget.__init__
- SearchPanelWidget._on_find_next_from_combobox_activation
- SearchPanelWidget._add_to_history
- SearchPanelWidget._update_combobox_items
- SearchPanelWidget.load_history
- SearchPanelWidget.get_history
- SearchPanelWidget._on_find_next
- SearchPanelWidget._on_find_previous
- SearchPanelWidget.get_search_parameters
- SearchPanelWidget.set_status_message
- SearchPanelWidget.focus_search_input
- SearchPanelWidget.clear_status
- SearchPanelWidget.get_query
- SearchPanelWidget.set_query
- SearchPanelWidget.set_search_options

### Файл: gemini\session_bootstrap_dialog.py
- SessionBootstrapDialog.__init__
- SessionBootstrapDialog.get_instructions

### Файл: gemini\session_manager.py
- TranslationSessionState.set_instructions
- TranslationSessionState.prepare_request
- TranslationSessionState.record_exchange
- TranslationSessionManager.__init__
- TranslationSessionManager.reset
- TranslationSessionManager.ensure_session
- TranslationSessionManager.get_state

### Файл: gemini\settings_dialog.py
- ColorPickerButton.__init__
- ColorPickerButton.color
- ColorPickerButton.setColor
- ColorPickerButton._update_style
- ColorPickerButton._get_contrasting_text_color
- ColorPickerButton.pick_color
- SettingsDialog.__init__
- SettingsDialog._get_lang_name
- SettingsDialog._create_path_selector
- SettingsDialog._browse_for_file
- SettingsDialog.setup_general_tab
- SettingsDialog.setup_plugin_tab
- SettingsDialog.rebuild_plugin_tabs
- SettingsDialog.setup_spelling_tab
- SettingsDialog._open_dictionary_manager
- SettingsDialog.populate_spellchecker_languages
- SettingsDialog._populate_font_list
- SettingsDialog._setup_display_subtab
- SettingsDialog.on_rules_changed
- SettingsDialog._setup_rules_subtab
- SettingsDialog._setup_paths_subtab
- SettingsDialog._populate_checkbox_subtab
- SettingsDialog._setup_detection_subtab
- SettingsDialog._setup_autofix_subtab
- SettingsDialog.on_provider_changed
- SettingsDialog.setup_ai_translation_tab
- SettingsDialog.setup_ai_glossary_tab
- SettingsDialog._set_glossary_api_key_text
- SettingsDialog._get_translation_credentials_for_glossary
- SettingsDialog._update_glossary_api_key_controls
- SettingsDialog._refresh_glossary_api_key_from_translation
- SettingsDialog._on_glossary_use_translation_key_changed
- SettingsDialog._on_glossary_provider_changed
- SettingsDialog._on_glossary_api_key_changed
- SettingsDialog.find_plugins
- SettingsDialog.populate_plugin_list
- SettingsDialog.on_theme_changed
- SettingsDialog.on_plugin_changed
- SettingsDialog.load_initial_settings
- SettingsDialog.get_settings

### Файл: gemini\settings_manager.py
- SettingsManager.__init__
- SettingsManager._substitute_env_vars
- SettingsManager.get
- SettingsManager.set
- SettingsManager._get_plugin_config_path
- SettingsManager.load_settings
- SettingsManager._load_global_settings
- SettingsManager._load_plugin_settings
- SettingsManager.save_settings
- SettingsManager._save_global_settings
- SettingsManager._save_plugin_settings
- SettingsManager.save_block_names
- SettingsManager.load_unsaved_session
- SettingsManager._parse_new_font_format
- SettingsManager.load_all_font_maps
- SettingsManager._load_font_overrides
- SettingsManager._apply_font_overrides
- SettingsManager._refresh_icon_highlighting
- SettingsManager._update_icon_sequences_cache
- SettingsManager.add_recent_project
- SettingsManager.remove_recent_project
- SettingsManager.clear_recent_projects

### Файл: gemini\spellcheck_dialog.py
- SpellcheckDialog.__init__
- SpellcheckDialog.setup_ui
- SpellcheckDialog._process_text_spacing_and_line_numbers
- SpellcheckDialog._apply_zebra_striping
- SpellcheckDialog._load_content
- SpellcheckDialog.find_misspelled_words
- SpellcheckDialog.pre_highlight_all_misspelled_words
- SpellcheckDialog.show_current_word
- SpellcheckDialog.go_to_previous_word
- SpellcheckDialog.go_to_next_word
- SpellcheckDialog.clear_current_word_highlight
- SpellcheckDialog.jump_to_word_from_list
- SpellcheckDialog.ignore_word
- SpellcheckDialog.ignore_all_word
- SpellcheckDialog.replace_word
- SpellcheckDialog.replace_with_suggestion
- SpellcheckDialog.add_to_dictionary
- SpellcheckDialog.get_corrected_text
- SpellcheckDialog._on_text_double_click

### Файл: gemini\spellchecker_manager.py
- SpellcheckerManager.__init__
- SpellcheckerManager._initialize_spellchecker
- SpellcheckerManager.reload_dictionary
- SpellcheckerManager.set_enabled
- SpellcheckerManager.scan_local_dictionaries
- SpellcheckerManager._load_user_dictionary
- SpellcheckerManager.reload_glossary_words
- SpellcheckerManager._load_glossary_words
- SpellcheckerManager.add_to_custom_dictionary
- SpellcheckerManager.is_misspelled
- SpellcheckerManager.get_suggestions

### Файл: gemini\string_settings_handler.py
- StringSettingsHandler.__init__
- StringSettingsHandler._apply_and_rescan
- StringSettingsHandler.on_font_changed
- StringSettingsHandler.on_width_changed
- StringSettingsHandler.apply_settings_change
- StringSettingsHandler.apply_font_to_range
- StringSettingsHandler.apply_font_to_lines
- StringSettingsHandler.apply_width_to_lines
- StringSettingsHandler.apply_width_to_range

### Файл: gemini\string_settings_updater.py
- StringSettingsUpdater.__init__
- StringSettingsUpdater.update_font_combobox
- StringSettingsUpdater.update_string_settings_panel

### Файл: gemini\syntax_highlighter.py
- JsonTagHighlighter.__init__
- JsonTagHighlighter.on_contents_change
- JsonTagHighlighter.set_glossary_manager
- JsonTagHighlighter.set_spellchecker_enabled
- JsonTagHighlighter._apply_css_to_format
- JsonTagHighlighter.reconfigure_styles
- JsonTagHighlighter._invalidate_icon_cache
- JsonTagHighlighter._rebuild_glossary_cache
- JsonTagHighlighter._ensure_icon_cache
- JsonTagHighlighter._get_icon_matches_for_block
- JsonTagHighlighter._get_icon_sequences
- JsonTagHighlighter._should_highlight_icons
- JsonTagHighlighter._should_check_spelling
- JsonTagHighlighter._extract_words_from_text
- JsonTagHighlighter.highlightBlock

### Файл: gemini\tag_checker_handler.py
- TagCheckerHandler.__init__
- TagCheckerHandler._get_initial_search_indices
- TagCheckerHandler._get_tags_from_string
- TagCheckerHandler._find_tag_in_translation
- TagCheckerHandler._highlight_mismatched_tag
- TagCheckerHandler._remove_mismatch_highlight
- TagCheckerHandler._reset_search_state_and_ui
- TagCheckerHandler._show_completion_popup
- TagCheckerHandler.start_or_continue_check

### Файл: gemini\tag_logic.py
- _analyze_tags_for_issues_zww
- process_segment_tags_aggressively_zww

### Файл: gemini\tag_manager.py
- GenericTagManager.__init__
- GenericTagManager.reconfigure_styles
- GenericTagManager.get_syntax_highlighting_rules
- GenericTagManager.is_tag_legitimate
- GenericTagManager.get_legitimate_tags

### Файл: gemini\tag_utils.py
- apply_default_mappings_only

### Файл: gemini\test_project_dialogs_manual.py
- TestWindow.__init__
- TestWindow.test_new_project_dialog
- TestWindow.test_open_project_dialog
- TestWindow.test_import_block_dialog
- main

### Файл: gemini\test_project_manager.py
- test_basic_project_creation
- test_load_save_project
- test_add_block
- test_categories
- test_uncategorized_lines
- test_serialization
- run_all_tests

### Файл: gemini\text_analysis_handler.py
- TextAnalysisHandler.__init__
- TextAnalysisHandler.ensure_menu_action
- TextAnalysisHandler.analyze_original_text
- TextAnalysisHandler._activate_entry

### Файл: gemini\text_autofix_logic.py
- TextAutofixLogic.__init__
- TextAutofixLogic._ends_with_sentence_punctuation
- TextAutofixLogic._extract_first_word_with_tags
- TextAutofixLogic._fix_empty_odd_sublines
- TextAutofixLogic._fix_short_lines
- TextAutofixLogic._fix_width_exceeded
- TextAutofixLogic._fix_blue_sublines
- TextAutofixLogic._fix_leading_spaces_in_sublines
- TextAutofixLogic._cleanup_spaces_around_tags
- TextAutofixLogic.auto_fix_current_string

### Файл: gemini\text_fixer.py
- GenericTextFixer.__init__
- GenericTextFixer._extract_first_word_with_tags_generic
- GenericTextFixer._fix_width_exceeded_generic

### Файл: gemini\text_highlight_manager.py
- TextHighlightManager.__init__
- TextHighlightManager._create_block_background_selection
- TextHighlightManager._create_search_match_selection
- TextHighlightManager.applyHighlights
- TextHighlightManager.updateCurrentLineHighlight
- TextHighlightManager.clearCurrentLineHighlight
- TextHighlightManager.setLinkedCursorPosition
- TextHighlightManager.clearLinkedCursorPosition
- TextHighlightManager.setPreviewSelectedLineHighlight
- TextHighlightManager.set_background_for_lines
- TextHighlightManager.clearPreviewSelectedLineHighlight
- TextHighlightManager.addProblemLineHighlight
- TextHighlightManager.addCriticalProblemHighlight
- TextHighlightManager.removeCriticalProblemHighlight
- TextHighlightManager.clearCriticalProblemHighlights
- TextHighlightManager.hasCriticalProblemHighlight
- TextHighlightManager.addWarningLineHighlight
- TextHighlightManager.removeWarningLineHighlight
- TextHighlightManager.clearWarningLineHighlights
- TextHighlightManager.hasWarningLineHighlight
- TextHighlightManager.momentaryHighlightTag
- TextHighlightManager.clearTagInteractionHighlight
- TextHighlightManager.add_search_match_highlight
- TextHighlightManager.clear_search_match_highlights
- TextHighlightManager.add_width_exceed_char_highlight
- TextHighlightManager.clear_width_exceed_char_highlights
- TextHighlightManager.addEmptyOddSublineHighlight
- TextHighlightManager.removeEmptyOddSublineHighlight
- TextHighlightManager.clearEmptyOddSublineHighlights
- TextHighlightManager.hasEmptyOddSublineHighlight
- TextHighlightManager.clearAllProblemHighlights
- TextHighlightManager.clearAllHighlights

### Файл: gemini\text_operation_handler.py
- TextOperationHandler.__init__
- TextOperationHandler._rescan_issues_for_current_string
- TextOperationHandler._log_undo_state
- TextOperationHandler._update_preview_content
- TextOperationHandler.text_edited
- TextOperationHandler.paste_block_text
- TextOperationHandler.revert_single_line
- TextOperationHandler.calculate_width_for_data_line_action
- TextOperationHandler.auto_fix_current_string

### Файл: gemini\title_status_bar_updater.py
- TitleStatusBarUpdater.__init__
- TitleStatusBarUpdater.update_title
- TitleStatusBarUpdater.update_statusbar_paths

### Файл: gemini\translation_handler.py
- TranslationHandler.__init__
- TranslationHandler.initialize_glossary_highlighting
- TranslationHandler.show_glossary_dialog
- TranslationHandler.get_glossary_entry
- TranslationHandler.add_glossary_entry
- TranslationHandler.edit_glossary_entry
- TranslationHandler.append_selection_to_glossary
- TranslationHandler.request_glossary_occurrence_update
- TranslationHandler.request_glossary_occurrence_batch_update
- TranslationHandler.request_glossary_notes_variation
- TranslationHandler.reset_translation_session
- TranslationHandler._trim_trailing_whitespace_from_lines
- TranslationHandler._maybe_edit_prompt
- TranslationHandler._should_use_session
- TranslationHandler._prepare_session_for_request
- TranslationHandler._attach_session_to_task
- TranslationHandler._record_session_exchange
- TranslationHandler._set_notes_dialog_busy
- TranslationHandler._cleanup_and_retry
- TranslationHandler._run_ai_task
- TranslationHandler.prompt_for_revert_after_cancel
- TranslationHandler._handle_translation_cancellation
- TranslationHandler._setup_progress_bar
- TranslationHandler.translate_current_string
- TranslationHandler.translate_preview_selection
- TranslationHandler.translate_current_block
- TranslationHandler.resume_block_translation
- TranslationHandler._resolve_base_timeout
- TranslationHandler._initiate_batch_translation
- TranslationHandler._handle_chunk_translated
- TranslationHandler._handle_preview_translation_success
- TranslationHandler._handle_single_translation_success
- TranslationHandler._handle_glossary_occurrence_update_success
- TranslationHandler._handle_glossary_occurrence_batch_success
- TranslationHandler._handle_glossary_notes_variation_success
- TranslationHandler._handle_variation_success
- TranslationHandler._handle_ai_error
- TranslationHandler.generate_variation_for_current_string
- TranslationHandler._translate_and_apply
- TranslationHandler._prepare_provider
- TranslationHandler._log_provider_response
- TranslationHandler._clean_model_output
- TranslationHandler.translate_selected_lines

### Файл: gemini\translation_ui_handler.py
- TranslationUIHandler.__init__
- TranslationUIHandler._set_ai_controls_enabled
- TranslationUIHandler.status_dialog
- TranslationUIHandler.show_variations_dialog
- TranslationUIHandler.prompt_session_bootstrap
- TranslationUIHandler.confirm_line_count
- TranslationUIHandler.apply_full_translation
- TranslationUIHandler.apply_inline_variation
- TranslationUIHandler.apply_partial_translation
- TranslationUIHandler.normalize_line_count
- TranslationUIHandler.parse_variation_payload
- TranslationUIHandler.update_status_message
- TranslationUIHandler.clear_status_message
- TranslationUIHandler.start_ai_operation
- TranslationUIHandler._handle_dialog_rejection
- TranslationUIHandler.update_ai_operation_step
- TranslationUIHandler.finish_ai_operation
- TranslationUIHandler.merge_session_instructions
- TranslationUIHandler._activate_entry

### Файл: gemini\translation_variations_dialog.py
- TranslationVariationsDialog.__init__
- TranslationVariationsDialog._populate_variations
- TranslationVariationsDialog._update_preview
- TranslationVariationsDialog._apply_current_selection

### Файл: gemini\ui_event_filters.py
- TextEditEventFilter.__init__
- TextEditEventFilter.eventFilter
- MainWindowEventFilter.__init__
- MainWindowEventFilter.eventFilter

### Файл: gemini\ui_setup.py
- setup_main_window_ui

### Файл: gemini\ui_updater.py
- UIUpdater.__init__
- UIUpdater.highlight_glossary_occurrence
- UIUpdater._get_aggregated_problems_for_block
- UIUpdater.populate_blocks
- UIUpdater.update_block_item_text_with_problem_count
- UIUpdater.update_status_bar
- UIUpdater.update_status_bar_selection
- UIUpdater.clear_status_bar
- UIUpdater.synchronize_original_cursor
- UIUpdater.highlight_problem_block
- UIUpdater.clear_all_problem_block_highlights_and_text
- UIUpdater.update_title
- UIUpdater.update_plugin_status_label
- UIUpdater.update_statusbar_paths
- UIUpdater._apply_highlights_for_block
- UIUpdater._apply_highlights_to_editor
- UIUpdater.populate_strings_for_block
- UIUpdater.update_text_views

### Файл: gemini\utils.py
- remove_all_tags
- calculate_string_width
- convert_spaces_to_dots_for_display
- convert_dots_to_spaces_from_editor
- remove_curly_tags
- convert_raw_to_display_text
- prepare_text_for_tagless_search

### Файл: handlers\ai_chat_handler.py
- AIChatHandler.__init__
- AIChatHandler._get_available_providers
- AIChatHandler.show_chat_window
- AIChatHandler._add_new_chat_session
- AIChatHandler._handle_tab_closed
- AIChatHandler._handle_send_message
- AIChatHandler._process_annotations
- AIChatHandler._format_ai_response_for_display
- AIChatHandler._on_ai_chunk_received
- AIChatHandler._on_ai_stream_finished
- AIChatHandler._on_ai_chat_success
- AIChatHandler._on_ai_error
- AIChatHandler._cleanup_worker

### Файл: handlers\app_action_handler.py
- AppActionHandler.__init__
- AppActionHandler.rescan_all_tags
- AppActionHandler.handle_close_event
- AppActionHandler._derive_edited_path
- AppActionHandler.open_file_dialog_action
- AppActionHandler.open_changes_file_dialog_action
- AppActionHandler.save_data_action
- AppActionHandler.save_as_dialog_action
- AppActionHandler.load_all_data_for_path
- AppActionHandler.reload_original_data_action
- AppActionHandler.calculate_widths_for_block_action
- AppActionHandler._perform_initial_silent_scan_all_issues

### Файл: handlers\base_handler.py
- BaseHandler.__init__
- BaseHandler.mw
- BaseHandler.state
- BaseHandler.data_store

### Файл: handlers\issue_scan_handler.py
- IssueScanHandler.__init__
- IssueScanHandler._perform_issues_scan_for_block
- IssueScanHandler._perform_initial_silent_scan_all_issues
- IssueScanHandler.rescan_issues_for_single_block
- IssueScanHandler.rescan_all_tags

### Файл: handlers\list_selection_handler.py
- ListSelectionHandler.__init__
- ListSelectionHandler.navigate_between_blocks
- ListSelectionHandler.navigate_between_folders
- ListSelectionHandler.block_selected
- ListSelectionHandler._restore_block_selection
- ListSelectionHandler._update_block_toolbar_button_states
- ListSelectionHandler.select_string_by_absolute_index
- ListSelectionHandler.string_selected_from_preview
- ListSelectionHandler.rename_block
- ListSelectionHandler.handle_block_item_text_changed
- ListSelectionHandler._data_string_has_any_problem
- ListSelectionHandler.navigate_to_problem_string
- ListSelectionHandler.handle_preview_selection_changed
- ListSelectionHandler.move_selection_to_category
- ListSelectionHandler.rename_category
- ListSelectionHandler.delete_category
- ListSelectionHandler.toggle_highlight_categorized
- ListSelectionHandler.toggle_hide_categorized

### Файл: handlers\project_action_handler.py
- ProjectActionHandler.__init__
- ProjectActionHandler._set_project_actions_enabled
- ProjectActionHandler.create_new_project_action
- ProjectActionHandler.open_project_action
- ProjectActionHandler.close_project_action
- ProjectActionHandler.import_block_action
- ProjectActionHandler.import_directory_action
- ProjectActionHandler.delete_block_action
- ProjectActionHandler.move_block_up_action
- ProjectActionHandler.move_block_down_action
- ProjectActionHandler.add_folder_action
- ProjectActionHandler.add_items_to_folder_action
- ProjectActionHandler._populate_blocks_from_project
- ProjectActionHandler._update_recent_projects_menu
- ProjectActionHandler._open_recent_project
- ProjectActionHandler._clear_recent_projects
- ProjectActionHandler.expand_all_action
- ProjectActionHandler.collapse_all_action
- ProjectActionHandler._update_all_folder_expansion_state

### Файл: handlers\search_handler.py
- SearchHandler.__init__
- SearchHandler.get_current_search_params
- SearchHandler._get_text_for_search
- SearchHandler.reset_search
- SearchHandler._find_in_text
- SearchHandler.find_next
- SearchHandler.find_previous
- SearchHandler._find_nth_occurrence_in_display_text
- SearchHandler._calculate_qtextblock_and_pos_in_block
- SearchHandler._navigate_to_match
- SearchHandler.clear_all_search_highlights

### Файл: handlers\string_settings_handler.py
- StringSettingsHandler.__init__
- StringSettingsHandler._apply_and_rescan
- StringSettingsHandler.on_font_changed
- StringSettingsHandler.on_width_changed
- StringSettingsHandler.apply_settings_change
- StringSettingsHandler.apply_font_to_range
- StringSettingsHandler.apply_font_to_lines
- StringSettingsHandler.apply_width_to_lines
- StringSettingsHandler.apply_width_to_range

### Файл: handlers\text_analysis_handler.py
- TextAnalysisHandler.__init__
- TextAnalysisHandler.ensure_menu_action
- TextAnalysisHandler.analyze_original_text
- TextAnalysisHandler._activate_entry

### Файл: handlers\text_autofix_logic.py
- TextAutofixLogic.__init__
- TextAutofixLogic._ends_with_sentence_punctuation
- TextAutofixLogic._extract_first_word_with_tags
- TextAutofixLogic._fix_empty_odd_sublines
- TextAutofixLogic._fix_short_lines
- TextAutofixLogic._fix_width_exceeded
- TextAutofixLogic._fix_blue_sublines
- TextAutofixLogic._fix_leading_spaces_in_sublines
- TextAutofixLogic._cleanup_spaces_around_tags
- TextAutofixLogic.auto_fix_current_string

### Файл: handlers\text_operation_handler.py
- TextOperationHandler.__init__
- TextOperationHandler._rescan_issues_for_current_string
- TextOperationHandler._log_undo_state
- TextOperationHandler._update_preview_content
- TextOperationHandler.text_edited
- TextOperationHandler.paste_block_text
- TextOperationHandler.revert_single_line
- TextOperationHandler.calculate_width_for_data_line_action
- TextOperationHandler.auto_fix_current_string

### Файл: handlers\translation\ai_lifecycle_manager.py
- AILifecycleManager.__init__
- AILifecycleManager.register_handler
- AILifecycleManager._prepare_provider
- AILifecycleManager.run_ai_task
- AILifecycleManager._on_thread_finished
- AILifecycleManager._on_success
- AILifecycleManager._on_chunk_translated
- AILifecycleManager._on_worker_cancelled
- AILifecycleManager._on_error
- AILifecycleManager._handle_task_error
- AILifecycleManager._record_session_exchange
- AILifecycleManager._clean_model_output
- AILifecycleManager._trim_trailing_whitespace_from_lines
- AILifecycleManager._on_retry_timer_timeout
- AILifecycleManager._perform_retry

### Файл: handlers\translation\ai_prompt_composer.py
- AIPromptComposer.prepare_text_for_translation
- AIPromptComposer.restore_placeholders
- AIPromptComposer.compose_batch_request
- AIPromptComposer.compose_variation_request
- AIPromptComposer.compose_messages
- AIPromptComposer.compose_glossary_occurrence_update_request
- AIPromptComposer.compose_glossary_occurrence_batch_request
- AIPromptComposer.compose_glossary_request
- AIPromptComposer._glossary_entries_to_text
- AIPromptComposer._prepare_glossary_for_prompt

### Файл: handlers\translation\ai_worker.py
- AIWorker.__init__
- AIWorker.cancel
- AIWorker._clean_json_response
- AIWorker.run

### Файл: handlers\translation\base_translation_handler.py
- BaseTranslationHandler.__init__

### Файл: handlers\translation\glossary_builder_handler.py
- GlossaryBuilderHandler.__init__
- GlossaryBuilderHandler._load_prompts
- GlossaryBuilderHandler._split_text_into_chunks
- GlossaryBuilderHandler._mask_tags_for_ai
- GlossaryBuilderHandler._clean_json_response
- GlossaryBuilderHandler._resolve_translation_credentials
- GlossaryBuilderHandler.build_glossary_for_block
- GlossaryBuilderHandler._start_async_glossary_task
- GlossaryBuilderHandler._on_glossary_success
- GlossaryBuilderHandler._on_glossary_error
- GlossaryBuilderHandler._on_glossary_cancelled
- GlossaryBuilderHandler._cleanup_worker

### Файл: handlers\translation\glossary_handler.py
- GlossaryHandler.__init__
- GlossaryHandler._current_prompts_path
- GlossaryHandler.translation_update_dialog
- GlossaryHandler.translation_update_dialog
- GlossaryHandler.load_prompts
- GlossaryHandler.save_prompt_section
- GlossaryHandler._get_glossary_prompt_template
- GlossaryHandler._update_glossary_highlighting
- GlossaryHandler._ensure_glossary_loaded
- GlossaryHandler.request_glossary_occurrence_update
- GlossaryHandler.request_glossary_occurrence_batch_update
- GlossaryHandler.request_glossary_notes_variation
- GlossaryHandler._handle_occurrence_ai_result
- GlossaryHandler._handle_occurrence_batch_success
- GlossaryHandler._handle_occurrence_ai_error
- GlossaryHandler._handle_glossary_occurrence_update_success
- GlossaryHandler._handle_glossary_occurrence_batch_success
- GlossaryHandler.install_menu_actions
- GlossaryHandler.initialize_glossary_highlighting
- GlossaryHandler._on_glossary_dialog_closed
- GlossaryHandler.show_glossary_dialog
- GlossaryHandler.add_glossary_entry
- GlossaryHandler.edit_glossary_entry
- GlossaryHandler._create_edit_dialog
- GlossaryHandler._ai_fill_glossary_entry
- GlossaryHandler._handle_ai_fill_success
- GlossaryHandler._handle_ai_fill_error
- GlossaryHandler._set_notes_dialog_busy
- GlossaryHandler._start_glossary_notes_variation
- GlossaryHandler._handle_notes_variation_from_dialog
- GlossaryHandler._handle_glossary_notes_variation_success
- GlossaryHandler._get_original_string
- GlossaryHandler._get_original_block
- GlossaryHandler._jump_to_occurrence
- GlossaryHandler._handle_glossary_entry_update
- GlossaryHandler._handle_glossary_entry_delete

### Файл: handlers\translation\glossary_occurrence_updater.py
- GlossaryOccurrenceUpdater.__init__
- GlossaryOccurrenceUpdater._mw
- GlossaryOccurrenceUpdater._main_handler
- GlossaryOccurrenceUpdater.show_translation_update_dialog
- GlossaryOccurrenceUpdater._on_dialog_closed
- GlossaryOccurrenceUpdater._get_occurrence_original_text
- GlossaryOccurrenceUpdater._get_occurrence_translation_text
- GlossaryOccurrenceUpdater._apply_occurrence_translation
- GlossaryOccurrenceUpdater._request_ai_occurrence_update
- GlossaryOccurrenceUpdater.request_glossary_occurrence_update
- GlossaryOccurrenceUpdater._start_ai_occurrence_batch
- GlossaryOccurrenceUpdater._resume_ai_occurrence_batch
- GlossaryOccurrenceUpdater.request_glossary_occurrence_batch_update
- GlossaryOccurrenceUpdater.handle_occurrence_ai_result
- GlossaryOccurrenceUpdater.handle_occurrence_batch_success
- GlossaryOccurrenceUpdater._handle_occurrence_ai_error
- GlossaryOccurrenceUpdater.handle_glossary_occurrence_update_success
- GlossaryOccurrenceUpdater.handle_glossary_occurrence_batch_success
- GlossaryOccurrenceUpdater.request_glossary_notes_variation

### Файл: handlers\translation\glossary_prompt_manager.py
- GlossaryPromptManager.__init__
- GlossaryPromptManager._plugin_dir
- GlossaryPromptManager._fallback_dir
- GlossaryPromptManager._resolve_file
- GlossaryPromptManager.load_prompts
- GlossaryPromptManager.initialize_highlighting
- GlossaryPromptManager.get_glossary_prompt_template
- GlossaryPromptManager.save_prompt_section
- GlossaryPromptManager._extract_system_prompt
- GlossaryPromptManager._extract_glossary_prompt
- GlossaryPromptManager._ensure_glossary_loaded
- GlossaryPromptManager._update_glossary_highlighting

### Файл: handlers\translation\translation_ui_handler.py
- TranslationUIHandler.__init__
- TranslationUIHandler._set_ai_controls_enabled
- TranslationUIHandler.status_dialog
- TranslationUIHandler.show_variations_dialog
- TranslationUIHandler.prompt_session_bootstrap
- TranslationUIHandler.confirm_line_count
- TranslationUIHandler.apply_full_translation
- TranslationUIHandler.apply_inline_variation
- TranslationUIHandler.apply_partial_translation
- TranslationUIHandler.normalize_line_count
- TranslationUIHandler.parse_variation_payload
- TranslationUIHandler.update_status_message
- TranslationUIHandler.clear_status_message
- TranslationUIHandler.start_ai_operation
- TranslationUIHandler._handle_dialog_rejection
- TranslationUIHandler.update_ai_operation_step
- TranslationUIHandler.finish_ai_operation
- TranslationUIHandler.merge_session_instructions
- TranslationUIHandler._activate_entry

### Файл: handlers\translation_handler.py
- TranslationHandler.__init__
- TranslationHandler.initialize_glossary_highlighting
- TranslationHandler.show_glossary_dialog
- TranslationHandler.get_glossary_entry
- TranslationHandler.add_glossary_entry
- TranslationHandler.edit_glossary_entry
- TranslationHandler.append_selection_to_glossary
- TranslationHandler._prepare_provider
- TranslationHandler.reset_translation_session
- TranslationHandler._maybe_edit_prompt
- TranslationHandler._should_use_session
- TranslationHandler._prepare_session_for_request
- TranslationHandler._attach_session_to_task
- TranslationHandler._set_notes_dialog_busy
- TranslationHandler._run_ai_task
- TranslationHandler._handle_ai_cancel
- TranslationHandler.prompt_for_revert_after_cancel
- TranslationHandler._setup_progress_bar
- TranslationHandler.translate_current_string
- TranslationHandler.translate_preview_selection
- TranslationHandler.translate_current_block
- TranslationHandler.resume_block_translation
- TranslationHandler._on_chunk_timer_timeout
- TranslationHandler._resolve_base_timeout
- TranslationHandler._initiate_batch_translation
- TranslationHandler._handle_chunk_translated
- TranslationHandler._handle_preview_translation_success
- TranslationHandler._handle_ai_error
- TranslationHandler._handle_single_translation_success
- TranslationHandler._on_task_finished
- TranslationHandler._handle_variation_success
- TranslationHandler.generate_variation_for_current_string
- TranslationHandler._translate_and_apply
- TranslationHandler._handle_block_translation_success
- TranslationHandler.translate_selected_lines

### Файл: main.py
- MainWindow.is_adjusting_cursor
- MainWindow.is_adjusting_cursor
- MainWindow.is_adjusting_selection
- MainWindow.is_adjusting_selection
- MainWindow.is_programmatically_changing_text
- MainWindow.is_programmatically_changing_text
- MainWindow.is_restart_in_progress
- MainWindow.is_restart_in_progress
- MainWindow.is_closing
- MainWindow.is_closing
- MainWindow.is_loading_data
- MainWindow.is_loading_data
- MainWindow.is_saving_data
- MainWindow.is_saving_data
- MainWindow.is_reverting_data
- MainWindow.is_reverting_data
- MainWindow.is_reloading_data
- MainWindow.is_reloading_data
- MainWindow.is_pasting_block
- MainWindow.is_pasting_block
- MainWindow.is_undoing_paste
- MainWindow.is_undoing_paste
- MainWindow.is_auto_fixing
- MainWindow.is_auto_fixing
- MainWindow.json_path
- MainWindow.json_path
- MainWindow.edited_json_path
- MainWindow.edited_json_path
- MainWindow.data
- MainWindow.data
- MainWindow.edited_data
- MainWindow.edited_data
- MainWindow.edited_file_data
- MainWindow.edited_file_data
- MainWindow.block_names
- MainWindow.block_names
- MainWindow.current_block_idx
- MainWindow.current_block_idx
- MainWindow.current_string_idx
- MainWindow.current_string_idx
- MainWindow.selected_string_indices
- MainWindow.selected_string_indices
- MainWindow.displayed_string_indices
- MainWindow.displayed_string_indices
- MainWindow.current_category_name
- MainWindow.current_category_name
- MainWindow.highlight_categorized
- MainWindow.highlight_categorized
- MainWindow.hide_categorized
- MainWindow.hide_categorized
- MainWindow.unsaved_changes
- MainWindow.unsaved_changes
- MainWindow.unsaved_block_indices
- MainWindow.unsaved_block_indices
- MainWindow.problems_per_subline
- MainWindow.problems_per_subline
- MainWindow.edited_sublines
- MainWindow.edited_sublines
- MainWindow.last_selected_block_index
- MainWindow.last_selected_block_index
- MainWindow.last_selected_string_index
- MainWindow.last_selected_string_index
- MainWindow.ui_provider
- MainWindow.force_focus
- MainWindow.__init__
- MainWindow._init_metadata
- MainWindow._init_state
- MainWindow._init_visual_settings
- MainWindow._init_data_structures
- MainWindow._init_handlers
- MainWindow._init_ui
- MainWindow.keyPressEvent
- MainWindow.load_game_plugin
- MainWindow.nativeEvent
- MainWindow.current_font_size
- MainWindow.current_font_size
- MainWindow.active_game_plugin
- MainWindow.active_game_plugin
- MainWindow.show_multiple_spaces_as_dots
- MainWindow.show_multiple_spaces_as_dots
- MainWindow.theme
- MainWindow.theme
- MainWindow.restore_unsaved_on_startup
- MainWindow.restore_unsaved_on_startup
- MainWindow.game_dialog_max_width_pixels
- MainWindow.game_dialog_max_width_pixels
- MainWindow.line_width_warning_threshold_pixels
- MainWindow.line_width_warning_threshold_pixels
- MainWindow.tree_font_size
- MainWindow.tree_font_size
- MainWindow.preview_font_size
- MainWindow.preview_font_size
- MainWindow.editors_font_size
- MainWindow.editors_font_size
- MainWindow.handle_zoom
- MainWindow.closeEvent
- MainWindow.build_glossary_with_ai
- global_exception_handler

### Файл: plugins\base_game_rules.py
- BaseGameRules.__init__
- BaseGameRules.load_data_from_json_obj
- BaseGameRules.save_data_to_json_obj
- BaseGameRules.get_enter_char
- BaseGameRules.get_shift_enter_char
- BaseGameRules.get_ctrl_enter_char
- BaseGameRules.convert_editor_text_to_data
- BaseGameRules.get_display_name
- BaseGameRules.get_problem_definitions
- BaseGameRules.get_color_marker_definitions
- BaseGameRules.get_spellcheck_ignore_pattern
- BaseGameRules.analyze_subline
- BaseGameRules.autofix_data_string
- BaseGameRules.process_pasted_segment
- BaseGameRules.get_base_game_rules_class
- BaseGameRules.get_default_tag_mappings
- BaseGameRules.get_tag_checker_handler
- BaseGameRules.get_short_problem_name
- BaseGameRules.get_plugin_actions
- BaseGameRules.get_text_representation_for_editor
- BaseGameRules.get_text_representation_for_preview
- BaseGameRules.get_syntax_highlighting_rules
- BaseGameRules.get_legitimate_tags
- BaseGameRules.get_context_menu_actions
- BaseGameRules.calculate_string_width_override
- BaseGameRules.get_editor_page_size
- BaseGameRules.get_custom_context_tags
- BaseGameRules.save_custom_context_tags

### Файл: plugins\common\problem_analyzer.py
- GenericProblemAnalyzer.__init__
- GenericProblemAnalyzer._check_single_word_subline_generic
- GenericProblemAnalyzer.analyze_subline

### Файл: plugins\common\tag_manager.py
- GenericTagManager.__init__
- GenericTagManager.reconfigure_styles
- GenericTagManager.get_syntax_highlighting_rules
- GenericTagManager.is_tag_legitimate
- GenericTagManager.get_legitimate_tags

### Файл: plugins\common\text_fixer.py
- GenericTextFixer.__init__
- GenericTextFixer._extract_first_word_with_tags_generic
- GenericTextFixer._fix_width_exceeded_generic

### Файл: plugins\import_plugins\base_import_rules.py
- BaseImportRules.__init__
- BaseImportRules.parse_clipboard_text
- BaseImportRules.process_segment_for_insertion
- BaseImportRules.apply_mappings_to_text

### Файл: plugins\import_plugins\kruptar_format\rules.py
- _analyze_tags_for_issues_kruptar
- ImportRules.parse_clipboard_text
- ImportRules.process_segment_for_insertion

### Файл: plugins\plain_text\problem_analyzer.py
- ProblemAnalyzer.__init__
- ProblemAnalyzer._ends_with_sentence_punctuation_zww
- ProblemAnalyzer._check_short_line_zww
- ProblemAnalyzer.check_for_empty_first_line_of_page
- ProblemAnalyzer.analyze_data_string
- ProblemAnalyzer.analyze_subline

### Файл: plugins\plain_text\rules.py
- GameRules.__init__
- GameRules.get_display_name
- GameRules.get_default_tag_mappings
- GameRules.load_data_from_json_obj
- GameRules.save_data_to_json_obj
- GameRules.get_tag_pattern
- GameRules.get_text_representation_for_preview
- GameRules.get_text_representation_for_editor
- GameRules.convert_editor_text_to_data
- GameRules.get_syntax_highlighting_rules
- GameRules.get_legitimate_tags
- GameRules.is_tag_legitimate
- GameRules.get_problem_definitions
- GameRules.get_short_problem_name
- GameRules.calculate_string_width_override
- GameRules.analyze_subline
- GameRules.autofix_data_string
- GameRules.process_pasted_segment

### Файл: plugins\plain_text\tag_logic.py
- _analyze_tags_for_issues_zww
- process_segment_tags_aggressively_zww

### Файл: plugins\plain_text\tag_manager.py
- TagManager.__init__
- TagManager.get_syntax_highlighting_rules
- TagManager.get_legitimate_tags
- TagManager.is_tag_legitimate

### Файл: plugins\plain_text\text_fixer.py
- TextFixer.__init__
- TextFixer._fix_empty_odd_sublines_zww
- TextFixer._fix_short_lines_zww
- TextFixer._cleanup_spaces_around_tags_zww
- TextFixer.fix_empty_first_line_of_page
- TextFixer.autofix_data_string

### Файл: plugins\pokemon_fr\problem_analyzer.py
- ProblemAnalyzer.__init__
- ProblemAnalyzer._get_sublines_from_data_string
- ProblemAnalyzer._ends_with_sentence_punctuation
- ProblemAnalyzer._check_short_line
- ProblemAnalyzer.analyze_data_string
- ProblemAnalyzer.analyze_subline

### Файл: plugins\pokemon_fr\rules.py
- GameRules.__init__
- GameRules.load_data_from_json_obj
- GameRules.save_data_to_json_obj
- GameRules.get_text_representation_for_preview
- GameRules.get_enter_char
- GameRules.get_shift_enter_char
- GameRules.get_ctrl_enter_char
- GameRules.get_text_representation_for_editor
- GameRules.convert_editor_text_to_data
- GameRules.get_syntax_highlighting_rules
- GameRules.get_display_name
- GameRules.get_problem_definitions
- GameRules.get_default_tag_mappings
- GameRules.analyze_subline
- GameRules.autofix_data_string
- GameRules.process_pasted_segment

### Файл: plugins\pokemon_fr\tag_manager.py
- TagManager.__init__
- TagManager.get_syntax_highlighting_rules
- TagManager.get_legitimate_tags
- TagManager.is_tag_legitimate

### Файл: plugins\pokemon_fr\text_fixer.py
- TextFixer.__init__
- TextFixer._get_sublines_with_tags
- TextFixer._reassemble_data_string
- TextFixer._fix_width_exceeded
- TextFixer._fix_short_lines
- TextFixer._fix_empty_sublines
- TextFixer.autofix_data_string

### Файл: plugins\zelda_mc\problem_analyzer.py
- ProblemAnalyzer.__init__
- ProblemAnalyzer._ends_with_sentence_punctuation_zmc
- ProblemAnalyzer._check_short_line_zmc
- ProblemAnalyzer._check_empty_odd_subline_display_zmc
- ProblemAnalyzer.analyze_subline

### Файл: plugins\zelda_mc\rules.py
- GameRules.__init__
- GameRules.load_data_from_json_obj
- GameRules.save_data_to_json_obj
- GameRules.get_display_name
- GameRules.get_default_tag_mappings
- GameRules.get_tag_checker_handler
- GameRules.get_syntax_highlighting_rules
- GameRules.get_legitimate_tags
- GameRules.is_tag_legitimate
- GameRules.get_problem_definitions
- GameRules.get_color_marker_definitions
- GameRules.get_short_problem_name
- GameRules.get_plugin_actions
- GameRules.get_text_representation_for_preview
- GameRules.get_text_representation_for_editor
- GameRules.convert_editor_text_to_data
- GameRules.analyze_subline
- GameRules.autofix_data_string
- GameRules.process_pasted_segment
- GameRules.get_base_game_rules_class

### Файл: plugins\zelda_mc\tag_checker_handler.py
- TagCheckerHandler.__init__
- TagCheckerHandler._get_initial_search_indices
- TagCheckerHandler._get_tags_from_string
- TagCheckerHandler._find_tag_in_translation
- TagCheckerHandler._highlight_mismatched_tag
- TagCheckerHandler._remove_mismatch_highlight
- TagCheckerHandler._reset_search_state_and_ui
- TagCheckerHandler._show_completion_popup
- TagCheckerHandler.start_or_continue_check

### Файл: plugins\zelda_mc\tag_logic.py
- analyze_tags_for_issues_zmc
- process_segment_tags_aggressively_zmc

### Файл: plugins\zelda_mc\tag_manager.py
- TagManager.__init__
- TagManager.reconfigure_styles
- TagManager.get_syntax_highlighting_rules
- TagManager._ensure_exact_tags_loaded
- TagManager.get_legitimate_tags
- TagManager.is_tag_legitimate

### Файл: plugins\zelda_mc\text_fixer.py
- TextFixer.__init__
- TextFixer._fix_empty_odd_sublines_zmc
- TextFixer._fix_short_lines_zmc
- TextFixer._fix_blue_sublines_zmc
- TextFixer._fix_leading_spaces_in_sublines_zmc
- TextFixer._cleanup_spaces_around_tags_zmc
- TextFixer.autofix_data_string

### Файл: plugins\zelda_ww\problem_analyzer.py
- ProblemAnalyzer.__init__
- ProblemAnalyzer._ends_with_sentence_punctuation_zww
- ProblemAnalyzer._check_short_line_zww
- ProblemAnalyzer.check_for_empty_first_line_of_page
- ProblemAnalyzer.analyze_data_string
- ProblemAnalyzer.analyze_subline

### Файл: plugins\zelda_ww\rules.py
- GameRules.__init__
- GameRules.load_data_from_json_obj
- GameRules.save_data_to_json_obj
- GameRules.get_display_name
- GameRules.get_problem_definitions
- GameRules.get_syntax_highlighting_rules
- GameRules.get_legitimate_tags
- GameRules.is_tag_legitimate
- GameRules.analyze_subline
- GameRules.autofix_data_string
- GameRules.process_pasted_segment
- GameRules.calculate_string_width_override
- GameRules.get_short_problem_name
- GameRules.get_text_representation_for_preview
- GameRules.get_text_representation_for_editor
- GameRules.convert_editor_text_to_data
- GameRules.get_enter_char
- GameRules.get_shift_enter_char
- GameRules.get_ctrl_enter_char
- GameRules.get_editor_page_size

### Файл: plugins\zelda_ww\tag_logic.py
- _analyze_tags_for_issues_zww
- process_segment_tags_aggressively_zww

### Файл: plugins\zelda_ww\tag_manager.py
- TagManager.__init__
- TagManager.reconfigure_styles
- TagManager.get_syntax_highlighting_rules
- TagManager.get_legitimate_tags
- TagManager.is_tag_legitimate

### Файл: plugins\zelda_ww\text_fixer.py
- TextFixer.__init__
- TextFixer._fix_empty_odd_sublines_zww
- TextFixer._fix_short_lines_zww
- TextFixer._cleanup_spaces_around_tags_zww
- TextFixer.fix_empty_first_line_of_page
- TextFixer.autofix_data_string

### Файл: scripts\build_gemini_dir.py
- copy_files_recursively

### Файл: scripts\bump_version.py
- bump

### Файл: scripts\cleanup_project.py
- git_commit
- delete_files
- move_files
- fix_imports
- main

### Файл: scripts\deploy.py
- log
- run_command
- get_current_version
- bump_version
- update_file
- get_recent_commits
- update_changelog
- deploy

### Файл: tree.py
- add_header_if_missing
- tree

### Файл: ui\builders\layout_builder.py
- LayoutBuilder.__init__
- LayoutBuilder.build
- LayoutBuilder._build_left_panel
- LayoutBuilder._build_right_panel
- LayoutBuilder._build_original_panel
- LayoutBuilder._build_edited_panel
- LayoutBuilder._create_header_button
- LayoutBuilder._create_toolbar_button

### Файл: ui\builders\menu_builder.py
- MenuBuilder.__init__
- MenuBuilder.build_all
- MenuBuilder._build_file_menu
- MenuBuilder._build_edit_menu
- MenuBuilder._build_tools_menu
- MenuBuilder._build_navigation_menu
- MenuBuilder._build_help_menu

### Файл: ui\builders\statusbar_builder.py
- StatusBarBuilder.__init__
- StatusBarBuilder.build

### Файл: ui\builders\toolbar_builder.py
- ToolBarBuilder.__init__
- ToolBarBuilder.build

### Файл: ui\main_window\main_window_actions.py
- MainWindowActions.__init__
- MainWindowActions.open_settings_dialog
- MainWindowActions.trigger_save_action
- MainWindowActions.trigger_revert_action
- MainWindowActions.trigger_undo_paste_action
- MainWindowActions.trigger_reload_tag_mappings
- MainWindowActions.handle_add_tag_mapping_request
- MainWindowActions.show_shortcuts_help

### Файл: ui\main_window\main_window_block_handler.py
- MainWindowBlockHandler.__init__
- MainWindowBlockHandler.get_block_color_markers
- MainWindowBlockHandler.toggle_block_color_marker
- MainWindowBlockHandler.rebuild_unsaved_block_indices

### Файл: ui\main_window\main_window_event_handler.py
- MainWindowEventHandler.__init__
- MainWindowEventHandler.connect_signals
- MainWindowEventHandler.keyPressEvent
- MainWindowEventHandler.closeEvent
- MainWindowEventHandler.handle_edited_cursor_position_changed
- MainWindowEventHandler.handle_edited_selection_changed

### Файл: ui\main_window\main_window_helper.py
- MainWindowHelper.__init__
- MainWindowHelper.get_font_map_for_string
- MainWindowHelper.restart_application
- MainWindowHelper.rebuild_unsaved_block_indices
- MainWindowHelper.execute_find_next_shortcut
- MainWindowHelper.execute_find_previous_shortcut
- MainWindowHelper.handle_panel_find_next
- MainWindowHelper.handle_panel_find_previous
- MainWindowHelper.toggle_search_panel
- MainWindowHelper.hide_search_panel
- MainWindowHelper.load_all_data_for_path
- MainWindowHelper.apply_text_wrap_settings
- MainWindowHelper.reconfigure_all_highlighters
- MainWindowHelper.prepare_to_close
- MainWindowHelper.restore_state_after_settings_load

### Файл: ui\main_window\main_window_plugin_handler.py
- MainWindowPluginHandler.__init__
- MainWindowPluginHandler.setup_plugin_ui
- MainWindowPluginHandler.load_game_plugin
- MainWindowPluginHandler._load_fallback_rules
- MainWindowPluginHandler.trigger_check_tags_action

### Файл: ui\main_window\main_window_ui_handler.py
- MainWindowUIHandler.__init__
- MainWindowUIHandler.update_editor_rules_properties
- MainWindowUIHandler.apply_font_size
- MainWindowUIHandler.apply_text_wrap_settings
- MainWindowUIHandler.reconfigure_all_highlighters
- MainWindowUIHandler.force_focus
- MainWindowUIHandler.apply_theme

### Файл: ui\settings\settings_ui_setup.py
- SettingsDialogUiMixin.setup_general_tab
- SettingsDialogUiMixin.setup_plugin_tab
- SettingsDialogUiMixin.rebuild_plugin_tabs
- SettingsDialogUiMixin.setup_spelling_tab
- SettingsDialogUiMixin._open_dictionary_manager
- SettingsDialogUiMixin.populate_spellchecker_languages
- SettingsDialogUiMixin._populate_font_list
- SettingsDialogUiMixin._setup_display_subtab
- SettingsDialogUiMixin.on_rules_changed
- SettingsDialogUiMixin._setup_rules_subtab
- SettingsDialogUiMixin._setup_context_tags_subtab
- SettingsDialogUiMixin._handle_table_double_click
- SettingsDialogUiMixin._show_table_context_menu
- SettingsDialogUiMixin._add_table_row
- SettingsDialogUiMixin._filter_tags_tables
- SettingsDialogUiMixin._remove_table_row
- SettingsDialogUiMixin._setup_paths_subtab
- SettingsDialogUiMixin._populate_checkbox_subtab
- SettingsDialogUiMixin._setup_detection_subtab
- SettingsDialogUiMixin._setup_autofix_subtab
- SettingsDialogUiMixin.on_provider_changed
- SettingsDialogUiMixin.setup_ai_translation_tab
- SettingsDialogUiMixin.setup_ai_glossary_tab
- SettingsDialogUiMixin._set_glossary_api_key_text
- SettingsDialogUiMixin._get_translation_credentials_for_glossary
- SettingsDialogUiMixin._update_glossary_api_key_controls
- SettingsDialogUiMixin._refresh_glossary_api_key_from_translation
- SettingsDialogUiMixin._on_glossary_use_translation_key_changed
- SettingsDialogUiMixin._on_glossary_provider_changed
- SettingsDialogUiMixin._on_glossary_api_key_changed
- SettingsDialogUiMixin.find_plugins
- SettingsDialogUiMixin.populate_plugin_list
- SettingsDialogUiMixin.setup_logging_tab
- SettingsDialogUiMixin.on_theme_changed
- SettingsDialogUiMixin.on_plugin_changed

### Файл: ui\settings\settings_widgets.py
- ColorPickerButton.__init__
- ColorPickerButton.color
- ColorPickerButton.setColor
- ColorPickerButton._update_style
- ColorPickerButton._get_contrasting_text_color
- ColorPickerButton.pick_color
- TagDisplayWidget.__init__
- TagDisplayWidget._update_btn_color
- TagDisplayWidget._pick_color
- TagDisplayWidget.text

### Файл: ui\settings_dialog.py
- SettingsDialog.__init__
- SettingsDialog._get_lang_name
- SettingsDialog._create_path_selector
- SettingsDialog._browse_for_file
- SettingsDialog.load_initial_settings
- SettingsDialog.get_settings
- SettingsDialog._get_tags_from_tables

### Файл: ui\ui_event_filters.py
- TextEditEventFilter.__init__
- TextEditEventFilter.eventFilter
- MainWindowEventFilter.__init__
- MainWindowEventFilter.eventFilter

### Файл: ui\ui_setup.py
- setup_main_window_ui

### Файл: ui\ui_updater.py
- UIUpdater.__init__
- UIUpdater.get_tree_state
- UIUpdater.apply_tree_state
- UIUpdater._get_item_id
- UIUpdater.highlight_glossary_occurrence
- UIUpdater._get_aggregated_problems_for_block
- UIUpdater._create_block_tree_item
- UIUpdater._add_virtual_folder_to_tree
- UIUpdater.populate_blocks
- UIUpdater.update_block_item_text_with_problem_count
- UIUpdater.update_status_bar
- UIUpdater.update_status_bar_selection
- UIUpdater.clear_status_bar
- UIUpdater.synchronize_original_cursor
- UIUpdater.highlight_problem_block
- UIUpdater.clear_all_problem_block_highlights_and_text
- UIUpdater.update_title
- UIUpdater.update_plugin_status_label
- UIUpdater.update_statusbar_paths
- UIUpdater._apply_highlights_for_block
- UIUpdater._apply_highlights_to_editor
- UIUpdater._get_all_categorized_indices_for_block
- UIUpdater.populate_strings_for_block
- UIUpdater.update_text_views

### Файл: ui\updaters\base_ui_updater.py
- BaseUIUpdater.__init__

### Файл: ui\updaters\block_list_updater.py
- BlockListUpdater.__init__
- BlockListUpdater.populate_blocks
- BlockListUpdater.update_block_item_text_with_problem_count
- BlockListUpdater.clear_all_problem_block_highlights_and_text

### Файл: ui\updaters\preview_updater.py
- PreviewUpdater.__init__
- PreviewUpdater.populate_strings_for_block

### Файл: ui\updaters\string_settings_updater.py
- StringSettingsUpdater.__init__
- StringSettingsUpdater.update_font_combobox
- StringSettingsUpdater.update_string_settings_panel

### Файл: ui\updaters\title_status_bar_updater.py
- TitleStatusBarUpdater.__init__
- TitleStatusBarUpdater.update_title
- TitleStatusBarUpdater.update_statusbar_paths

### Файл: utils\hotkey_manager.py
- HotkeyManager.__init__
- HotkeyManager.register
- HotkeyManager.unregister
- HotkeyManager.handle_native_event
- HotkeyManager._handle_repeat
- HotkeyManager._dispatch_hotkey

### Файл: utils\logging_utils.py
- DuplicateFilter.__init__
- DuplicateFilter.filter
- set_enabled_log_categories
- update_logger_handlers
- _should_log
- CategoryAdapter.process
- _log_message
- log_debug
- log_info
- log_warning
- log_error

### Файл: utils\syntax_highlighter.py
- JsonTagHighlighter.__init__
- JsonTagHighlighter.on_contents_change
- JsonTagHighlighter.set_glossary_manager
- JsonTagHighlighter.set_spellchecker_enabled
- JsonTagHighlighter._apply_css_to_format
- JsonTagHighlighter.reconfigure_styles
- JsonTagHighlighter._invalidate_icon_cache
- JsonTagHighlighter._rebuild_glossary_cache
- JsonTagHighlighter._ensure_icon_cache
- JsonTagHighlighter._get_icon_matches_for_block
- JsonTagHighlighter._get_icon_sequences
- JsonTagHighlighter._should_highlight_icons
- JsonTagHighlighter._should_check_spelling
- JsonTagHighlighter._extract_words_from_text
- JsonTagHighlighter.highlightBlock

### Файл: utils\utils.py
- remove_all_tags
- calculate_string_width
- calculate_strict_string_width
- is_fuzzy_match
- convert_spaces_to_dots_for_display
- convert_dots_to_spaces_from_editor
- remove_curly_tags
- convert_raw_to_display_text
- prepare_text_for_tagless_search

