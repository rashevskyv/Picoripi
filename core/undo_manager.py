# --- START OF FILE core/undo_manager.py ---
import time
from dataclasses import dataclass
from typing import List, Optional, Any
from utils.logging_utils import log_debug

@dataclass
class UndoAction:
    action_type: str # 'TEXT_EDIT', 'PASTE', 'AUTOFIX', 'TRANSLATE', 'REVERT'
    block_idx: int
    string_idx: int
    old_text: str
    new_text: str
    timestamp: float
    cursor_pos: Optional[int] = None
    metadata: Optional[dict] = None

@dataclass
class GroupAction:
    actions: List[UndoAction]
    action_type: str
    timestamp: float

@dataclass
class StructuralAction:
    """Snapshot-based undo for block structure operations (rename, move, folder ops)."""
    action_type: str  # 'RENAME_BLOCK', 'RENAME_FOLDER', 'MOVE_BLOCK', 'ADD_FOLDER', 'DELETE_FOLDER', 'DRAG_DROP'
    before_snapshot: dict
    after_snapshot: dict
    label: str
    timestamp: float

class UndoManager:
    def __init__(self, main_window):
        self.mw = main_window
        self.undo_stack: List[Any] = []
        self.redo_stack: List[Any] = []
        self.is_undoing_redoing = False
        self.grouping_threshold = 3.5 # seconds to group character edits
        self.current_group: Optional[List[UndoAction]] = None
        
    def begin_group(self):
        self.current_group = []
        
    def end_group(self, action_type: str = "COMPOSITE"):
        if self.current_group:
            group = GroupAction(
                actions=self.current_group,
                action_type=action_type,
                timestamp=time.time()
            )
            self.undo_stack.append(group)
            self.redo_stack.clear()
        self.current_group = None

    def _is_word_char(self, c: str) -> bool:
        return c.isalnum() or c == '_'

    def record_action(self, action_type: str, block_idx: int, string_idx: int, old_text: str, new_text: str, metadata: dict = None):
        if self.is_undoing_redoing:
            return

        if old_text == new_text:
            return

        now = time.time()
        
        cursor_pos = None
        if self.mw.data_store.current_block_idx == block_idx and self.mw.data_store.current_string_idx == string_idx:
            cursor_pos = self.mw.edited_text_edit.textCursor().position()

        action = UndoAction(
            action_type=action_type,
            block_idx=block_idx,
            string_idx=string_idx,
            old_text=old_text,
            new_text=new_text,
            timestamp=now,
            cursor_pos=cursor_pos,
            metadata=metadata
        )

        if self.current_group is not None:
            self.current_group.append(action)
            return

        # Try to group small text edits
        if action_type == 'TEXT_EDIT' and self.undo_stack:
            last = self.undo_stack[-1]
            if isinstance(last, UndoAction) and \
                last.action_type == 'TEXT_EDIT' and \
                last.block_idx == block_idx and \
                last.string_idx == string_idx and \
                now - last.timestamp < self.grouping_threshold:
                
                is_simple_addition = False
                is_simple_deletion = False
                char = ""
                prev_char = ""

                diff_len = len(new_text) - len(last.new_text)
                if abs(diff_len) == 1:
                    min_len = min(len(new_text), len(last.new_text))
                    diff_idx = 0
                    while diff_idx < min_len and new_text[diff_idx] == last.new_text[diff_idx]:
                        diff_idx += 1
                        
                    if diff_len == 1:
                        is_simple_addition = True
                        char = new_text[diff_idx]
                        if diff_idx > 0:
                            prev_char = new_text[diff_idx - 1]
                    elif diff_len == -1:
                        is_simple_deletion = True
                        char = last.new_text[diff_idx]
                        if diff_idx > 0:
                            prev_char = last.new_text[diff_idx - 1]

                if is_simple_addition or is_simple_deletion:
                    # Don't group if char is newline
                    # Don't group if we transitioned from word char to non-word char (or vice versa)
                    if char == '\n' or (prev_char and char and self._is_word_char(char) != self._is_word_char(prev_char)):
                        # Break grouping
                        pass
                    else:
                        # Update the new_text of the last action
                        last.new_text = new_text
                        last.timestamp = now
                        last.cursor_pos = cursor_pos
                        self.redo_stack.clear()
                        return

        self.undo_stack.append(action)
        self.redo_stack.clear()
        
        if len(self.undo_stack) > 500:
            self.undo_stack.pop(0)
            
        log_debug(f"UndoManager: Recorded {action_type} for ({block_idx}, {string_idx})")

    # ------------------------------------------------------------------
    # Structural snapshot-based operations (rename, move, folder ops)
    # ------------------------------------------------------------------

    def get_project_snapshot(self) -> dict:
        """Capture current project + block_names structure for undo purposes."""
        import copy
        snapshot = {'block_names': copy.deepcopy(self.mw.data_store.block_names)}
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
            project = self.mw.project_manager.project
            snapshot['virtual_folders'] = [vf.to_dict() for vf in project.virtual_folders]
            snapshot['root_block_ids'] = list(project.metadata.get('root_block_ids', []))
        return snapshot

    def record_structural_action(self, before_snapshot: dict, action_type: str = 'STRUCTURE', label: str = ''):
        """Record a structural change (rename, move, folder) for undo/redo."""
        if self.is_undoing_redoing:
            return
        after_snapshot = self.get_project_snapshot()
        if before_snapshot == after_snapshot:
            return  # No change — nothing to record
        action = StructuralAction(
            action_type=action_type,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            label=label,
            timestamp=time.time()
        )
        self.undo_stack.append(action)
        self.redo_stack.clear()
        if len(self.undo_stack) > 500:
            self.undo_stack.pop(0)
        log_debug(f"UndoManager: Recorded structural '{action_type}': {label}")

    def _apply_project_snapshot(self, snapshot: dict):
        """Restore project structure from a snapshot and refresh UI."""
        from core.project_models import VirtualFolder
        import copy
        if 'block_names' in snapshot:
            self.mw.data_store.block_names = copy.deepcopy(snapshot['block_names'])
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_block_names()
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
            project = self.mw.project_manager.project
            if 'virtual_folders' in snapshot:
                project.virtual_folders = [VirtualFolder.from_dict(vf) for vf in snapshot['virtual_folders']]
            if 'root_block_ids' in snapshot:
                project.metadata['root_block_ids'] = list(snapshot['root_block_ids'])
            self.mw.project_manager.save()
        if hasattr(self.mw, 'ui_updater'):
            self.mw.ui_updater.populate_blocks()
            self.mw.ui_updater.update_title()
        log_debug("UndoManager: Applied project snapshot.")


    def record_navigation(self, block_idx: int, string_idx: int, prev_block_idx: int, prev_string_idx: int, category: str = None, prev_category: str = None):
        if self.is_undoing_redoing or self.current_group is not None:
            return

        if block_idx == prev_block_idx and string_idx == prev_string_idx and category == prev_category:
            return

        # Check if last action was also a navigation to group them or avoid duplicates
        if self.undo_stack:
            last = self.undo_stack[-1]
            if isinstance(last, UndoAction) and last.action_type == 'NAVIGATE':
                if time.time() - last.timestamp < 0.5:
                     last.block_idx = block_idx
                     last.string_idx = string_idx
                     if last.metadata:
                         last.metadata['category'] = category
                     last.timestamp = time.time()
                     return

        action = UndoAction(
            action_type='NAVIGATE',
            block_idx=block_idx,
            string_idx=string_idx,
            old_text="",
            new_text="",
            timestamp=time.time(),
            metadata={
                'prev_block': prev_block_idx, 
                'prev_string': prev_string_idx,
                'category': category,
                'prev_category': prev_category
            }
        )
        self.undo_stack.append(action)
        self.redo_stack.clear()
        if len(self.undo_stack) > 500:
            self.undo_stack.pop(0)
        log_debug(f"UndoManager: Recorded navigation to ({block_idx}, {string_idx})")

    def undo(self):
        if not self.undo_stack:
            log_debug("UndoManager: Undo stack empty")
            return

        item = self.undo_stack.pop()
        self.redo_stack.append(item)
        
        self.is_undoing_redoing = True
        try:
            if isinstance(item, UndoAction):
                if item.action_type == 'NAVIGATE':
                    prev_b = item.metadata.get('prev_block', -1)
                    prev_s = item.metadata.get('prev_string', -1)
                    prev_cat = item.metadata.get('prev_category')
                    self._navigate_to(prev_b, prev_s, prev_cat)
                else:
                    # For non-navigate actions, we might need to navigate to THEIR location first if not there
                    # But the requirement was "movements are separate steps".
                    # However, if we JUST popped a TEXT_EDIT, we should apply it at its location.
                    self._apply_data(item.block_idx, item.string_idx, item.old_text, item.cursor_pos)
            elif isinstance(item, GroupAction):
                for action in reversed(item.actions):
                    self._apply_data(action.block_idx, action.string_idx, action.old_text, action.cursor_pos)
            elif isinstance(item, StructuralAction):
                self._apply_project_snapshot(item.before_snapshot)
            log_debug(f"UndoManager: Undone item of type {item.action_type if isinstance(item, (UndoAction, StructuralAction)) else 'Group'}")
        finally:
            self.is_undoing_redoing = False

    def redo(self):
        if not self.redo_stack:
            log_debug("UndoManager: Redo stack empty")
            return

        item = self.redo_stack.pop()
        self.undo_stack.append(item)
        
        self.is_undoing_redoing = True
        try:
            if isinstance(item, UndoAction):
                if item.action_type == 'NAVIGATE':
                    cat = item.metadata.get('category')
                    self._navigate_to(item.block_idx, item.string_idx, cat)
                else:
                    self._apply_data(item.block_idx, item.string_idx, item.new_text, item.cursor_pos)
            elif isinstance(item, GroupAction):
                for action in item.actions:
                    self._apply_data(action.block_idx, action.string_idx, action.new_text, action.cursor_pos)
            elif isinstance(item, StructuralAction):
                self._apply_project_snapshot(item.after_snapshot)
            log_debug(f"UndoManager: Redone item of type {item.action_type if isinstance(item, (UndoAction, StructuralAction)) else 'Group'}")
        finally:
            self.is_undoing_redoing = False


    def _get_item_location(self, item: Any, is_undo: bool) -> tuple[int, int]:
        if isinstance(item, UndoAction):
            return item.block_idx, item.string_idx
        elif isinstance(item, GroupAction) and item.actions:
            # For undo, we jump to the last action in group (newest focus)
            # For redo, we jump to the first action (usually where it started)
            idx = -1 if is_undo else 0
            return item.actions[idx].block_idx, item.actions[idx].string_idx
        return -1, -1

    def _navigate_to(self, block_idx: int, string_idx: int, category: str = None):
        if block_idx == -1: return

        current_block = self.mw.data_store.current_block_idx
        current_string = self.mw.data_store.current_string_idx
        
        needs_string_refresh = False
        
        if current_block != block_idx or getattr(self.mw, 'current_category_name', None) != category:
            if hasattr(self.mw, 'block_list_widget'):
                self.mw.block_list_widget.select_block_by_index(block_idx, category)
            needs_string_refresh = True
            
        if current_string != string_idx or needs_string_refresh:
            if hasattr(self.mw, 'list_selection_handler'):
                self.mw.list_selection_handler.string_selected_from_preview(string_idx)
                
        if hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
            self.mw.edited_text_edit.setFocus()
            from PyQt5.QtGui import QTextCursor
            cursor = self.mw.edited_text_edit.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.mw.edited_text_edit.setTextCursor(cursor)

    def _apply_data(self, block_idx: int, string_idx: int, text: str, cursor_pos: Optional[int] = None):
        # We assume the navigation has already been performed or is not needed
        # but we stay at the correct focus just in case (though we should already be there)
        self._navigate_to(block_idx, string_idx)

        # 2. Apply text to data and UI
        was_programmatic = self.mw.is_programmatically_changing_text
        self.mw.is_programmatically_changing_text = True
        try:
            # Update data processor
            self.mw.data_processor.update_edited_data(block_idx, string_idx, text)
            
            # Update editor text if it's currently showing this string
            if self.mw.data_store.current_block_idx == block_idx and self.mw.data_store.current_string_idx == string_idx:
                editor_text = self.mw.current_game_rules.get_text_representation_for_editor(text)
                self.mw.edited_text_edit.setPlainText(editor_text)
                
                if cursor_pos is not None:
                    cursor = self.mw.edited_text_edit.textCursor()
                    cursor.setPosition(min(cursor_pos, len(editor_text)))
                    self.mw.edited_text_edit.setTextCursor(cursor)
                else:
                    cursor = self.mw.edited_text_edit.textCursor()
                    cursor.movePosition(QTextCursor.End)
                    self.mw.edited_text_edit.setTextCursor(cursor)
                
                # Perform necessary issue rescan
                if hasattr(self.mw, 'editor_operation_handler'):
                    self.mw.editor_operation_handler._rescan_issues_for_current_string(block_idx, string_idx, text)

                # Perform necessary UI refreshes
                self.mw.editor_operation_handler.preview_update_timer.start(50)
                self.mw.ui_updater.update_title()
                self.mw.ui_updater.update_status_bar()
                self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)

                # Dynamically calculate which sublines remain edited relative to saved file
                text_from_saved_file = self.mw.data_processor._get_string_from_source(block_idx, string_idx, self.mw.data_store.edited_file_data, "edited_file_data")
                if text_from_saved_file is None:
                    text_from_saved_file = self.mw.data_processor._get_string_from_source(block_idx, string_idx, self.mw.data_store.data, "original_data")
                if text_from_saved_file is None:
                    text_from_saved_file = ""
                    
                saved_lines = str(text_from_saved_file).split('\n')
                
                # We need actual_text_with_spaces representation
                actual_text_with_spaces = self.mw.utils.convert_dots_to_spaces_from_editor(text) if hasattr(self.mw, 'utils') else text
                # Actually 'text' parameter in _apply_data is ALREADY the raw actual_text_with_spaces
                curr_lines = text.split('\n')
                
                self.mw.data_store.edited_sublines.clear()
                for i, curr_line in enumerate(curr_lines):
                    if i >= len(saved_lines) or curr_line != saved_lines[i]:
                        self.mw.data_store.edited_sublines.add(i)
                
                # Re-apply highlights
                self.mw.ui_updater._apply_highlights_to_editor(self.mw.edited_text_edit, block_idx, string_idx)
                
                if hasattr(self.mw.edited_text_edit, 'lineNumberArea'):
                    self.mw.edited_text_edit.lineNumberArea.update()
                
        finally:
            self.mw.is_programmatically_changing_text = was_programmatic

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
