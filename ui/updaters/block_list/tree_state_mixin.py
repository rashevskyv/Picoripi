"""Block-tree expansion/selection state capture and restore."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItemIterator
from utils.logging_utils import log_info

class TreeStateMixin:
    """Block-tree expansion/selection state capture and restore."""

    def get_tree_state(self) -> dict:
        """Returns the current expansion and selection state of the block tree."""
        if not self.mw.block_list_widget:
            return {}

        expanded_ids = []
        expanded_locators = []
        selected_id = None
        selected_type = None # 'block', 'folder', 'category'
        selected_locator = None

        current_item = self.mw.block_list_widget.currentItem()

        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            item = iterator.value()

            # Identify the item
            item_id = None
            item_type = None

            # Check if it's a block
            block_idx = item.data(0, Qt.ItemDataRole.UserRole)
            category_name = item.data(0, Qt.ItemDataRole.UserRole + 10)
            folder_id = item.data(0, Qt.ItemDataRole.UserRole + 1)
            chapter_id = item.data(0, Qt.ItemDataRole.UserRole + 11)

            if chapter_id is not None:
                item_id = f"chapter_{chapter_id}"
                item_type = 'chapter'
            elif folder_id is not None:
                item_id = f"folder_{folder_id}"
                item_type = 'folder'
            elif category_name is not None:
                parent = item.parent()
                if parent:
                    p_block_idx = parent.data(0, Qt.ItemDataRole.UserRole)
                    item_id = f"cat_{p_block_idx}_{category_name}"
                item_type = 'category'
            elif block_idx is not None:
                item_id = f"block_{block_idx}"
                item_type = 'block'

            if item_id:
                if item.isExpanded():
                    expanded_ids.append(item_id)
                if item == current_item:
                    selected_id = item_id
                    selected_type = item_type

            locator = self._get_tree_item_locator(item)
            if locator:
                if item.isExpanded():
                    expanded_locators.append([list(segment) for segment in locator])
                if item == current_item:
                    selected_locator = [list(segment) for segment in locator]

            iterator += 1

        result = {
            "expanded_ids": expanded_ids,
            "expanded_locators": expanded_locators,
            "selected_id": selected_id,
            "selected_type": selected_type,
            "selected_locator": selected_locator,
            "selected_physical_block_idx": self.mw.data_store.physical_block_idx,
            "selected_string_idx": self.mw.data_store.current_string_idx if (hasattr(self.mw, 'data_store') and hasattr(self.mw.data_store, 'current_string_idx')) else (self.mw.current_string_idx if hasattr(self.mw, 'current_string_idx') else -1)
        }
        log_info(f"UIUpdater: Captured tree state: selected={selected_id}, string_idx={result['selected_string_idx']}")
        return result

    def apply_tree_state(self, state: dict, on_completed=None):
        """Restores the tree expansion and selection from state."""
        if not state or not self.mw.block_list_widget:
            if callable(on_completed):
                on_completed()
            return

        self._tree_state_restore_pending = True

        if self._is_loading_chapters and not state.get("_virtual_ready_retry"):
            retry_state = dict(state)
            retry_state["_virtual_ready_retry"] = True
            self.when_virtual_blocks_ready(
                lambda: self.apply_tree_state(retry_state, on_completed)
            )
            return


        completed = False

        def finish_restore():
            nonlocal completed
            if completed:
                return
            completed = True
            self.mw._restoring_session_state = False
            self._notify_tree_state_ready()
            if callable(on_completed):
                on_completed()

        expanded_ids = set(state.get("expanded_ids", []))
        has_expanded_locators = "expanded_locators" in state
        expanded_locators = {
            self._normalize_tree_locator(locator)
            for locator in state.get("expanded_locators", [])
            if locator
        }
        selected_id = state.get("selected_id")
        selected_locator = self._normalize_tree_locator(state.get("selected_locator"))
        selected_physical_block_idx = state.get("selected_physical_block_idx", -1)
        selected_string_idx = state.get("selected_string_idx", -1)

        # Set a flag indicating that session state is being restored to prevent double loads
        self.mw._restoring_session_state = True

        # 1. Restore Expansion (Signals blocked to avoid redundant updates)
        old_blocked = self.mw.block_list_widget.blockSignals(True)
        try:
            iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
            while iterator.value():
                item = iterator.value()
                item_id = self._get_item_id(item)
                if has_expanded_locators:
                    item.setExpanded(
                        self._get_tree_item_locator(item) in expanded_locators
                    )
                elif item_id in expanded_ids:
                    item.setExpanded(True)
                iterator += 1
        finally:
            self.mw.block_list_widget.blockSignals(old_blocked)

        # 2. Restore Selection (Delayed to ensure tree is stable)
        if selected_locator or selected_id:
            from utils.logging_utils import log_info, log_warning

            def _delayed_select():
                try:
                    from PyQt6 import sip
                except ImportError:
                    import sip

                def safe_isdeleted(obj):
                    try:
                        return sip.isdeleted(obj)
                    except (TypeError, RuntimeError):
                        return False

                try:
                    if not self.mw.block_list_widget or safe_isdeleted(self.mw.block_list_widget):
                        finish_restore()
                        return

                    # Re-find the item to avoid "deleted object" errors
                    target_item = None
                    iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
                    while iterator.value():
                        item = iterator.value()
                        if not safe_isdeleted(item):
                            try:
                                locator_matches = (
                                    selected_locator
                                    and self._get_tree_item_locator(item) == selected_locator
                                )
                                if locator_matches or (
                                    not selected_locator
                                    and self._get_item_id(item) == selected_id
                                ):
                                    target_item = item
                                    break
                            except RuntimeError:
                                pass
                        iterator += 1

                    if target_item and not safe_isdeleted(target_item):
                        log_info(f"UIUpdater: Restoring selection to {selected_id or selected_locator}")
                        self.mw.block_list_widget.setFocus()
                        self.mw.block_list_widget.setCurrentItem(target_item)
                        # Manually trigger block load
                        selection_handler = self.mw.list_selection_handler
                        if selected_physical_block_idx is not None and selected_physical_block_idx >= 0:
                            selection_handler._target_block_idx = selected_physical_block_idx
                            selection_handler._target_string_idx = selected_string_idx
                        # force: this is a deliberate restore, not incidental
                        # selection churn, so it must run even while loading.
                        selection_handler.block_selected(target_item, None, force=True)

                        if selected_string_idx != -1:
                            log_info(f"UIUpdater: Restoring string selection to absolute index {selected_string_idx}")
                            # Further delay for strings to ensure they are populated and mapped
                            from PyQt6.QtCore import QTimer

                            def _select_string_and_restore_scroll():
                                try:
                                    if safe_isdeleted(self.mw.block_list_widget):
                                        return
                                    target_row = (
                                        selected_physical_block_idx,
                                        selected_string_idx,
                                    )
                                    displayed = self.mw.data_store.displayed_string_indices
                                    if target_row in displayed:
                                        self.mw.list_selection_handler.string_selected_from_preview(
                                            displayed.index(target_row)
                                        )
                                    else:
                                        self.mw.list_selection_handler.select_string_by_absolute_index(selected_string_idx)

                                    # Restore scroll & cursor after string is loaded and text edits are populated!
                                    if self.mw.edited_text_edit and not safe_isdeleted(self.mw.edited_text_edit):
                                        self.mw.edited_text_edit.verticalScrollBar().setValue(state.get("v_scroll", 0))
                                        self.mw.edited_text_edit.horizontalScrollBar().setValue(state.get("h_scroll", 0))
                                        if self.mw.preview_text_edit and not safe_isdeleted(self.mw.preview_text_edit):
                                            self.mw.preview_text_edit.verticalScrollBar().setValue(state.get("preview_v_scroll", 0))
                                        if self.mw.original_text_edit and not safe_isdeleted(self.mw.original_text_edit):
                                            self.mw.original_text_edit.verticalScrollBar().setValue(state.get("original_v_scroll", 0))
                                            self.mw.original_text_edit.horizontalScrollBar().setValue(state.get("original_h_scroll", 0))

                                        cursor_pos = state.get("cursor_pos", 0)
                                        try:
                                            doc_len = self.mw.edited_text_edit.document().characterCount() - 1
                                        except Exception:
                                            doc_len = 0

                                        try:
                                            try:
                                                c_pos = int(cursor_pos)
                                            except (TypeError, ValueError):
                                                c_pos = 0
                                            try:
                                                d_len = int(doc_len)
                                            except (TypeError, ValueError):
                                                d_len = 0
                                            pos_to_set = min(c_pos, max(0, d_len))
                                            log_info(f"UIUpdater: Restoring cursor position to {pos_to_set}")
                                        except Exception:
                                            pos_to_set = 0

                                        cursor = self.mw.edited_text_edit.textCursor()
                                        cursor.setPosition(pos_to_set)
                                        self.mw.edited_text_edit.setTextCursor(cursor)
                                        self.mw.edited_text_edit.ensureCursorVisible()
                                except Exception as e:
                                    log_warning(f"UIUpdater: Error in _select_string_and_restore_scroll: {e}")
                                finally:
                                    finish_restore()

                            QTimer.singleShot(200, _select_string_and_restore_scroll)
                        else:
                            finish_restore()
                    else:
                        log_warning(f"UIUpdater: Failed to find item {selected_id or selected_locator} for restoration.")
                        finish_restore()
                except Exception as e:
                    log_warning(f"UIUpdater: Error in _delayed_select: {e}")
                    finish_restore()

            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, _delayed_select)
        else:
            finish_restore()

    def _get_item_id(self, item) -> str:
        """Helper to generate consistent IDs for tree items."""
        if not item: return None

        block_idx = item.data(0, Qt.ItemDataRole.UserRole)
        category_name = item.data(0, Qt.ItemDataRole.UserRole + 10)
        folder_id = item.data(0, Qt.ItemDataRole.UserRole + 1)
        chapter_id = item.data(0, Qt.ItemDataRole.UserRole + 11)

        if chapter_id is not None:
            return f"chapter_{chapter_id}"
        elif folder_id is not None:
            return f"folder_{folder_id}"
        elif category_name is not None:
            parent = item.parent()
            if parent:
                p_block_idx = parent.data(0, Qt.ItemDataRole.UserRole)
                return f"cat_{p_block_idx}_{category_name}"
        elif block_idx is not None:
            return f"block_{block_idx}"
        return None

    @staticmethod
    def _normalize_tree_locator(locator):
        """Normalize JSON lists and runtime tuples to one comparable locator."""
        if not locator:
            return None
        return tuple(tuple(segment) for segment in locator)

    def _get_tree_item_locator(self, item):
        """Return an exact, rebuild-safe path for real and virtual tree nodes."""
        if item is None:
            return None
        path = []
        cursor = item
        roles = (0, 1, 10, 11, 15, 16, 17, 18, 19)
        while cursor is not None:
            stable_label = cursor.data(0, Qt.ItemDataRole.UserRole + 4)
            if stable_label is None:
                stable_label = cursor.text(0)
            path.append(tuple(
                [stable_label]
                + [cursor.data(0, Qt.ItemDataRole.UserRole + offset) for offset in roles]
            ))
            cursor = cursor.parent()
        return tuple(reversed(path))
