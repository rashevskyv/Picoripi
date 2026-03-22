# handlers/list_selection_handler.py
from typing import Any, Optional, List, Dict, Union, Tuple
from PyQt5.QtWidgets import QInputDialog, QTextEdit, QTreeWidgetItemIterator, QTreeWidgetItem
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTextCursor, QTextBlockFormat, QColor, QTextBlock 
from .base_handler import BaseHandler
from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN

class ListSelectionHandler(BaseHandler):
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        super().__init__(main_window, data_processor, ui_updater)
        self._restoring_selection: bool = False
    def navigate_between_blocks(self, forward: bool) -> None:
        """Handle global Alt+Shift+Up/Down to jump to next/prev block in the tree."""
        if not hasattr(self.mw, 'block_list_widget'): return
        direction: int = 1 if forward else -1
        self.mw.block_list_widget.navigate_blocks(direction)

    def navigate_between_folders(self, forward: bool) -> None:
        """Handle global Alt+Shift+Left/Right to jump to next/prev folder in the tree."""
        log_debug(f"ListSelectionHandler: navigate_between_folders forward={forward}")
        if not hasattr(self.mw, 'block_list_widget'): return
        direction: int = 1 if forward else -1
        self.mw.block_list_widget.navigate_folders(direction)

    def block_selected(self, current_item: Optional[QTreeWidgetItem], previous_item: Optional[QTreeWidgetItem]) -> None:
        if self.mw.is_loading_data or self._restoring_selection:
            return

        if previous_item:
            previous_block_idx = previous_item.data(0, Qt.UserRole)
            if previous_block_idx is not None:
                self.ui_updater.update_block_item_text_with_problem_count(previous_block_idx)

        if not current_item:
            return

        old_block = self.mw.data_store.current_block_idx
        old_string = self.mw.data_store.current_string_idx
        old_category = getattr(self.mw, 'current_category_name', None)

        self.mw.is_programmatically_changing_text = True
        try:
            block_index = current_item.data(0, Qt.UserRole)
            category_name = current_item.data(0, Qt.UserRole + 10)
            
            if block_index is None:
                self.mw.data_store.current_block_idx = -1
                self.mw.data_store.current_string_idx = -1
                self.mw.data_store.current_category_name = None
                self.ui_updater.populate_strings_for_block(-1)
                if hasattr(self.mw, 'string_settings_updater'):
                    self.mw.string_settings_updater.update_string_settings_panel()
                self._update_block_toolbar_button_states(-1)
                return

            if self.mw.data_store.current_block_idx != block_index or self.mw.data_store.current_category_name != category_name:
                self.mw.data_store.current_block_idx = block_index
                self.mw.data_store.current_category_name = category_name
                
                # Restore selection logic
                target_string_idx = -1
                if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                    project = self.mw.project_manager.project
                    if hasattr(self.mw, 'block_to_project_file_map'):
                         project_block_idx = self.mw.block_to_project_file_map.get(block_index)
                         if project_block_idx is not None and project_block_idx < len(project.blocks):
                             target_string_idx = project.blocks[project_block_idx].last_selected_string_idx
                
                self.mw.data_store.current_string_idx = target_string_idx
                
                if hasattr(self.mw, 'undo_manager'):
                    # Navigation recording
                    self.mw.undo_manager.record_navigation(
                        block_index, target_string_idx, 
                        old_block, old_string,
                        category_name, old_category
                    )

                self.ui_updater.populate_strings_for_block(block_index, category_name)
                
                if target_string_idx != -1:
                    rel_idx = -1
                    if hasattr(self.mw, 'displayed_string_indices') and target_string_idx in self.mw.data_store.displayed_string_indices:
                        rel_idx = self.mw.data_store.displayed_string_indices.index(target_string_idx)
                    
                    if rel_idx != -1:
                        # Schedule selection to avoid recursion issues
                        from PyQt5.QtCore import QTimer
                        QTimer.singleShot(0, lambda ridx=rel_idx: self.string_selected_from_preview(ridx))
                else:
                    self.ui_updater.update_text_views()
                    if hasattr(self.mw, 'string_settings_updater'):
                        self.mw.string_settings_updater.update_string_settings_panel()
                
                self.ui_updater.update_statusbar_paths()
                self.ui_updater.update_block_item_text_with_problem_count(block_index)

            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_font_combobox()
                self.mw.string_settings_updater.update_string_settings_panel()

            self._update_block_toolbar_button_states(block_index)
        finally:
            self.mw.is_programmatically_changing_text = False

    def _restore_block_selection(self) -> None:
        if self.mw.data_store.current_block_idx != -1:
            iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
            while iterator.value():
                if iterator.value().data(0, Qt.UserRole) == self.mw.data_store.current_block_idx:
                    self.mw.block_list_widget.setCurrentItem(iterator.value())
                    break
                iterator += 1
        self._restoring_selection = False

    def _update_block_toolbar_button_states(self, block_idx: int):
        """Update the enabled/disabled state of toolbar buttons based on selection and position."""
        has_project = bool(hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project)
        
        # Enable Add Folder if project exists
        if hasattr(self.mw, 'add_folder_button'):
            self.mw.add_folder_button.setEnabled(has_project)

        current_item = self.mw.block_list_widget.currentItem()
        if has_project and current_item:
            parent = current_item.parent() or self.mw.block_list_widget.invisibleRootItem()
            index = parent.indexOfChild(current_item)
            is_first = index == 0
            is_last = index == parent.childCount() - 1

            # Enable delete and rename for any selected block or folder
            if hasattr(self.mw, 'delete_block_button'):
                self.mw.delete_block_button.setEnabled(True)
            if hasattr(self.mw, 'rename_block_button'):
                self.mw.rename_block_button.setEnabled(True)

            # Enable move up/down based on siblings in the tree
            if hasattr(self.mw, 'move_block_up_button'):
                self.mw.move_block_up_button.setEnabled(not is_first)
            if hasattr(self.mw, 'move_block_down_button'):
                self.mw.move_block_down_button.setEnabled(not is_last)
        else:
            # Disable selection-dependent buttons
            if hasattr(self.mw, 'delete_block_button'):
                self.mw.delete_block_button.setEnabled(False)
            if hasattr(self.mw, 'rename_block_button'):
                self.mw.rename_block_button.setEnabled(False)
            if hasattr(self.mw, 'move_block_up_button'):
                self.mw.move_block_up_button.setEnabled(False)
            if hasattr(self.mw, 'move_block_down_button'):
                self.mw.move_block_down_button.setEnabled(False)


    def select_string_by_absolute_index(self, absolute_idx: int) -> None:
        """Select a string using its absolute index in block data, handling relative mapping automatically."""
        if absolute_idx == -1: return

        rel_idx: int = -1
        if hasattr(self.mw, 'displayed_string_indices') and absolute_idx in self.mw.data_store.displayed_string_indices:
            rel_idx = self.mw.data_store.displayed_string_indices.index(absolute_idx)
        else:
            rel_idx = absolute_idx # Fallback if no mapping exists

        # If strings are not yet populated (e.g. initial load), displayed_string_indices might be empty.
        # string_selected_from_preview will handle further validation.
        self.string_selected_from_preview(rel_idx)

    def string_selected_from_preview(self, line_number: int, is_manual_click: bool = False) -> None:
        preview_edit = getattr(self.mw, 'preview_text_edit', None)

        original_programmatic_state = self.mw.is_programmatically_changing_text
        self.mw.is_programmatically_changing_text = True

        # Translate relative preview line_number to absolute data index
        real_idx = line_number
        if hasattr(self.mw, 'displayed_string_indices') and self.mw.data_store.displayed_string_indices:
            if 0 <= line_number < len(self.mw.data_store.displayed_string_indices):
                real_idx = self.mw.data_store.displayed_string_indices[line_number]
            else:
                real_idx = -1

        if self.mw.data_store.current_block_idx == -1 or real_idx == -1:
            self.mw.data_store.current_string_idx = -1
            if preview_edit and hasattr(preview_edit, 'highlightManager'):
                 preview_edit.highlightManager.clearPreviewSelectedLineHighlight()
            self.ui_updater.update_text_views()
            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_string_settings_panel()
            self.mw.is_programmatically_changing_text = original_programmatic_state
            return

        is_valid_line = False
        if 0 <= self.mw.data_store.current_block_idx < len(self.mw.data_store.data) and \
           isinstance(self.mw.data_store.data[self.mw.data_store.current_block_idx], list) and \
           0 <= real_idx < len(self.mw.data_store.data[self.mw.data_store.current_block_idx]):
            is_valid_line = True
        
        previous_string_idx = self.mw.data_store.current_string_idx
        
        if not is_valid_line:
            self.mw.data_store.current_string_idx = -1
            if preview_edit and hasattr(preview_edit, 'highlightManager'):
                preview_edit.highlightManager.clearPreviewSelectedLineHighlight()
        else:
            self.mw.data_store.current_string_idx = real_idx
            self.mw.data_store.edited_sublines.clear() # Clear editor sublines on line change
            
            # Restore subline asterisks if the selected line has unsaved changes in memory
            if (self.mw.data_store.current_block_idx, real_idx) in self.mw.data_store.edited_data:
                current_text = self.mw.data_store.edited_data[(self.mw.data_store.current_block_idx, real_idx)]
                if hasattr(self.mw, 'text_operation_handler'):
                    self.mw.text_operation_handler.sync_subline_asterisks(
                        self.mw.data_store.current_block_idx, real_idx, current_text
                    )

            if hasattr(self.mw, 'undo_manager') and not original_programmatic_state:
                cat = getattr(self.mw, 'current_category_name', None)
                self.mw.undo_manager.record_navigation(
                    self.mw.data_store.current_block_idx, real_idx, 
                    self.mw.data_store.current_block_idx, previous_string_idx,
                    cat, cat
                )

            if previous_string_idx != self.mw.data_store.current_string_idx and previous_string_idx != -1:
                self.ui_updater.update_block_item_text_with_problem_count(self.mw.data_store.current_block_idx)
            
            self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, getattr(self.mw, 'current_category_name', None)) 
            
            # Save selection to project
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                project = self.mw.project_manager.project
                if hasattr(self.mw, 'block_to_project_file_map'):
                    project_block_idx = self.mw.block_to_project_file_map.get(self.mw.data_store.current_block_idx)
                    if project_block_idx is not None and project_block_idx < len(project.blocks):
                        project.blocks[project_block_idx].last_selected_string_idx = real_idx

        self.ui_updater.update_text_views()
        if hasattr(self.mw, 'string_settings_updater'):
            self.mw.string_settings_updater.update_string_settings_panel()

        self.mw.is_programmatically_changing_text = original_programmatic_state

        if preview_edit and self.mw.data_store.current_string_idx != -1 and \
           0 <= self.mw.data_store.current_string_idx < len(self.mw.data_store.data[self.mw.data_store.current_block_idx]):
            
            # Find relative index for preview
            rel_idx = -1
            if hasattr(self.mw, 'displayed_string_indices') and self.mw.data_store.current_string_idx in self.mw.data_store.displayed_string_indices:
                rel_idx = self.mw.data_store.displayed_string_indices.index(self.mw.data_store.current_string_idx)

            if rel_idx != -1 and hasattr(preview_edit, 'set_selected_lines'): 
                preview_edit.set_selected_lines([rel_idx])
            
            if rel_idx != -1:
                block_to_show = preview_edit.document().findBlockByNumber(rel_idx)
                if block_to_show.isValid():
                    cursor = QTextCursor(block_to_show)
                    preview_edit.setTextCursor(cursor)
                    # Use a small timer to ensure the widget has finished layout after potential text updates
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(10, lambda: preview_edit.ensureCursorVisible())
        elif preview_edit and hasattr(preview_edit, 'highlightManager'): 
            preview_edit.highlightManager.clearPreviewSelectedLineHighlight()
            
        if self.mw.data_store.current_string_idx != -1 and hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
            self.mw.edited_text_edit.setFocus()
            cursor = self.mw.edited_text_edit.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.mw.edited_text_edit.setTextCursor(cursor)


    def rename_block(self, item: QTreeWidgetItem) -> None:
        if not item: return
        self.mw.block_list_widget.editItem(item, 0)

    def handle_block_item_text_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle inline renaming of block or folder."""
        if self.mw.is_loading_data or self.mw.is_programmatically_changing_text:
            return
            
        new_text = item.text(column).strip()
        if not new_text:
            # Revert if empty
            self.ui_updater.populate_blocks()
            return

        # Check if it's a virtual folder or a block
        folder_id = item.data(0, Qt.UserRole + 1)
        block_index_from_data = item.data(0, Qt.UserRole)
        merged_ids = item.data(0, Qt.UserRole + 2)

        undo_mgr = getattr(self.mw, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None

        # Check if it's a virtual block (category). Virtual blocks have BOTH block_index AND category_name set.
        # We must check category_name FIRST because virtual block items also have a block_index.
        category_name = item.data(0, Qt.UserRole + 10)
        
        self.mw.is_programmatically_changing_text = True
        try:
            if category_name is not None and block_index_from_data is not None:
                # Rename Virtual Block (Category) — delegate to the proper method
                log_debug(f"Virtual block '{category_name}' renamed to '{new_text}' (via inline edit)")
                pm = getattr(self.mw, 'project_manager', None)
                block_map = getattr(self.mw, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_index_from_data, block_index_from_data)
                if pm and proj_b_idx < len(pm.project.blocks):
                    block = pm.project.blocks[proj_b_idx]
                    for cat in block.categories:
                        if cat.name == category_name:
                            cat.name = new_text.strip()
                            break
                    pm.save()
                    self.ui_updater.populate_blocks()
            elif block_index_from_data is not None:
                # Rename Block
                block_index_str = str(block_index_from_data)
                
                # If there are merged IDs (compact folders), handle multi-part rename
                if merged_ids and " / " in new_text:
                    parts = new_text.split(" / ")
                    actual_block_name = parts[-1].strip()
                    self.mw.data_store.block_names[block_index_str] = actual_block_name
                    
                    # Rename parent folders in the chain
                    folder_names = parts[:-1]
                    for f_idx, f_id in enumerate(merged_ids):
                        folder_obj = self.mw.project_manager.find_virtual_folder(f_id)
                        if folder_obj and folder_names:
                            name_idx = len(folder_names) - 1 - (len(merged_ids) - 1 - f_idx)
                            if name_idx >= 0:
                                import re
                                raw_name = folder_names[name_idx].strip()
                                # Strip the display count [f / b]
                                new_name = re.sub(r'\s*\[\d+\s*/\s*\d+\]$', '', raw_name)
                                # Check for collision with siblings of this folder in the chain
                                siblings = []
                                if folder_obj.parent_id:
                                    p = self.mw.project_manager.find_virtual_folder(folder_obj.parent_id)
                                    if p: siblings = p.children
                                else:
                                    siblings = self.mw.project_manager.project.virtual_folders
                                
                                collision = None
                                for s in siblings:
                                    if s.id != folder_obj.id and s.name == new_name:
                                        collision = s
                                        break
                                
                                if collision:
                                    self.mw.project_manager.merge_folders(folder_obj.id, collision.id)
                                else:
                                    folder_obj.name = new_name
                else:
                    self.mw.data_store.block_names[block_index_str] = new_text
                
                self.mw.settings_manager.save_block_names()
                log_debug(f"Block {block_index_from_data} renamed to '{new_text}'")
            elif folder_id:
                # Rename Folder
                folder = self.mw.project_manager.find_virtual_folder(folder_id)
                if folder:
                    if merged_ids and " / " in new_text:
                        parts = new_text.split(" / ")
                        for f_idx, f_id in enumerate(merged_ids):
                            f_obj = self.mw.project_manager.find_virtual_folder(f_id)
                            if f_obj:
                                name_idx = len(parts) - 1 - (len(merged_ids) - 1 - f_idx)
                                if name_idx >= 0:
                                    import re
                                    raw_name = parts[name_idx].strip()
                                    # Strip the display count [f / b]
                                    new_name = re.sub(r'\s*\[\d+\s*/\s*\d+\]$', '', raw_name)
                                    # Merge if collision
                                    siblings = []
                                    if f_obj.parent_id:
                                        p = self.mw.project_manager.find_virtual_folder(f_obj.parent_id)
                                        if p: siblings = p.children
                                    else:
                                        siblings = self.mw.project_manager.project.virtual_folders
                                    
                                    collision = None
                                    for s in siblings:
                                        if s.id != f_obj.id and s.name == new_name:
                                            collision = s
                                            break
                                    if collision:
                                        self.mw.project_manager.merge_folders(f_obj.id, collision.id)
                                    else:
                                        f_obj.name = new_name
                    else:
                        import re
                        raw_input = new_text.strip()
                        new_name = re.sub(r'\s*\[\d+\s*/\s*\d+\]$', '', raw_input)
                        # Check for collision at same level
                        siblings = []
                        if folder.parent_id:
                            p_obj = self.mw.project_manager.find_virtual_folder(folder.parent_id)
                            if p_obj: siblings = p_obj.children
                        else:
                            siblings = self.mw.project_manager.project.virtual_folders
                        
                        target_collision = None
                        for s in siblings:
                            if s.id != folder.id and s.name == new_name:
                                target_collision = s
                                break
                        
                        if target_collision:
                            # MERGE CASE: Rename to existing folder name
                            log_info(f"Renaming '{folder.name}' to existing '{new_name}' -> merging {folder.id} into {target_collision.id}")
                            self.mw.project_manager.merge_folders(folder.id, target_collision.id)
                        else:
                            folder.name = new_name
                            
                    self.mw.project_manager.save()
                    log_debug(f"Folder {folder_id} rename/merge handled.")
            
            # Repopulate to fix any visual issues
            self.ui_updater.populate_blocks()
        finally:
            self.mw.is_programmatically_changing_text = False

        if undo_mgr and before is not None:
            action_label = f"Rename block to '{new_text}'" if block_index_from_data is not None else f"Rename folder to '{new_text}'"
            action_type = 'RENAME_BLOCK' if block_index_from_data is not None else 'RENAME_FOLDER'
            undo_mgr.record_structural_action(before, action_type, action_label)

    def _data_string_has_any_problem(self, block_idx: int, string_idx: int) -> bool:
        if not self.mw.current_game_rules:
            return False

        data_string_text, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        if data_string_text is None:
            return False
            
        num_sublines = str(data_string_text).count('\n') + 1
        
        detection_config = getattr(self.mw, 'detection_enabled', {})
        
        for i in range(num_sublines):
            key = (block_idx, string_idx, i)
            if key in self.mw.data_store.problems_per_subline:
                problems = self.mw.data_store.problems_per_subline[key]
                if any(detection_config.get(p_id, True) for p_id in problems):
                    return True
                    
        return False

    def navigate_to_problem_string(self, direction_down: bool):
        if self.mw.data_store.current_block_idx == -1 or not self.mw.data_store.data or \
           not (0 <= self.mw.data_store.current_block_idx < len(self.mw.data_store.data)):
            return

        current_block_data = self.mw.data_store.data[self.mw.data_store.current_block_idx]
        if not isinstance(current_block_data, list) or not current_block_data:
            return

        num_strings_in_block = len(current_block_data)
        start_scan_idx = self.mw.data_store.current_string_idx
        log_debug(f"[NAV] Start navigation. Direction down: {direction_down}, current_string_idx: {start_scan_idx}")
        
        current_check_idx = -1
        if start_scan_idx == -1: 
            current_check_idx = 0 if direction_down else num_strings_in_block - 1
        else: 
             current_check_idx = (start_scan_idx + 1) if direction_down else (start_scan_idx - 1)

        original_programmatic_state = self.mw.is_programmatically_changing_text
        self.mw.is_programmatically_changing_text = True

        found_target_s_idx = -1

        if direction_down:
            for s_idx in range(current_check_idx, num_strings_in_block):
                if self._data_string_has_any_problem(self.mw.data_store.current_block_idx, s_idx):
                    found_target_s_idx = s_idx
                    break
            if found_target_s_idx == -1: 
                for s_idx in range(0, current_check_idx if start_scan_idx != -1 else num_strings_in_block): 
                    if self._data_string_has_any_problem(self.mw.data_store.current_block_idx, s_idx):
                        found_target_s_idx = s_idx
                        break
        else: 
            for s_idx in range(current_check_idx, -1, -1):
                if self._data_string_has_any_problem(self.mw.data_store.current_block_idx, s_idx):
                    found_target_s_idx = s_idx
                    break
            if found_target_s_idx == -1: 
                for s_idx in range(num_strings_in_block - 1, current_check_idx if start_scan_idx != -1 else -1, -1): 
                    if self._data_string_has_any_problem(self.mw.data_store.current_block_idx, s_idx):
                        found_target_s_idx = s_idx
                        break
        
        if found_target_s_idx != -1:
            log_debug(f"[NAV] Found target string at index: {found_target_s_idx}")
            self.string_selected_from_preview(found_target_s_idx)
        else:
            log_debug("[NAV] No problem string found in current search.")
            if start_scan_idx != -1 and self._data_string_has_any_problem(self.mw.data_store.current_block_idx, start_scan_idx):
                 self.string_selected_from_preview(start_scan_idx)

            self.mw.is_programmatically_changing_text = original_programmatic_state

    def handle_preview_selection_changed(self, selected_lines: Optional[List[int]] = None) -> None:
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit or not preview_edit.hasFocus() or self.mw.is_programmatically_changing_text:
            return
            
        if selected_lines is None:
            cursor = preview_edit.textCursor()
            if not cursor.hasSelection():
                if self.mw.data_store.current_string_idx != -1:
                    if hasattr(preview_edit, 'set_selected_lines'):
                        preview_edit.set_selected_lines([self.mw.data_store.current_string_idx])
                return

            start_pos = cursor.selectionStart()
            end_pos = cursor.selectionEnd()
            
            start_block = self.mw.preview_text_edit.document().findBlock(start_pos)
            end_block = self.mw.preview_text_edit.document().findBlock(end_pos)
            
            start_line = start_block.blockNumber()
            end_line = end_block.blockNumber()
            
            if end_pos > start_pos and end_pos == end_block.position() and start_block.blockNumber() != end_block.blockNumber():
                end_line -= 1
                
            if end_line < start_line:
                end_line = start_line

            selected_lines = list(range(start_line, end_line + 1))
        
        # Translate rel to abs
        abs_indices = []
        if hasattr(self.mw, 'displayed_string_indices') and self.mw.data_store.displayed_string_indices:
            for rel in selected_lines:
                if 0 <= rel < len(self.mw.data_store.displayed_string_indices):
                    abs_indices.append(self.mw.data_store.displayed_string_indices[rel])
        else:
            abs_indices = selected_lines
            
        # Save to app state
        self.mw.data_store.selected_string_indices = abs_indices
        
        # If only one selected, update current_string_idx
        if len(abs_indices) == 1:
            target_idx = abs_indices[0]
            if self.mw.data_store.current_string_idx != target_idx:
                # Update current_string_idx so other views follow
                self.mw.data_store.current_string_idx = target_idx
                self.ui_updater.update_text_views()
                if hasattr(self.mw, 'string_settings_updater'):
                    self.mw.string_settings_updater.update_string_settings_panel()

        if preview_edit and hasattr(preview_edit, 'set_selected_lines'):
            preview_edit.set_selected_lines(selected_lines)

    def move_selection_to_category(self) -> None:
        """Move selected strings to a virtual block (Category)."""
        selected_indices = getattr(self.mw, 'selected_string_indices', [])
        if not selected_indices:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self.mw, "Move to Virtual Block", "No strings selected in preview.")
            return
        
        if self.mw.data_store.current_block_idx == -1:
            return
            
        pm = self.mw.project_manager
        if not pm or not pm.project:
             log_debug("No project loaded, cannot create virtual blocks.")
             return
             
        # Find the project block index
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(self.mw.data_store.current_block_idx, self.mw.data_store.current_block_idx)
        if proj_b_idx >= len(pm.project.blocks):
            return
            
        block = pm.project.blocks[proj_b_idx]
        
        # Get existing categories names
        existing_names = [c.name for c in block.categories]
        
        # Simple input dialog for now
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self.mw, "Move to Virtual Block", "Enter Category Name:", text="New Category")
        if not ok or not name.strip():
            return
            
        pm.move_strings_to_category(proj_b_idx, selected_indices, name.strip())
        
        # Update UI
        self.ui_updater.populate_blocks()
        self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, self.mw.data_store.current_category_name)
        
        # Re-select the block to show the new category (if we implement category display)
        # For now, just logging
        log_debug(f"Moved {len(selected_indices)} strings to Category '{name}' in Block {proj_b_idx}")

    def rename_category(self, block_idx: int, old_name: str) -> None:
        """Rename a virtual block."""
        from PyQt5.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self.mw, "Rename Virtual Block", "Enter new name:", text=old_name)
        if not ok or not new_name.strip() or new_name == old_name:
            return
            
        pm = self.mw.project_manager
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)
        
        if proj_b_idx < len(pm.project.blocks):
            block = pm.project.blocks[proj_b_idx]
            for cat in block.categories:
                if cat.name == old_name:
                    cat.name = new_name.strip()
                    break
            pm.save()
            self.ui_updater.populate_blocks()

    def delete_category(self, block_idx: int, category_name: str) -> None:
        """Remove a virtual block (the strings remain in the block)."""
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(self.mw, "Delete Virtual Block", f"Are you sure you want to delete virtual block '{category_name}'?\n\n(Strings will not be deleted from the block itself.)", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
            
        pm = self.mw.project_manager
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)
        
        if proj_b_idx < len(pm.project.blocks):
            block = pm.project.blocks[proj_b_idx]
            block.categories = [c for c in block.categories if c.name != category_name]
            pm.save()
            self.ui_updater.populate_blocks()


    def toggle_highlight_categorized(self, checked: bool) -> None:
        """Toggle highlighting of categorized strings in parent block."""
        self.mw.data_store.highlight_categorized = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, self.mw.data_store.current_category_name)

    def toggle_hide_categorized(self, checked: bool) -> None:
        """Toggle hiding of categorized strings in parent block."""
        self.mw.data_store.hide_categorized = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, self.mw.data_store.current_category_name)
