"""Physical block selection, preview selection, and toolbar state."""
from __future__ import annotations

from typing import Any, Optional, List, Tuple
from PyQt6.QtWidgets import QTreeWidgetItemIterator, QTreeWidgetItem, QApplication
from PyQt6.QtCore import Qt, QObject
from PyQt6.QtGui import QTextCursor
from core.data_store import ViewKind, get_view_kind, store_is_virtual_view
from utils.logging_utils import log_debug
from core.i18n import tr


def _refresh_string_settings_panel(mw) -> None:
    """Paint editors first; defer the story/speaker panel when we can."""
    updater = getattr(mw, 'string_settings_updater', None)
    if updater is None:
        return
    schedule = getattr(updater, 'schedule_panel_update', None)
    if callable(schedule) and type(updater).__name__ == 'StringSettingsUpdater':
        schedule()
        return
    updater.update_string_settings_panel()


class PhysicalSelectionMixin:
    """Physical block selection, preview selection, and toolbar state."""

    def block_selected(
        self,
        current_item: Optional[QTreeWidgetItem],
        previous_item: Optional[QTreeWidgetItem],
        force: bool = False,
    ) -> None:
        """Block selected.

        ``force`` runs the load even while data is loading. Selection signals
        fired incidentally during a load must be ignored, but a deliberate call
        from session restore must not be: dropping it leaves the block selected
        in the tree with no strings shown until the user clicks another block.
        """
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

        if not force and (self.mw.is_loading_data or self._restoring_selection):
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
                self._handle_virtual_row_selection(current_item)
                return

            block_index = current_item.data(0, Qt.UserRole)
            category_name = current_item.data(0, Qt.UserRole + 10)
            chapter_id = current_item.data(0, Qt.UserRole + 11)
            is_physical_block = isinstance(block_index, int) and block_index >= 0

            if current_item.data(0, Qt.UserRole + 18) == "aggregate" and not is_physical_block:
                self._handle_aggregate_virtual_selection(current_item)
                return

            if block_index == -3:
                self._handle_speaker_selection(current_item)
                return
            if block_index == -4:
                self._handle_item_selection(current_item)
                return
            if block_index == -5:
                self._handle_notated_selection(current_item)
                return

            if chapter_id is not None:
                self._handle_chapter_selection(
                    chapter_id,
                    current_item.data(0, Qt.UserRole + 13),
                )
                return

            if block_index is None:
                self._handle_folder_selection()
                return

            self._handle_physical_block_selection(block_index, category_name, old_block, old_string, old_category, force=force)
        finally:
            self.mw.is_programmatically_changing_text = False

        if not getattr(self.mw, 'is_loading_data', False) and not self._restoring_selection:
            self.data_processor.schedule_autosave()

    def _handle_physical_block_selection(self, block_index: int, category_name: Optional[str], old_block: int, old_string: int, old_category: Optional[str], force: bool = False) -> None:
        """Load a physical block into the view.

        The body is normally skipped when the block is already the current one,
        since re-selecting it would rebuild an identical view. ``force`` overrides
        that: on session restore the indices are restored *before* the view is
        built, so the "already current" check would leave the block selected with
        no strings shown until the user clicked away and back.
        """
        if force or self.mw.data_store.current_block_idx != block_index or self.mw.data_store.current_category_name != category_name or type(self.mw.data_store.current_chapter_id) is int or isinstance(getattr(self.mw.data_store, 'current_speaker_name', None), str):
            self._clear_pending_speaker_retention()
            self.mw.data_store.current_block_idx = block_index
            self.mw.data_store.physical_block_idx = block_index
            self.mw.data_store.set_view_kind(
                ViewKind.CATEGORY if category_name else ViewKind.PHYSICAL
            )
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
                rel_idx = self._get_relative_index(target_string_idx)

                if rel_idx != -1:
                    # Schedule selection to avoid recursion issues
                    if not getattr(self.mw, '_restoring_session_state', False):
                        self._schedule_string_selection(rel_idx)
            else:
                self.ui_updater.update_text_views()
                if hasattr(self.mw, 'string_settings_updater'):
                    _refresh_string_settings_panel(self.mw)

            self.ui_updater.update_statusbar_paths()
            self.ui_updater.update_block_item_text_with_problem_count(block_index)

        if hasattr(self.mw, 'string_settings_updater'):
            self.mw.string_settings_updater.update_font_combobox()
            _refresh_string_settings_panel(self.mw)

        self._update_block_toolbar_button_states(block_index)

    def _on_cursor_visible_timeout(self) -> None:
        """Position preview scrollbar so the target row appears near top with 2 rows above it."""
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit:
            return
        try:
            from PyQt6 import sip
        except ImportError:
            import sip
        try:
            if sip.isdeleted(preview_edit):
                return
        except (TypeError, RuntimeError):
            pass

        try:
            cursor = preview_edit.textCursor() if hasattr(preview_edit, 'textCursor') else None
            cursor_obj = cursor() if callable(cursor) else cursor
            target_block_number = -1
            if cursor_obj:
                if hasattr(cursor_obj, 'blockNumber'):
                    target_block_number = cursor_obj.blockNumber()
                elif hasattr(cursor_obj, 'block'):
                    block = cursor_obj.block()
                    if block and hasattr(block, 'isValid') and block.isValid():
                        target_block_number = block.blockNumber()

            if target_block_number >= 0:
                anchor_block_number = max(0, target_block_number - 2)
                doc = preview_edit.document() if hasattr(preview_edit, 'document') else None
                doc_obj = doc() if callable(doc) else doc
                anchor_block = doc_obj.findBlockByNumber(anchor_block_number) if doc_obj and hasattr(doc_obj, 'findBlockByNumber') else None

                if anchor_block and hasattr(anchor_block, 'isValid') and anchor_block.isValid():
                    scrollbar = preview_edit.verticalScrollBar() if hasattr(preview_edit, 'verticalScrollBar') else None
                    scrollbar_obj = scrollbar() if callable(scrollbar) else scrollbar
                    if scrollbar_obj and hasattr(scrollbar_obj, 'setValue'):
                        anchor_pos = anchor_block.firstLineNumber() if hasattr(anchor_block, 'firstLineNumber') else anchor_block_number
                        if anchor_pos == -1:
                            anchor_pos = anchor_block_number
                        min_val = scrollbar_obj.minimum() if hasattr(scrollbar_obj, 'minimum') and callable(scrollbar_obj.minimum) else 0
                        max_val = scrollbar_obj.maximum() if hasattr(scrollbar_obj, 'maximum') and callable(scrollbar_obj.maximum) else anchor_pos
                        clamped_val = max(min_val, min(anchor_pos, max_val))
                        scrollbar_obj.setValue(clamped_val)
                        return

            if hasattr(preview_edit, 'ensureCursorVisible') and callable(preview_edit.ensureCursorVisible):
                preview_edit.ensureCursorVisible()
        except Exception:
            pass

    def _schedule_string_selection(self, line_number: int) -> None:
        """Schedule string selection via timer."""
        self._pending_selection_line = line_number
        self._selection_timer.start(0)

    def _on_selection_timer_timeout(self) -> None:
        """Handle selection timer timeout with safety guards."""
        if self._pending_selection_line is not None:
            line_to_select = self._pending_selection_line
            self._pending_selection_line = None
            try:
                from PyQt6 import sip
            except ImportError:
                import sip
            try:
                if hasattr(self, 'mw') and self.mw:
                    if isinstance(self.mw, QObject) and sip.isdeleted(self.mw):
                        return
                    self.string_selected_from_preview(line_to_select)
            except (TypeError, RuntimeError):
                pass

    def _restore_block_selection(self) -> None:
        """Internal helper to restore block selection."""
        if self.mw.data_store.current_block_idx != -1:
            target_token = self.mw.data_store.view_block_token
            iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
            while iterator.value():
                item = iterator.value()
                matches = item.data(0, Qt.UserRole) == target_token
                current_view_kind = get_view_kind(self.mw.data_store)
                if current_view_kind == ViewKind.CHAPTER:
                    matches = matches and item.data(0, Qt.UserRole + 11) == self.mw.data_store.current_chapter_id
                elif current_view_kind == ViewKind.SPEAKER:
                    matches = matches and item.data(0, Qt.UserRole + 15) == self.mw.data_store.current_speaker_name
                elif current_view_kind == ViewKind.ITEM:
                    matches = matches and item.data(0, Qt.UserRole + 16) == self.mw.data_store.current_speaker_name
                elif current_view_kind == ViewKind.NOTATED:
                    matches = matches and item.data(0, Qt.UserRole + 19) == self.mw.data_store.current_speaker_name
                if matches:
                    self.mw.block_list_widget.setCurrentItem(item)
                    break
                iterator += 1
        self._restoring_selection = False

    def _update_block_toolbar_button_states(self, block_idx: int):
        """Update the enabled/disabled state of toolbar buttons based on selection and position."""
        has_project = bool(hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project)

        # Enable Add Folder if project exists
        if hasattr(self.mw, 'add_folder_button'):
            self.mw.add_folder_button.setEnabled(has_project)
            from ui.builders.layout_builder import ADD_FOLDER_TOOLTIP
            self.mw.add_folder_button.setToolTip(
                ADD_FOLDER_TOOLTIP if has_project
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
                self.mw.delete_block_button.setToolTip(tr('Delete selected block or folder'))
            if hasattr(self.mw, 'rename_block_button'):
                self.mw.rename_block_button.setEnabled(True)
                self.mw.rename_block_button.setToolTip(tr('Rename selected block or folder'))

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
        if store_is_virtual_view(self.mw.data_store):
            target_tuple = None
            displayed_indices = self._get_displayed_indices()
            for item in displayed_indices:
                if isinstance(item, tuple) and len(item) == 2 and item[1] == absolute_idx:
                    target_tuple = item
                    break
            if target_tuple is not None:
                rel_idx = self._get_relative_index(target_tuple)
        else:
            rel_idx = self._get_relative_index(absolute_idx)
            if rel_idx == -1:
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
            self.ui_updater.update_text_views(heavy=False)
            if hasattr(self.mw, 'string_settings_updater'):
                _refresh_string_settings_panel(self.mw)
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
            self.mw.data_store.current_block_idx = curr_b_idx

            self.mw.data_store.current_string_idx = curr_s_idx
            self.mw.data_store.edited_sublines.clear() # Clear editor sublines on line change

            if hasattr(self.mw, 'undo_manager') and not original_programmatic_state:
                cat = getattr(self.mw.data_store, 'current_category_name', None)
                self.mw.undo_manager.record_navigation(
                    curr_b_idx, curr_s_idx,
                    curr_b_idx, previous_string_idx,
                    cat, cat
                )

            # Save selection to project
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                project = self.mw.project_manager.project
                if hasattr(self.mw, 'block_to_project_file_map'):
                    project_block_idx = self.mw.block_to_project_file_map.get(curr_b_idx)
                    if project_block_idx is not None and project_block_idx < len(project.blocks):
                        project.blocks[project_block_idx].last_selected_string_idx = curr_s_idx

        self.ui_updater.update_text_views(heavy=False)
        if hasattr(self.mw, 'string_settings_updater'):
            _refresh_string_settings_panel(self.mw)

        # Determine the physical block index for validation; current_block_idx can be -2 (chapter) or -3 (speaker).
        _phys_b_idx = self.mw.data_store.physical_block_idx
        _is_virtual_mode = store_is_virtual_view(self.mw.data_store)

        if preview_edit and self.mw.data_store.current_string_idx != -1 and \
           (_is_virtual_mode or (0 <= _phys_b_idx < len(self.mw.data_store.data) and
            0 <= self.mw.data_store.current_string_idx < len(self.mw.data_store.data[_phys_b_idx]))):

            # Find relative index for preview
            displayed_indices = self._get_displayed_indices()
            if _is_virtual_mode or (displayed_indices and isinstance(displayed_indices[0], tuple)):
                target_tuple = (_phys_b_idx, self.mw.data_store.current_string_idx)
                rel_idx = self._get_relative_index(target_tuple)
            else:
                rel_idx = self._get_relative_index(self.mw.data_store.current_string_idx)

            if rel_idx != -1 and hasattr(preview_edit, 'set_selected_lines'):
                already = getattr(preview_edit, '_selected_lines', None)
                if already != {rel_idx}:
                    preview_edit.set_selected_lines([rel_idx])

            # Jump-to-third-row is for external navigation (glossary,
            # search, undo). A click or arrow in Strings & Blocks
            # should leave the list where the user put it.
            if not is_manual_click and rel_idx != -1:
                block_to_show = preview_edit.document().findBlockByNumber(rel_idx)
                if block_to_show.isValid():
                    cursor = QTextCursor(block_to_show)
                    preview_edit.setTextCursor(cursor)
                    self._cursor_visible_timer.start(10)
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

        self.mw.is_programmatically_changing_text = original_programmatic_state

        if self.mw.data_store.current_string_idx != -1:
            if hasattr(self.ui_updater, 'schedule_row_paint_followup'):
                self.ui_updater.schedule_row_paint_followup()

        if not getattr(self.mw, 'is_loading_data', False) and not original_programmatic_state:
            self.data_processor.schedule_autosave()

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
                        displayed_indices = self._get_displayed_indices()
                        is_virtual = store_is_virtual_view(self.mw.data_store)
                        if is_virtual or (displayed_indices and isinstance(displayed_indices[0], tuple)):
                            target_tuple = (self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx)
                            rel_idx = self._get_relative_index(target_tuple)
                        else:
                            rel_idx = self._get_relative_index(self.mw.data_store.current_string_idx)
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
                self.mw.data_store.current_block_idx = target_b_idx
                self.mw.data_store.physical_block_idx = target_b_idx
                self.mw.data_store.current_string_idx = target_s_idx
                self.ui_updater.update_text_views(heavy=False)
                if hasattr(self.mw, 'string_settings_updater'):
                    _refresh_string_settings_panel(self.mw)
                if hasattr(self.ui_updater, 'schedule_row_paint_followup'):
                    self.ui_updater.schedule_row_paint_followup()

        if preview_edit and hasattr(preview_edit, 'set_selected_lines'):
            preview_edit.set_selected_lines(selected_lines)

    def scroll_to_current_string_in_preview(self) -> None:
        """Scroll and focus the preview text edit to the currently selected string."""
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit:
            return

        current_string_idx = self.mw.data_store.current_string_idx
        if current_string_idx == -1:
            return

        # Physical/category views address rows by string index, while virtual
        # chapter/speaker/item/aggregate views address them by the physical
        # (block, string) tuple. Prefer the representation actually present in
        # the current preview so this action never switches view paradigms.
        displayed_indices = self._get_displayed_indices()
        physical_target = (
            self.mw.data_store.physical_block_idx,
            current_string_idx,
        )
        target = physical_target if physical_target in displayed_indices else current_string_idx

        rel_idx = self._get_relative_index(target)
        if rel_idx != -1:
            if 0 <= rel_idx < preview_edit.document().blockCount():
                block_to_show = preview_edit.document().findBlockByNumber(rel_idx)
                if block_to_show.isValid():
                    cursor = QTextCursor(block_to_show)
                    preview_edit.setTextCursor(cursor)
                    if hasattr(preview_edit, 'set_selected_lines'):
                        preview_edit.set_selected_lines([rel_idx])
                    self._cursor_visible_timer.start(10)

    def _get_displayed_indices(self) -> list:
        """Internal helper to get the displayed indices."""
        indices = getattr(self.mw.data_store, 'displayed_string_indices', [])
        if not indices and hasattr(self.mw, 'displayed_string_indices'):
            indices = self.mw.displayed_string_indices
        return indices

    def _get_relative_index(self, target: Any) -> int:
        """O(1) lookup of target in displayed_string_indices.
        Returns the relative index of the target or -1 if not found.
        """
        if hasattr(self.mw, 'data_store') and self.mw.data_store:
            if hasattr(self.mw.data_store, 'get_displayed_index_pos'):
                res = self.mw.data_store.get_displayed_index_pos(target)
                if isinstance(res, int) and not isinstance(res, bool):
                    return res
        # Fallback to O(n) index
        indices = self._get_displayed_indices()
        try:
            return indices.index(target)
        except ValueError:
            return -1
