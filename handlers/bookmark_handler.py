# --- START OF FILE handlers/bookmark_handler.py ---
import uuid
from typing import Any, Optional
from PyQt5.QtWidgets import QMessageBox, QInputDialog, QTreeWidgetItemIterator
from PyQt5.QtCore import Qt, QTimer
from .base_handler import BaseHandler
from utils.logging_utils import log_info, log_debug

class BookmarkHandler(BaseHandler):
    """
    Handler for managing and navigating text line bookmarks.
    Bookmarks are saved persistently inside settings.json.
    """
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        super().__init__(main_window, data_processor, ui_updater)

    def add_bookmark(self) -> None:
        """Create a new bookmark at the current line of the active block."""
        block_idx = self.data_store.current_block_idx
        string_idx = self.data_store.current_string_idx

        if block_idx == -1 or string_idx == -1:
            QMessageBox.warning(
                self.mw,
                "Add Bookmark",
                "Please select a block and a string to bookmark."
            )
            return

        # Fetch string text preview
        text, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        text_str = str(text) if text is not None else ""
        text_preview = text_str.replace('\n', ' ').strip()
        if len(text_preview) > 35:
            text_preview = text_preview[:35] + "..."

        block_name = self.mw.data_store.block_names.get(str(block_idx), f"Block {block_idx}")
        default_name = f"Line {string_idx + 1}: {text_preview}" if text_preview else f"Line {string_idx + 1}"

        name, ok = QInputDialog.getText(
            self.mw,
            "Add Bookmark",
            "Enter Bookmark Name:",
            text=default_name
        )

        if ok and name.strip():
            # Get project name if project is active
            project_name = None
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                project_name = self.mw.project_manager.project.name

            bookmark = {
                "id": str(uuid.uuid4()),
                "name": name.strip(),
                "project_name": project_name,
                "block_name": block_name,
                "block_idx": block_idx,
                "string_idx": string_idx,
                "text_preview": text_preview
            }

            # Initialize bookmarks list if not exists
            if not hasattr(self.mw, 'bookmarks') or self.mw.bookmarks is None:
                self.mw.bookmarks = []

            self.mw.bookmarks.append(bookmark)
            self.mw.settings_manager.save_settings()
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                self.mw.project_manager.save_settings_to_project(self.mw)
            self.update_bookmarks_menu()
            
            log_info(f"Bookmark added: {name.strip()} in block {block_name} at line {string_idx + 1}")

    def jump_to_bookmark(self, bookmark_id: str) -> None:
        """Navigate to the block and line index specified by the bookmark."""
        bookmarks = getattr(self.mw, 'bookmarks', [])
        bookmark = None
        for b in bookmarks:
            if b.get('id') == bookmark_id:
                bookmark = b
                break

        if not bookmark:
            log_debug(f"Bookmark with ID {bookmark_id} not found.")
            return

        # Check if project matches
        if bookmark.get('project_name'):
            current_project_name = None
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                current_project_name = self.mw.project_manager.project.name

            if current_project_name != bookmark.get('project_name'):
                QMessageBox.warning(
                    self.mw,
                    "Jump to Bookmark",
                    f"This bookmark belongs to project '{bookmark.get('project_name')}', "
                    f"but the currently active project is '{current_project_name or 'None'}'."
                )
                return

        block_idx = bookmark.get('block_idx')
        string_idx = bookmark.get('string_idx')

        if block_idx is None or string_idx is None:
            return

        # Perform jumps
        if self.mw.data_store.current_block_idx != block_idx:
            # Find and set current item in tree view
            iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
            found_item = None
            while iterator.value():
                item = iterator.value()
                # Check for matching block index, avoiding virtual category nodes
                if item.data(0, Qt.UserRole) == block_idx and item.data(0, Qt.UserRole + 10) is None:
                    found_item = item
                    break
                iterator += 1

            if found_item:
                self.mw.block_list_widget.setCurrentItem(found_item)
                # Defer string selection to allow UI update to finish
                QTimer.singleShot(80, lambda: self.mw.list_selection_handler.select_string_by_absolute_index(string_idx))
            else:
                log_debug(f"Could not find block {block_idx} in the list widget tree.")
        else:
            self.mw.list_selection_handler.select_string_by_absolute_index(string_idx)

    def clear_bookmarks(self) -> None:
        """Clear all saved bookmarks after user confirmation."""
        bookmarks = getattr(self.mw, 'bookmarks', [])
        if not bookmarks:
            return

        reply = QMessageBox.question(
            self.mw,
            "Clear Bookmarks",
            "Are you sure you want to delete all bookmarks?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.mw.bookmarks = []
            self.mw.settings_manager.save_settings()
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                self.mw.project_manager.save_settings_to_project(self.mw)
            self.update_bookmarks_menu()
            log_info("All bookmarks cleared.")

    def update_bookmarks_menu(self) -> None:
        """Redraw bookmarks dynamically in the Bookmarks menu."""
        if not hasattr(self.mw, 'bookmarks_menu') or not self.mw.bookmarks_menu:
            return

        self.mw.bookmarks_menu.clear()
        self.mw.bookmarks_menu.addAction(self.mw.add_bookmark_action)
        self.mw.bookmarks_menu.addAction(self.mw.clear_bookmarks_action)
        self.mw.bookmarks_menu.addSeparator()

        bookmarks = getattr(self.mw, 'bookmarks', [])
        if not bookmarks:
            no_bookmarks_action = self.mw.bookmarks_menu.addAction("No Bookmarks")
            no_bookmarks_action.setEnabled(False)
            return

        # Populate bookmarks
        for b in bookmarks:
            block_name = b.get('block_name', 'Unknown Block')
            string_idx = b.get('string_idx', 0)
            name = b.get('name', 'Bookmark')
            
            # Format display text: "{Bookmark Name} ({Block}, Line {Num})"
            display_text = f"{name} ({block_name}, Line {string_idx + 1})"
            
            action = self.mw.bookmarks_menu.addAction(display_text)
            bookmark_id = b.get('id')
            # Capture block_id inside slot lambda
            action.triggered.connect(
                lambda checked, b_id=bookmark_id: self.jump_to_bookmark(b_id)
            )
