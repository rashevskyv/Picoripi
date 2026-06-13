from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QTextCursor, QIcon
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem, QTreeWidgetItemIterator, QStyle
from utils.logging_utils import log_debug
from utils.constants import APP_VERSION
from utils.utils import convert_spaces_to_dots_for_display, convert_dots_to_spaces_from_editor, remove_curly_tags, calculate_string_width, calculate_strict_string_width, remove_all_tags
from core.glossary_manager import GlossaryOccurrence

class UIUpdater:
    """U i updater implementation."""
    def __init__(self, main_window, data_processor):
        """Initialize a new instance."""
        self.mw = main_window
        self.data_processor = data_processor
        
        from .updaters.title_status_bar_updater import TitleStatusBarUpdater
        self.title_status_bar_updater = TitleStatusBarUpdater(main_window, data_processor)
        
        from .updaters.block_list_updater import BlockListUpdater
        self.block_list_updater = BlockListUpdater(main_window, data_processor)
        
        from .updaters.preview_updater import PreviewUpdater
        self.preview_updater = PreviewUpdater(main_window, data_processor)

    def get_tree_state(self) -> dict:
        """Get the tree state."""
        return self.block_list_updater.get_tree_state()

    def apply_tree_state(self, state: dict):
        """Apply tree state."""
        self.block_list_updater.apply_tree_state(state)

    def highlight_glossary_occurrence(self, occurrence: GlossaryOccurrence):
        """Highlight glossary occurrence."""
        self.preview_updater.highlight_glossary_occurrence(occurrence)

    def populate_blocks(self, override_folder_id=None, override_block_idx=None):
        """Populate blocks."""
        self.block_list_updater.populate_blocks(override_folder_id, override_block_idx)

    def update_block_item_text_with_problem_count(self, block_idx: int):
        """Update the block item text with problem count."""
        self.block_list_updater.update_block_item_text_with_problem_count(block_idx)

    def update_status_bar(self):
        """Update the status bar."""
        self.title_status_bar_updater.update_status_bar()

    def update_status_bar_selection(self):
        """Update the status bar selection."""
        self.title_status_bar_updater.update_status_bar_selection()

    def clear_status_bar(self):
        """Remove status bar."""
        self.title_status_bar_updater.clear_status_bar()

    def synchronize_original_cursor(self):
        """Synchronize original cursor."""
        self.preview_updater.synchronize_original_cursor()

    def highlight_problem_block(self, block_idx: int, highlight: bool, is_critical: bool = True):
        """Highlight problem block."""
        self.block_list_updater.highlight_problem_block(block_idx, highlight, is_critical)

    def clear_all_problem_block_highlights_and_text(self): 
        """Remove all problem block highlights and text."""
        self.block_list_updater.clear_all_problem_block_highlights_and_text()
            
    def update_title(self):
        """Update the title."""
        self.title_status_bar_updater.update_title()

    def update_plugin_status_label(self):
        """Update the plugin status label."""
        self.title_status_bar_updater.update_plugin_status_label()

    def update_statusbar_paths(self):
        """Update the statusbar paths."""
        self.title_status_bar_updater.update_statusbar_paths()

    def populate_strings_for_block(self, block_idx, category_name=None, force=False):
        """Populate strings for block."""
        self.preview_updater.populate_strings_for_block(block_idx, category_name, force)
            
    def update_text_views(self): 
        """Update the text views."""
        self.preview_updater.update_text_views()

    def update_preview_visibility(self):
        """Update the preview visibility."""
        self.preview_updater.update_preview_visibility()