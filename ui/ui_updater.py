# --- START OF FILE ui/ui_updater.py ---
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QTextCursor, QIcon
from PyQt5.QtWidgets import QApplication, QTreeWidgetItem, QTreeWidgetItemIterator, QStyle
from utils.logging_utils import log_debug
from utils.constants import APP_VERSION
from utils.utils import convert_spaces_to_dots_for_display, convert_dots_to_spaces_from_editor, remove_curly_tags, calculate_string_width, calculate_strict_string_width, remove_all_tags
from core.glossary_manager import GlossaryOccurrence

class UIUpdater:
    def __init__(self, main_window, data_processor):
        self.mw = main_window
        self.data_processor = data_processor
        
        from .updaters.title_status_bar_updater import TitleStatusBarUpdater
        self.title_status_bar_updater = TitleStatusBarUpdater(main_window, data_processor)
        
        from .updaters.block_list_updater import BlockListUpdater
        self.block_list_updater = BlockListUpdater(main_window, data_processor)
        
        from .updaters.preview_updater import PreviewUpdater
        self.preview_updater = PreviewUpdater(main_window, data_processor)

    def get_tree_state(self) -> dict:
        return self.block_list_updater.get_tree_state()

    def apply_tree_state(self, state: dict):
        self.block_list_updater.apply_tree_state(state)

    def _get_item_id(self, item) -> str:
        return self.block_list_updater._get_item_id(item)

    def highlight_glossary_occurrence(self, occurrence: GlossaryOccurrence):
        self.preview_updater.highlight_glossary_occurrence(occurrence)

    def _get_aggregated_problems_for_block(self, block_idx: int, pre_aggregated_counts: dict = None, category_name: str = None) -> dict:
        return self.block_list_updater._get_aggregated_problems_for_block(block_idx, pre_aggregated_counts, category_name)


    def _apply_issues_and_tooltip(self, item: QTreeWidgetItem, base_display_name: str, problem_counts: dict, problem_definitions: dict):
        self.block_list_updater._apply_issues_and_tooltip(item, base_display_name, problem_counts, problem_definitions)

    def _create_block_tree_item(self, block_idx: int, problem_definitions: dict, pre_aggregated_counts: dict = None) -> QTreeWidgetItem:
        return self.block_list_updater._create_block_tree_item(block_idx, problem_definitions, pre_aggregated_counts)

    def _add_virtual_folder_to_tree(self, parent_item, folder, problem_definitions, current_selection_block_idx, pre_aggregated_counts: dict = None, folder_id_to_select=None):
        self.block_list_updater._add_virtual_folder_to_tree(parent_item, folder, problem_definitions, current_selection_block_idx, pre_aggregated_counts, folder_id_to_select)

    def populate_blocks(self, override_folder_id=None, override_block_idx=None):
        self.block_list_updater.populate_blocks(override_folder_id, override_block_idx)

    def update_block_item_text_with_problem_count(self, block_idx: int):
        self.block_list_updater.update_block_item_text_with_problem_count(block_idx)

    def update_status_bar(self):
        self.title_status_bar_updater.update_status_bar()

    def update_status_bar_selection(self):
        self.title_status_bar_updater.update_status_bar_selection()

    def clear_status_bar(self):
        self.title_status_bar_updater.clear_status_bar()


    def synchronize_original_cursor(self):
        self.preview_updater.synchronize_original_cursor()


    def highlight_problem_block(self, block_idx: int, highlight: bool, is_critical: bool = True):
        self.block_list_updater.highlight_problem_block(block_idx, highlight, is_critical)


    def clear_all_problem_block_highlights_and_text(self): 
        self.block_list_updater.clear_all_problem_block_highlights_and_text()

            
    def update_title(self):
        self.title_status_bar_updater.update_title()

    def update_plugin_status_label(self):
        self.title_status_bar_updater.update_plugin_status_label()

    def update_statusbar_paths(self):
        self.title_status_bar_updater.update_statusbar_paths()

    def _apply_highlights_for_block(self, block_idx: int):
        self.preview_updater._apply_highlights_for_block(block_idx)

    def _apply_highlights_to_editor(self, editor, block_idx: int, string_idx: int):
        self.preview_updater._apply_highlights_to_editor(editor, block_idx, string_idx)

    def _get_all_categorized_indices_for_block(self, block_idx: int) -> set:
        return self.preview_updater._get_all_categorized_indices_for_block(block_idx)

    def populate_strings_for_block(self, block_idx, category_name=None, force=False):
        self.preview_updater.populate_strings_for_block(block_idx, category_name, force)

            
    def update_text_views(self): 
        self.preview_updater.update_text_views()