# handlers/list_selection_handler.py
from typing import Any, Optional, List, Dict, Union, Tuple
from PyQt6.QtWidgets import QInputDialog, QTextEdit, QTreeWidgetItemIterator, QTreeWidgetItem, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor, QTextBlockFormat, QColor, QTextBlock 
from .base_handler import BaseHandler
from utils.logging_utils import log_debug, log_info, log_error
from utils.utils import calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN

class ListSelectionHandler(BaseHandler):
    """Handler for list selection operations."""
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor, ui_updater)
        self._restoring_selection: bool = False
        self._target_string_idx: Optional[int] = None
        self._target_block_idx: Optional[int] = None
        self._pending_speaker_retention: Optional[Tuple[str, Tuple[int, int], int]] = None
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
        """Block selected."""
        try:
            from PyQt6 import sip
        except ImportError:
            import sip

        try:
            if current_item and sip.isdeleted(current_item):
                current_item = None
        except (TypeError, RuntimeError):
            pass

        try:
            if previous_item and sip.isdeleted(previous_item):
                previous_item = None
        except (TypeError, RuntimeError):
            pass

        if self.mw.is_loading_data or self._restoring_selection:
            return
 
        if hasattr(self.mw, 'editor_operation_handler'):
            self.mw.editor_operation_handler.stop_and_flush_editor_changes()
 
        if previous_item:
            try:
                previous_block_idx = previous_item.data(0, Qt.UserRole)
                if previous_block_idx is not None:
                    self.ui_updater.update_block_item_text_with_problem_count(previous_block_idx)
            except RuntimeError:
                pass
 
        if not current_item:
            return
 
        old_block = self.mw.data_store.current_block_idx
        old_string = self.mw.data_store.current_string_idx
        old_category = getattr(self.mw.data_store, 'current_category_name', None)
 
        self.mw.is_programmatically_changing_text = True
        try:
            is_virtual_row = current_item.data(0, Qt.UserRole + 12)
            if is_virtual_row:
                b_idx = current_item.data(0, Qt.UserRole)
                s_idx = current_item.data(0, Qt.UserRole + 1)
                ch_id = current_item.data(0, Qt.UserRole + 11)
                self._clear_pending_speaker_retention((b_idx, s_idx))
                
                self.mw.data_store.current_block_idx = b_idx
                self.mw.data_store.current_string_idx = s_idx
                self.mw.data_store.current_chapter_id = ch_id
                self.mw.data_store.current_category_name = None
                self.mw.data_store.current_speaker_name = None
                
                # Fetch mappings from MemePalace client
                chapter_mappings = []
                composer = getattr(self.mw, "translation_handler", None)
                if composer and hasattr(composer, "prompt_composer"):
                    client = composer.prompt_composer._get_mempalace_client()
                    if client:
                        wing_name = composer.prompt_composer._get_wing_name()
                        mappings = client.get_chapter_mappings(wing_name, ch_id)
                        for m in mappings:
                            bmg_id = m.get("bmg_id")
                            indices = self.resolve_bmg_id_to_indices(bmg_id)
                            if indices:
                                chapter_mappings.append(indices)
                self.mw.data_store.chapter_mappings = chapter_mappings
                
                self.ui_updater.populate_strings_for_block(-2)
                
                # Find relative index for preview
                rel_idx = -1
                displayed_indices = self._get_displayed_indices()
                target_tuple = (b_idx, s_idx)
                if target_tuple in displayed_indices:
                    rel_idx = displayed_indices.index(target_tuple)
                
                if rel_idx != -1:
                    if not getattr(self.mw, '_restoring_session_state', False):
                        QTimer.singleShot(0, lambda ridx=rel_idx: self.string_selected_from_preview(ridx))
                else:
                    self.ui_updater.update_text_views()
                    
                self.ui_updater.update_statusbar_paths()
                self._update_block_toolbar_button_states(-2)
                return
 
            block_index = current_item.data(0, Qt.UserRole)
            category_name = current_item.data(0, Qt.UserRole + 10)
            chapter_id = current_item.data(0, Qt.UserRole + 11)
            
            if block_index == -3:
                # Speaker item selected
                char_name = current_item.data(0, Qt.UserRole + 15)
                pending = self._pending_speaker_retention
                if not pending or pending[0] != char_name:
                    self._clear_pending_speaker_retention()

                self.mw.data_store.current_block_idx = -3
                self.mw.data_store.current_category_name = None
                self.mw.data_store.current_chapter_id = None
                
                self.mw.data_store.current_speaker_name = char_name
                
                # Retrieve pre-calculated mappings from the tree item
                char_mappings = current_item.data(0, Qt.UserRole + 13) or []
                self.mw.data_store.chapter_mappings = char_mappings
                
                self.ui_updater.populate_strings_for_block(-3)
                
                if char_mappings:
                    target_idx = -1
                    if self._target_string_idx is not None and self._target_block_idx is not None:
                        target_tuple = (self._target_block_idx, self._target_string_idx)
                        if target_tuple in char_mappings:
                            target_idx = char_mappings.index(target_tuple)
                            
                    if target_idx != -1:
                        first_mapping = char_mappings[target_idx]
                        self.mw.data_store.physical_block_idx = first_mapping[0]
                        self.mw.data_store.current_string_idx = first_mapping[1]
                        self._target_block_idx = None
                        self._target_string_idx = None
                        if not getattr(self.mw, '_restoring_session_state', False):
                            QTimer.singleShot(0, lambda ridx=target_idx: self.string_selected_from_preview(ridx))
                    else:
                        first_mapping = char_mappings[0]
                        self.mw.data_store.physical_block_idx = first_mapping[0]
                        self.mw.data_store.current_string_idx = first_mapping[1]
                        if not getattr(self.mw, '_restoring_session_state', False):
                            QTimer.singleShot(0, lambda: self.string_selected_from_preview(0))
                else:
                    self.mw.data_store.physical_block_idx = -1
                    self.mw.data_store.current_string_idx = -1
                    self.ui_updater.update_text_views()
                    
                self.ui_updater.update_statusbar_paths()
                self._update_block_toolbar_button_states(-3)
                return

            if chapter_id is not None:
                # Chapter item selected
                self._clear_pending_speaker_retention()
                self.mw.data_store.current_block_idx = -2
                self.mw.data_store.current_category_name = None
                self.mw.data_store.current_chapter_id = chapter_id
                self.mw.data_store.current_speaker_name = None
                
                # Fetch mappings from MemePalace client
                chapter_mappings = []
                composer = getattr(self.mw, "translation_handler", None)
                if composer and hasattr(composer, "prompt_composer"):
                    client = composer.prompt_composer._get_mempalace_client()
                    if client:
                        wing_name = composer.prompt_composer._get_wing_name()
                        mappings = client.get_chapter_mappings(wing_name, chapter_id)
                        for m in mappings:
                            bmg_id = m.get("bmg_id")
                            indices = self.resolve_bmg_id_to_indices(bmg_id)
                            if indices:
                                chapter_mappings.append(indices)
                self.mw.data_store.chapter_mappings = chapter_mappings
                
                self.ui_updater.populate_strings_for_block(-2)
                
                if chapter_mappings:
                    target_idx = -1
                    if self._target_string_idx is not None and self._target_block_idx is not None:
                        target_tuple = (self._target_block_idx, self._target_string_idx)
                        if target_tuple in chapter_mappings:
                            target_idx = chapter_mappings.index(target_tuple)
                            
                    if target_idx != -1:
                        first_mapping = chapter_mappings[target_idx]
                        self.mw.data_store.physical_block_idx = first_mapping[0]
                        self.mw.data_store.current_string_idx = first_mapping[1]
                        self._target_block_idx = None
                        self._target_string_idx = None
                        if not getattr(self.mw, '_restoring_session_state', False):
                            QTimer.singleShot(0, lambda ridx=target_idx: self.string_selected_from_preview(ridx))
                    else:
                        first_mapping = chapter_mappings[0]
                        self.mw.data_store.physical_block_idx = first_mapping[0]
                        self.mw.data_store.current_string_idx = first_mapping[1]
                        if not getattr(self.mw, '_restoring_session_state', False):
                            QTimer.singleShot(0, lambda: self.string_selected_from_preview(0))
                else:
                    self.mw.data_store.physical_block_idx = -1
                    self.mw.data_store.current_string_idx = -1
                    self.ui_updater.update_text_views()
                    
                self.ui_updater.update_statusbar_paths()
                self._update_block_toolbar_button_states(-2)
                return
 
            if block_index is None:
                self._clear_pending_speaker_retention()
                self.mw.data_store.current_block_idx = -1
                self.mw.data_store.physical_block_idx = -1
                self.mw.data_store.current_string_idx = -1
                self.mw.data_store.current_category_name = None
                self.mw.data_store.current_chapter_id = None
                self.mw.data_store.current_speaker_name = None
                self.mw.data_store.chapter_mappings = []
                self.ui_updater.populate_strings_for_block(-1)
                if hasattr(self.mw, 'string_settings_updater'):
                    self.mw.string_settings_updater.update_string_settings_panel()
                self._update_block_toolbar_button_states(-1)
                return
 
            if self.mw.data_store.current_block_idx != block_index or self.mw.data_store.current_category_name != category_name or type(self.mw.data_store.current_chapter_id) is int or isinstance(getattr(self.mw.data_store, 'current_speaker_name', None), str):
                self._clear_pending_speaker_retention()
                self.mw.data_store.current_block_idx = block_index
                self.mw.data_store.physical_block_idx = block_index
                self.mw.data_store.current_category_name = category_name
                self.mw.data_store.current_chapter_id = None
                self.mw.data_store.current_speaker_name = None
                self.mw.data_store.chapter_mappings = []
                
                # Restore selection logic
                target_string_idx = -1
                if self._target_string_idx is not None and (self._target_block_idx is None or self._target_block_idx == block_index):
                    target_string_idx = self._target_string_idx
                else:
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
                    displayed_indices = self._get_displayed_indices()
                    if target_string_idx in displayed_indices:
                        rel_idx = displayed_indices.index(target_string_idx)
                    
                    if rel_idx != -1:
                        # Schedule selection to avoid recursion issues
                        if not getattr(self.mw, '_restoring_session_state', False):
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
        
        if not getattr(self.mw, 'is_loading_data', False) and not self._restoring_selection:
            self.data_processor.schedule_autosave()

    def _restore_block_selection(self) -> None:
        """Internal helper to restore block selection."""
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
            self.mw.add_folder_button.setToolTip(
                "Create new virtual folder" if has_project
                else "Creating folders is only available in Project mode (within a .uiproj project)."
            )

        current_item = self.mw.block_list_widget.currentItem()
        is_chapter = False
        if current_item:
            role_val = current_item.data(0, Qt.UserRole)
            ch_val = current_item.data(0, Qt.UserRole + 11)
            if isinstance(role_val, int):
                is_chapter = (role_val == -2 or ch_val is not None)

        if has_project and current_item and not is_chapter:
            parent = current_item.parent() or self.mw.block_list_widget.invisibleRootItem()
            index = parent.indexOfChild(current_item)
            is_first = index == 0
            is_last = index == parent.childCount() - 1

            # Enable delete and rename for any selected block or folder
            if hasattr(self.mw, 'delete_block_button'):
                self.mw.delete_block_button.setEnabled(True)
                self.mw.delete_block_button.setToolTip("Delete selected block or folder")
            if hasattr(self.mw, 'rename_block_button'):
                self.mw.rename_block_button.setEnabled(True)
                self.mw.rename_block_button.setToolTip("Rename selected block or folder")

            # Enable move up/down based on siblings in the tree
            if hasattr(self.mw, 'move_block_up_button'):
                self.mw.move_block_up_button.setEnabled(not is_first)
                self.mw.move_block_up_button.setToolTip(
                    "Move block or folder up" if not is_first
                    else "Cannot move up: item is already at the top of its folder"
                )
            if hasattr(self.mw, 'move_block_down_button'):
                self.mw.move_block_down_button.setEnabled(not is_last)
                self.mw.move_block_down_button.setToolTip(
                    "Move block or folder down" if not is_last
                    else "Cannot move down: item is already at the bottom of its folder"
                )
        else:
            # Disable selection-dependent buttons
            proj_tip = "only available in Project mode (within a .uiproj project)."
            select_tip = "Select a block or folder to enable this action."
            
            if hasattr(self.mw, 'delete_block_button'):
                self.mw.delete_block_button.setEnabled(False)
                self.mw.delete_block_button.setToolTip(
                    f"Deleting items is {proj_tip}" if not has_project else select_tip
                )
            if hasattr(self.mw, 'rename_block_button'):
                self.mw.rename_block_button.setEnabled(False)
                self.mw.rename_block_button.setToolTip(
                    f"Renaming items is {proj_tip}" if not has_project else select_tip
                )
            if hasattr(self.mw, 'move_block_up_button'):
                self.mw.move_block_up_button.setEnabled(False)
                self.mw.move_block_up_button.setToolTip(
                    f"Moving items is {proj_tip}" if not has_project else select_tip
                )
            if hasattr(self.mw, 'move_block_down_button'):
                self.mw.move_block_down_button.setEnabled(False)
                self.mw.move_block_down_button.setToolTip(
                    f"Moving items is {proj_tip}" if not has_project else select_tip
                )


    def resolve_bmg_id_to_indices(self, bmg_id: str) -> Optional[Tuple[int, int]]:
        """Resolve a BMG ID like 'main_Str_125' to (block_idx, string_idx)."""
        if not bmg_id:
            return None
            
        # Strip square brackets commonly used in database mappings/transcripts
        if bmg_id.startswith("[") and bmg_id.endswith("]"):
            bmg_id = bmg_id[1:-1]
            
        if "_Str_" not in bmg_id:
            return None
        try:
            parts = bmg_id.rsplit("_Str_", 1)
            if len(parts) != 2:
                return None
            block_label, s_idx_str = parts
            s_idx = int(s_idx_str)
            
            # Helper to normalize labels
            def normalize_label(lbl: str) -> str:
                if not lbl:
                    return ""
                # replace backslashes, take final path component
                lbl = lbl.replace("\\", "/").split("/")[-1]
                # remove typical extensions
                for ext in ['.bmg', '.json', '.arc', '.rarc', '.ark']:
                    if lbl.lower().endswith(ext):
                        lbl = lbl[:-len(ext)]
                return lbl.strip().lower()
            
            clean_blklbl = normalize_label(block_label)
            
            # Special case for general 'BMG' prefix (e.g. BMG_Str_0 in Zelda TP)
            if clean_blklbl == "bmg":
                for b_idx in range(len(self.mw.data_store.data)):
                    composer = getattr(self.mw, "translation_handler", None)
                    if composer and hasattr(composer, "prompt_composer"):
                        label = composer.prompt_composer._get_block_label(b_idx)
                    else:
                        label = f"Block_{b_idx}"
                    clean_lbl = normalize_label(label)
                    if clean_lbl == "bmg" or "zel_00" in clean_lbl or b_idx == 0:
                        return b_idx, s_idx
            
            # 1. Exact normalized match
            for b_idx in range(len(self.mw.data_store.data)):
                composer = getattr(self.mw, "translation_handler", None)
                if composer and hasattr(composer, "prompt_composer"):
                    label = composer.prompt_composer._get_block_label(b_idx)
                else:
                    label = f"Block_{b_idx}"
                if normalize_label(label) == clean_blklbl:
                    return b_idx, s_idx
            
            # 2. Fuzzy normalized match (substring)
            for b_idx in range(len(self.mw.data_store.data)):
                composer = getattr(self.mw, "translation_handler", None)
                if composer and hasattr(composer, "prompt_composer"):
                    label = composer.prompt_composer._get_block_label(b_idx)
                else:
                    label = f"Block_{b_idx}"
                clean_lbl = normalize_label(label)
                if clean_blklbl and clean_lbl and (clean_blklbl in clean_lbl or clean_lbl in clean_blklbl):
                    return b_idx, s_idx
        except Exception as e:
            log_debug(f"Failed to resolve bmg_id {bmg_id}: {e}")
        return None

    def select_string_by_absolute_index(self, absolute_idx: int) -> None:
        """Select a string using its absolute index in block data, handling relative mapping automatically."""
        if absolute_idx == -1: return

        rel_idx: int = -1
        displayed_indices = self._get_displayed_indices()
        
        is_chapter = getattr(self.mw.data_store, 'current_block_idx', -1) == -2
        if is_chapter:
            target_tuple = None
            for item in displayed_indices:
                if isinstance(item, tuple) and len(item) == 2 and item[1] == absolute_idx:
                    target_tuple = item
                    break
            if target_tuple is not None:
                rel_idx = displayed_indices.index(target_tuple)
        else:
            if absolute_idx in displayed_indices:
                rel_idx = displayed_indices.index(absolute_idx)
            else:
                rel_idx = absolute_idx # Fallback if no mapping exists

        # If strings are not yet populated (e.g. initial load), displayed_string_indices might be empty.
        # string_selected_from_preview will handle further validation.
        self.string_selected_from_preview(rel_idx)

    def string_selected_from_preview(self, line_number: int, is_manual_click: bool = False) -> None:
        """String selected from preview."""
        log_debug(f"DIAG_STRING_SELECTED_FROM_PREVIEW: line={line_number}, is_manual={is_manual_click}")
        
        if hasattr(self.mw, 'editor_operation_handler'):
            self.mw.editor_operation_handler.stop_and_flush_editor_changes()

        preview_edit = getattr(self.mw, 'preview_text_edit', None)

        original_programmatic_state = self.mw.is_programmatically_changing_text
        self.mw.is_programmatically_changing_text = True

        # Translate relative preview line_number to absolute data index
        real_idx = line_number
        displayed_indices = self._get_displayed_indices()
        if displayed_indices:
            if 0 <= line_number < len(displayed_indices):
                real_idx = displayed_indices[line_number]
            else:
                real_idx = -1

        curr_b_idx = self.mw.data_store.current_block_idx
        curr_s_idx = -1
        
        if isinstance(real_idx, tuple) and len(real_idx) == 2:
            curr_b_idx, curr_s_idx = real_idx
        else:
            curr_s_idx = real_idx

        self._clear_pending_speaker_retention((curr_b_idx, curr_s_idx))

        if curr_b_idx == -1 or curr_s_idx == -1:
            self.mw.data_store.current_string_idx = -1
            if preview_edit and hasattr(preview_edit, 'highlightManager'):
                 preview_edit.highlightManager.clearPreviewSelectedLineHighlight()
            self.ui_updater.update_text_views()
            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_string_settings_panel()
            self.mw.is_programmatically_changing_text = original_programmatic_state
            return

        is_valid_line = False
        if 0 <= curr_b_idx < len(self.mw.data_store.data) and \
           isinstance(self.mw.data_store.data[curr_b_idx], list) and \
           0 <= curr_s_idx < len(self.mw.data_store.data[curr_b_idx]):
            is_valid_line = True
        
        previous_string_idx = self.mw.data_store.current_string_idx
        
        if not is_valid_line:
            self.mw.data_store.current_string_idx = -1
            if preview_edit and hasattr(preview_edit, 'highlightManager'):
                preview_edit.highlightManager.clearPreviewSelectedLineHighlight()
        else:
            # Update physical_block_idx
            self.mw.data_store.physical_block_idx = curr_b_idx
            
            # Update current_block_idx if we switched to a different block inside the normal view (not in virtual speaker/chapter folders)
            if self.mw.data_store.current_block_idx >= 0 and self.mw.data_store.current_block_idx != curr_b_idx:
                self.mw.data_store.current_block_idx = curr_b_idx

            self.mw.data_store.current_string_idx = curr_s_idx
            self.mw.data_store.edited_sublines.clear() # Clear editor sublines on line change
            
            # Restore subline asterisks if the selected line has unsaved changes in memory
            if (curr_b_idx, curr_s_idx) in self.mw.data_store.edited_data:
                current_text = self.mw.data_store.edited_data[(curr_b_idx, curr_s_idx)]
                if hasattr(self.mw, 'text_operation_handler'):
                    self.mw.text_operation_handler.sync_subline_asterisks(
                        curr_b_idx, curr_s_idx, current_text
                    )

            if hasattr(self.mw, 'undo_manager') and not original_programmatic_state:
                cat = getattr(self.mw.data_store, 'current_category_name', None)
                self.mw.undo_manager.record_navigation(
                    curr_b_idx, curr_s_idx, 
                    curr_b_idx, previous_string_idx,
                    cat, cat
                )

            if previous_string_idx != self.mw.data_store.current_string_idx and previous_string_idx != -1:
                self.ui_updater.update_block_item_text_with_problem_count(curr_b_idx)
            
            # Save selection to project
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                project = self.mw.project_manager.project
                if hasattr(self.mw, 'block_to_project_file_map'):
                    project_block_idx = self.mw.block_to_project_file_map.get(curr_b_idx)
                    if project_block_idx is not None and project_block_idx < len(project.blocks):
                        project.blocks[project_block_idx].last_selected_string_idx = curr_s_idx

        self.ui_updater.update_text_views()
        if hasattr(self.mw, 'string_settings_updater'):
            self.mw.string_settings_updater.update_string_settings_panel()

        self.mw.is_programmatically_changing_text = original_programmatic_state

        # Determine the physical block index for validation; current_block_idx can be -2 (chapter) or -3 (speaker).
        _phys_b_idx = self.mw.data_store.physical_block_idx
        _is_virtual_mode = self.mw.data_store.current_block_idx in (-2, -3)

        if preview_edit and self.mw.data_store.current_string_idx != -1 and \
           (_is_virtual_mode or (0 <= _phys_b_idx < len(self.mw.data_store.data) and
            0 <= self.mw.data_store.current_string_idx < len(self.mw.data_store.data[_phys_b_idx]))):
            
            # Find relative index for preview
            rel_idx = -1
            displayed_indices = self._get_displayed_indices()
            
            # Virtual mode (speaker/chapter): displayed_indices contain (b_idx, s_idx) tuples
            # Use physical_block_idx to form the lookup tuple, NOT current_block_idx (-2/-3)
            if _is_virtual_mode or (displayed_indices and isinstance(displayed_indices[0], tuple)):
                target_tuple = (_phys_b_idx, self.mw.data_store.current_string_idx)
                if target_tuple in displayed_indices:
                    rel_idx = displayed_indices.index(target_tuple)
            else:
                if self.mw.data_store.current_string_idx in displayed_indices:
                    rel_idx = displayed_indices.index(self.mw.data_store.current_string_idx)

            if rel_idx != -1 and hasattr(preview_edit, 'set_selected_lines'): 
                preview_edit.set_selected_lines([rel_idx])
            
            if rel_idx != -1:
                block_to_show = preview_edit.document().findBlockByNumber(rel_idx)
                if block_to_show.isValid():
                    cursor = QTextCursor(block_to_show)
                    preview_edit.setTextCursor(cursor)
                    # Use a small timer to ensure the widget has finished layout after potential text updates
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(10, lambda: preview_edit.ensureCursorVisible())
        elif preview_edit and hasattr(preview_edit, 'highlightManager'): 
            preview_edit.highlightManager.clearPreviewSelectedLineHighlight()
            
        if self.mw.data_store.current_string_idx != -1 and hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
            search_has_focus = False
            if hasattr(self.mw, 'search_panel_widget') and self.mw.search_panel_widget and self.mw.search_panel_widget.isVisible():
                focus_widget = QApplication.focusWidget()
                if focus_widget:
                    parent = focus_widget
                    while parent:
                        if parent == self.mw.search_panel_widget:
                            search_has_focus = True
                            break
                        parent = parent.parentWidget()
            
            if not search_has_focus:
                self.mw.edited_text_edit.setFocus()
            cursor = self.mw.edited_text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.mw.edited_text_edit.setTextCursor(cursor)

        if self.mw.data_store.current_string_idx != -1 and hasattr(self.mw, 'editor_operation_handler') and self.mw.editor_operation_handler:
            self.mw.editor_operation_handler.launch_async_scanner_immediate()

        if not getattr(self.mw, 'is_loading_data', False) and not original_programmatic_state:
            self.data_processor.schedule_autosave()


    def rename_block(self, item: QTreeWidgetItem) -> None:
        """Rename block."""
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
                    item.setData(0, Qt.UserRole + 10, new_text.strip())
                    item.setData(0, Qt.UserRole + 4, new_text.strip())
                    item.setData(0, Qt.EditRole, new_text.strip())
                    self.ui_updater.update_block_item_text_with_problem_count(block_index_from_data)
            elif block_index_from_data is not None:
                # Rename Block
                block_index_str = str(block_index_from_data)
                
                # If there are merged IDs (compact folders), handle multi-part rename
                if merged_ids and " / " in new_text:
                    parts = new_text.split(" / ")
                    actual_block_name = parts[-1].strip()
                    self.mw.data_store.block_names[block_index_str] = actual_block_name
                    
                    # Also update ProjectManager if applicable
                    if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                        block_map = getattr(self.mw, 'block_to_project_file_map', {})
                        proj_idx = block_map.get(block_index_from_data)
                        if proj_idx is not None and proj_idx < len(self.mw.project_manager.project.blocks):
                            self.mw.project_manager.project.blocks[proj_idx].name = actual_block_name
                    
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
                    
                    # Also update ProjectManager if applicable
                    if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                        block_map = getattr(self.mw, 'block_to_project_file_map', {})
                        proj_idx = block_map.get(block_index_from_data)
                        if proj_idx is not None and proj_idx < len(self.mw.project_manager.project.blocks):
                            self.mw.project_manager.project.blocks[proj_idx].name = new_text
                            self.mw.project_manager.save()
                
                item.setData(0, Qt.UserRole + 4, new_text)
                item.setData(0, Qt.EditRole, new_text)
                self.mw.settings_manager.save_block_names()
                log_debug(f"Block {block_index_from_data} renamed to '{new_text}'")
                
                # Repopulate to fix any visual issues
                self.ui_updater.update_block_item_text_with_problem_count(block_index_from_data)
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
        """Internal helper to data string has any problem."""
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
        """Navigate to problem string."""
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
            self.mw.is_programmatically_changing_text = True # Set programmatic state before calling string_selected_from_preview
            self.string_selected_from_preview(found_target_s_idx)
            self.mw.is_programmatically_changing_text = original_programmatic_state # Restore after selection
        else:
            log_debug("[NAV] No problem string found in current search.")
            if start_scan_idx != -1 and self._data_string_has_any_problem(self.mw.data_store.current_block_idx, start_scan_idx):
                 self.mw.is_programmatically_changing_text = True # Set programmatic state before calling string_selected_from_preview
                 self.string_selected_from_preview(start_scan_idx)
                 self.mw.is_programmatically_changing_text = original_programmatic_state # Restore after selection
            else:
                self.mw.is_programmatically_changing_text = original_programmatic_state

    def handle_preview_selection_changed(self, selected_lines: Optional[List[int]] = None) -> None:
        """Handle preview selection changed."""
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        log_debug(f"DIAG_HANDLE_PREVIEW_SELECTION_CHANGED: selected={selected_lines}, focus={preview_edit.hasFocus() if preview_edit else False}, programmatic={self.mw.is_programmatically_changing_text}")
        if not preview_edit or self.mw.is_programmatically_changing_text:
            return
            
        if selected_lines is None:
            if not preview_edit.hasFocus():
                return
            cursor = preview_edit.textCursor()
            if not cursor.hasSelection():
                if self.mw.data_store.current_string_idx != -1:
                    if hasattr(preview_edit, 'set_selected_lines'):
                        # Find the relative index for the current string to highlight it
                        rel_idx = -1
                        displayed_indices = self._get_displayed_indices()
                        is_virtual = self.mw.data_store.current_block_idx < 0
                        if is_virtual or (displayed_indices and isinstance(displayed_indices[0], tuple)):
                            target_tuple = (self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx)
                            if target_tuple in displayed_indices:
                                rel_idx = displayed_indices.index(target_tuple)
                        else:
                            if self.mw.data_store.current_string_idx in displayed_indices:
                                rel_idx = displayed_indices.index(self.mw.data_store.current_string_idx)
                        if rel_idx != -1:
                            preview_edit.set_selected_lines([rel_idx])
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
        displayed_indices = self._get_displayed_indices()
        if displayed_indices:
            for rel in selected_lines:
                if 0 <= rel < len(displayed_indices):
                    abs_indices.append(displayed_indices[rel])
        else:
            abs_indices = selected_lines
            
        # Save to app state
        self.mw.data_store.selected_string_indices = abs_indices
        
        # If only one selected, update current_string_idx
        if len(abs_indices) == 1:
            target_idx = abs_indices[0]
            target_b_idx = self.mw.data_store.current_block_idx
            target_s_idx = target_idx
            if isinstance(target_idx, tuple) and len(target_idx) == 2:
                target_b_idx, target_s_idx = target_idx
            
            if self.mw.data_store.current_string_idx != target_s_idx or self.mw.data_store.current_block_idx != target_b_idx:
                # In virtual mode (speaker/chapter folder, current_block_idx is -2 or -3),
                # do NOT overwrite current_block_idx with the physical target_b_idx.
                # Only update physical_block_idx and current_string_idx.
                is_virtual_mode = self.mw.data_store.current_block_idx < 0
                if not is_virtual_mode:
                    self.mw.data_store.current_block_idx = target_b_idx
                self.mw.data_store.physical_block_idx = target_b_idx
                self.mw.data_store.current_string_idx = target_s_idx
                self.ui_updater.update_text_views()
                if hasattr(self.mw, 'string_settings_updater'):
                    self.mw.string_settings_updater.update_string_settings_panel()

        if preview_edit and hasattr(preview_edit, 'set_selected_lines'):
            preview_edit.set_selected_lines(selected_lines)

    def move_selection_to_category(self) -> None:
        """Move selected strings to a virtual block (Category)."""
        selected_indices = getattr(self.mw.data_store, 'selected_string_indices', [])
        if not selected_indices:
            from PyQt6.QtWidgets import QMessageBox
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
        from PyQt6.QtWidgets import QInputDialog
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
        from PyQt6.QtWidgets import QInputDialog
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
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self.mw, "Delete Virtual Block", f"Are you sure you want to delete virtual block '{category_name}'?\n\n(Strings will not be deleted from the block itself.)", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
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
        self.data_processor.schedule_autosave()

    def toggle_hide_categorized(self, checked: bool) -> None:
        """Toggle hiding of categorized strings in parent block."""
        self.mw.data_store.hide_categorized = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, self.mw.data_store.current_category_name)
        self.data_processor.schedule_autosave()

    def toggle_hide_empty_strings(self, checked: bool) -> None:
        """Toggle hiding of empty strings in preview list."""
        self.mw.data_store.hide_empty_strings = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, self.mw.data_store.current_category_name)
        self.data_processor.schedule_autosave()

    def toggle_hide_translated(self, checked: bool) -> None:
        """Toggle hiding of translated strings in preview list."""
        self.mw.data_store.hide_translated = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, self.mw.data_store.current_category_name)
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
                self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, self.mw.data_store.current_category_name)
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
                    from PyQt6.QtWidgets import QApplication
                    QApplication.processEvents()
            else:
                if current_idx != -1:
                    self.scroll_to_current_string_in_preview()
                    from PyQt6.QtWidgets import QApplication
                    QApplication.processEvents()
            
            self._saved_approx_visible_lines = 0

        # Close progress dialog after layout and scrolling are fully completed
        if preview_updater:
            preview_updater._keep_progress_dialog_open = False
            if hasattr(preview_updater, '_active_progress_dialog') and preview_updater._active_progress_dialog:
                preview_updater._active_progress_dialog.close()
                preview_updater._active_progress_dialog = None
        self.data_processor.schedule_autosave()


    def toggle_hide_original_tags(self, checked: bool) -> None:
        """Toggle hiding of tags in the original text edit."""
        self.mw.data_store.hide_original_tags = checked
        if hasattr(self.mw, 'helper') and hasattr(self.mw.helper, 'reconfigure_all_highlighters'):
            self.mw.helper.reconfigure_all_highlighters()
        self.data_processor.schedule_autosave()

    def toggle_hide_translation_tags(self, checked: bool) -> None:
        """Toggle hiding of tags in the translation and preview text edits."""
        self.mw.data_store.hide_translation_tags = checked
        if hasattr(self.mw, 'helper') and hasattr(self.mw.helper, 'reconfigure_all_highlighters'):
            self.mw.helper.reconfigure_all_highlighters()
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, self.mw.data_store.current_category_name)
        self.data_processor.schedule_autosave()

    def toggle_hide_tags_global(self) -> None:
        """Toggle hiding of tags globally for both original and translation."""
        orig_checked = self.mw.hide_original_tags_checkbox.isChecked() if getattr(self.mw, 'hide_original_tags_checkbox', None) else self.mw.data_store.hide_original_tags
        trans_checked = self.mw.hide_translation_tags_checkbox.isChecked() if getattr(self.mw, 'hide_translation_tags_checkbox', None) else self.mw.data_store.hide_translation_tags

        target_state = not (orig_checked or trans_checked)

        checkbox_triggered = False
        if getattr(self.mw, 'hide_original_tags_checkbox', None):
            self.mw.hide_original_tags_checkbox.setChecked(target_state)
            checkbox_triggered = True
        else:
            self.mw.data_store.hide_original_tags = target_state

        if getattr(self.mw, 'hide_translation_tags_checkbox', None):
            self.mw.hide_translation_tags_checkbox.setChecked(target_state)
            checkbox_triggered = True
        else:
            self.mw.data_store.hide_translation_tags = target_state

        if not checkbox_triggered:
            if hasattr(self.mw, 'helper') and hasattr(self.mw.helper, 'reconfigure_all_highlighters'):
                self.mw.helper.reconfigure_all_highlighters()
            if self.mw.data_store.current_block_idx != -1:
                self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, self.mw.data_store.current_category_name)
        self.data_processor.schedule_autosave()


    def toggle_show_unsaved_only(self, checked: bool) -> None:
        """Toggle showing only unsaved strings in preview list."""
        self.mw.data_store.show_unsaved_only = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, self.mw.data_store.current_category_name)
        self.data_processor.schedule_autosave()

    def toggle_show_unsaved_blocks_only(self, checked: bool) -> None:
        """Toggle showing only unsaved blocks in the tree."""
        self.mw.data_store.show_unsaved_blocks_only = checked
        self.ui_updater.block_list_updater.populate_blocks()
        self.data_processor.schedule_autosave()

    def scroll_to_current_string_in_preview(self) -> None:
        """Scroll and focus the preview text edit to the currently selected string."""
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit:
            return
            
        current_string_idx = self.mw.data_store.current_string_idx
        if current_string_idx == -1:
            return
            
        displayed_indices = self._get_displayed_indices()
        if current_string_idx in displayed_indices:
            rel_idx = displayed_indices.index(current_string_idx)
            if 0 <= rel_idx < preview_edit.document().blockCount():
                block_to_show = preview_edit.document().findBlockByNumber(rel_idx)
                if block_to_show.isValid():
                    cursor = QTextCursor(block_to_show)
                    preview_edit.setTextCursor(cursor)
                    if hasattr(preview_edit, 'set_selected_lines'):
                        preview_edit.set_selected_lines([rel_idx])
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(10, lambda: preview_edit.ensureCursorVisible())

    def _get_displayed_indices(self) -> list:
        """Internal helper to get the displayed indices."""
        indices = getattr(self.mw.data_store, 'displayed_string_indices', [])
        if not indices and hasattr(self.mw, 'displayed_string_indices'):
            indices = self.mw.displayed_string_indices
        return indices

    def _clear_pending_speaker_retention(self, next_tuple: Optional[Tuple[int, int]] = None) -> None:
        """Drop a temporarily retained speaker row once the user navigates away from it."""
        pending = self._pending_speaker_retention
        if not pending:
            return

        speaker_name, retained_tuple, _ = pending
        if next_tuple == retained_tuple:
            return

        self._pending_speaker_retention = None

        if getattr(self.mw.data_store, 'current_block_idx', None) != -3:
            return
        if getattr(self.mw.data_store, 'current_speaker_name', None) != speaker_name:
            return

        mappings = list(getattr(self.mw.data_store, 'chapter_mappings', []))
        if retained_tuple not in mappings:
            return

        mappings.remove(retained_tuple)
        self.mw.data_store.chapter_mappings = mappings
        if hasattr(self.ui_updater, 'populate_strings_for_block'):
            self.ui_updater.populate_strings_for_block(-3)

    def _restore_editor_focus_after_speaker_save(self) -> None:
        """Return focus from the editable speaker combobox to the main editor."""
        editor = getattr(self.mw, 'edited_text_edit', None)
        if not editor or not hasattr(editor, 'setFocus'):
            return

        def focus_editor() -> None:
            try:
                editor.setFocus(Qt.FocusReason.OtherFocusReason)
            except TypeError:
                editor.setFocus()

        QTimer.singleShot(0, focus_editor)

    def _expand_item_ancestors(self, item: QTreeWidgetItem) -> None:
        """Ensure the selected virtual folder remains visible after a tree rebuild."""
        parent = item.parent()
        while parent:
            parent.setExpanded(True)
            parent = parent.parent()

    def save_speaker_for_current_string(self, char_name: str) -> None:
        """Save speaker assignment for the current string and refresh UI."""
        char_name = char_name.strip()
        
        # Prevent redundant saves and selection changes when the user clicks/opens the combobox
        cb = getattr(self.mw, 'speaker_combobox', None)
        is_undoing_redoing = False
        if hasattr(self.mw, 'undo_manager') and self.mw.undo_manager:
            is_undoing_redoing = self.mw.undo_manager.is_undoing_redoing
            
        if cb is not None and not is_undoing_redoing:
            last_displayed = getattr(cb, '_last_displayed_char', None)
            if last_displayed is not None and char_name == last_displayed:
                return
                
        block_idx = self.mw.data_store.physical_block_idx
        string_idx = self.mw.data_store.current_string_idx
        
        if block_idx == -1 or string_idx == -1:
            return
            
        pm = getattr(self.mw, 'project_manager', None)
        if not pm or not pm.project:
            return
            
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)
        if proj_b_idx >= len(pm.project.blocks):
            return
            
        block = pm.project.blocks[proj_b_idx]
        assignments = block.metadata.setdefault("character_assignments", {})
        
        old_char = assignments.get(str(string_idx))
        
        # Normalize none/empty values to avoid false triggers upon dropdown focus/activation
        is_none_or_empty_new = (not char_name or char_name.lower() == "none")
        is_none_or_empty_old = (not old_char or old_char.lower() == "none")
        
        if old_char == char_name or (is_none_or_empty_new and is_none_or_empty_old):
            return
            
        # Record undo action
        if hasattr(self.mw, 'undo_manager') and self.mw.undo_manager and not is_undoing_redoing:
            self.mw.undo_manager.record_action(
                action_type='CHANGE_SPEAKER',
                block_idx=block_idx,
                string_idx=string_idx,
                old_text=old_char or "",
                new_text=char_name or ""
            )

        if is_none_or_empty_new:
            assignments.pop(str(string_idx), None)
        else:
            assignments[str(string_idx)] = char_name
            
        pm.save()
        
        current_item = self.mw.block_list_widget.currentItem()
        override_block_idx = None
        override_folder_id = None
        if current_item:
            override_block_idx = current_item.data(0, Qt.ItemDataRole.UserRole)
            override_folder_id = current_item.data(0, Qt.ItemDataRole.UserRole + 1)
            
        # Ensure we stay in virtual mode if we are editing inside virtual speakers/chapters directories
        current_speaker_name_in_store = getattr(self.mw.data_store, 'current_speaker_name', None)
        current_chapter_id_in_store = getattr(self.mw.data_store, 'current_chapter_id', None)
        if current_speaker_name_in_store is not None:
            override_block_idx = -3
            override_folder_id = current_speaker_name_in_store
            self._target_block_idx = block_idx
            self._target_string_idx = string_idx
            retained_tuple = (block_idx, string_idx)
            current_mappings = list(getattr(self.mw.data_store, 'chapter_mappings', []))
            retention_index = current_mappings.index(retained_tuple) if retained_tuple in current_mappings else len(current_mappings)
            self._pending_speaker_retention = (current_speaker_name_in_store, retained_tuple, retention_index)
        elif current_chapter_id_in_store is not None:
            override_block_idx = -2
            self._target_block_idx = block_idx
            self._target_string_idx = string_idx
        else:
            self._target_block_idx = block_idx
            self._target_string_idx = string_idx
            
        previous_programmatic_state = self.mw.is_programmatically_changing_text
        self.mw.is_programmatically_changing_text = True
        try:
            if override_block_idx == -3 and current_speaker_name_in_store:
                # Rebuild tree so items have updated mappings lists
                self.ui_updater.block_list_updater.populate_blocks(override_folder_id=override_folder_id, override_block_idx=override_block_idx)
                
                # Find the active speaker item in the block tree to get its updated mappings
                active_item = None
                iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
                while iterator.value():
                    item = iterator.value()
                    if item.data(0, Qt.UserRole) == -3 and item.data(0, Qt.UserRole + 15) == current_speaker_name_in_store:
                        active_item = item
                        break
                    iterator += 1

                if active_item:
                    # Update chapter_mappings from the freshly-rebuilt item, then refresh
                    # the preview WITHOUT treating emitted selection signals as navigation.
                    new_mappings = active_item.data(0, Qt.UserRole + 13) or []
                    retained_tuple = (block_idx, string_idx)
                    pending_retention = self._pending_speaker_retention
                    retention_index = 0
                    is_retained_by_pending = (
                        pending_retention is not None
                        and pending_retention[0] == current_speaker_name_in_store
                        and pending_retention[1] == retained_tuple
                    )
                    if is_retained_by_pending:
                        retention_index = pending_retention[2]

                    if retained_tuple not in new_mappings:
                        new_mappings = list(new_mappings)
                        new_mappings.insert(min(max(retention_index, 0), len(new_mappings)), retained_tuple)
                        active_item.setData(0, Qt.UserRole + 13, new_mappings)
                        self._pending_speaker_retention = (current_speaker_name_in_store, retained_tuple, retention_index)
                    elif is_retained_by_pending:
                        self._pending_speaker_retention = (current_speaker_name_in_store, retained_tuple, retention_index)
                    else:
                        self._pending_speaker_retention = None
                    self.mw.data_store.chapter_mappings = new_mappings
                    self.mw.data_store.current_block_idx = -3
                    self.mw.data_store.physical_block_idx = block_idx
                    self.mw.data_store.current_string_idx = string_idx
                    self.mw.data_store.current_speaker_name = current_speaker_name_in_store
                    block_list_widget = getattr(self.mw, 'block_list_widget', None)
                    if block_list_widget:
                        signals_were_blocked = block_list_widget.blockSignals(True)
                        try:
                            self._expand_item_ancestors(active_item)
                            block_list_widget.setCurrentItem(active_item)
                            active_item.setSelected(True)
                        finally:
                            block_list_widget.blockSignals(signals_were_blocked)
                    self.ui_updater.populate_strings_for_block(-3)
                    self.mw.data_store.current_block_idx = -3
                    self.mw.data_store.physical_block_idx = block_idx
                    self.mw.data_store.current_string_idx = string_idx
                    self.mw.data_store.current_speaker_name = current_speaker_name_in_store
                    self._target_block_idx = None
                    self._target_string_idx = None
                    self.ui_updater.update_text_views()
                    if hasattr(self.mw, 'string_settings_updater'):
                        self.mw.string_settings_updater.update_string_settings_panel()
                    self.ui_updater.update_statusbar_paths()
                else:
                    self.mw.data_store.chapter_mappings = []
                    self.mw.data_store.current_block_idx = -3
                    self.mw.data_store.physical_block_idx = block_idx
                    self.mw.data_store.current_string_idx = string_idx
                    self.mw.data_store.current_speaker_name = current_speaker_name_in_store
                    self.ui_updater.populate_strings_for_block(-3)
                    self.ui_updater.update_text_views()
                    if hasattr(self.mw, 'string_settings_updater'):
                        self.mw.string_settings_updater.update_string_settings_panel()
            else:
                self.ui_updater.block_list_updater.populate_blocks(override_folder_id=override_folder_id, override_block_idx=override_block_idx)
                if hasattr(self.mw, 'string_settings_updater'):
                    self.mw.string_settings_updater.update_string_settings_panel()
        finally:
            self.mw.is_programmatically_changing_text = previous_programmatic_state
                
        self._restore_editor_focus_after_speaker_save()
        self.data_processor.schedule_autosave()

    def save_character_for_current_string(self, char_name: str) -> None:
        """Alias for save_speaker_for_current_string to maintain compatibility."""
        self.save_speaker_for_current_string(char_name)

    def toggle_show_warnings_only(self, checked: bool) -> None:
        """Toggle showing only strings matching active warning filters."""
        self.mw.data_store.show_warnings_only = checked
        if self.mw.data_store.current_block_idx != -1:
            self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, self.mw.data_store.current_category_name)
        self.data_processor.schedule_autosave()

    def warnings_filter_changed(self, active_warnings: list) -> None:
        """Handle change in active warning filters selection."""
        self.mw.data_store.active_warning_filters = active_warnings
        if self.mw.data_store.current_block_idx != -1 and getattr(self.mw.data_store, 'show_warnings_only', False):
            self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, self.mw.data_store.current_category_name)
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

