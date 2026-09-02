"""Problem highlighting and chapters worker completion handlers."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItemIterator
from core.mempalace.story_timeline import StoryVirtualProjection
from core.manual_story_structures import apply_manual_story_structures
from core.i18n import tr

class HighlightMixin:
    """Problem highlighting and chapters worker completion handlers."""

    def update_block_item_text_with_problem_count(self, block_idx: int):
        """Update the block item text with problem count."""
        if not hasattr(self.mw, 'block_list_widget'):
            return

        items_to_update = self._block_items_cache.get(block_idx, [])
        if not items_to_update:
            # Fallback for unit tests where items are added manually without populate_blocks
            iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
            while iterator.value():
                tree_item = iterator.value()
                if tree_item.data(0, Qt.ItemDataRole.UserRole) == block_idx:
                    items_to_update.append(tree_item)
                iterator += 1

        if not items_to_update: return

        problem_definitions = self.mw.current_game_rules.get_problem_definitions() if self.mw.current_game_rules else {}

        self.mw.block_list_widget.blockSignals(True)
        try:
            for item in items_to_update:
                is_virtual_row = item.data(0, Qt.ItemDataRole.UserRole + 12)
                if is_virtual_row:
                    continue
                category_name = item.data(0, Qt.ItemDataRole.UserRole + 10)
                ch_id = item.data(0, Qt.ItemDataRole.UserRole + 11)

                # Try to use stored base name to preserve folder path in compacted view
                base_display_name = item.data(0, Qt.ItemDataRole.UserRole + 4)
                if base_display_name is None:
                    base_display_name = self.mw.data_store.block_names.get(str(block_idx), f"Block {block_idx}")
                    base_display_name = self._get_block_display_name_with_ext(block_idx, base_display_name)

                ch_mappings_from_item = item.data(0, Qt.ItemDataRole.UserRole + 13) if ch_id is not None else None
                block_problem_counts = self._get_aggregated_problems_for_block(block_idx, category_name=category_name, chapter_id=ch_id, chapter_mappings=ch_mappings_from_item)
                self._apply_issues_and_tooltip(item, base_display_name, block_problem_counts, problem_definitions)

            iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
            while iterator.value():
                virtual_item = iterator.value()
                mappings = virtual_item.data(0, Qt.ItemDataRole.UserRole + 13)
                if isinstance(mappings, (list, tuple)):
                    contains_block = False
                    for row in mappings:
                        try:
                            if len(row) == 2 and int(row[0]) == block_idx:
                                contains_block = True
                                break
                        except (TypeError, ValueError):
                            continue
                    if contains_block:
                        self._apply_virtual_issue_indicators(virtual_item)
                iterator += 1
        finally:
            self.mw.block_list_widget.blockSignals(False)

        # Global update to ensure all delegates are re-run for visible ancestors
        self.mw.block_list_widget.viewport().update()

    def highlight_problem_block(self, block_idx: int, highlight: bool, is_critical: bool = True):
        """Highlight problem block."""
        pass

    def clear_all_problem_block_highlights_and_text(self):
        """Remove all problem block highlights and text."""
        if not hasattr(self.mw, 'block_list_widget'): return

        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            item = iterator.value()
            block_idx = item.data(0, Qt.ItemDataRole.UserRole)
            if block_idx is not None:
                base_display_name = item.data(0, Qt.ItemDataRole.UserRole + 4)
                if base_display_name is None:
                    base_display_name = self.mw.data_store.block_names.get(str(block_idx), f"Block {block_idx}")
                    base_display_name = self._get_block_display_name_with_ext(block_idx, base_display_name)

                if item.text(0) != base_display_name:
                    item.setText(0, base_display_name)
                item.setToolTip(0, tr(''))
            iterator += 1

        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.viewport().update()

    def _on_chapters_loaded(self, chapters, mappings):
        """Slot for successful async loading of MemePalace chapters."""
        self._chapters_cache = chapters
        if isinstance(mappings, StoryVirtualProjection):
            project = getattr(getattr(self.mw, "project_manager", None), "project", None)
            self._story_projection_cache = apply_manual_story_structures(mappings, project)
            self._chapters_cache = list(self._story_projection_cache.roots)
            self._chapter_mappings_cache = None
        else:
            self._story_projection_cache = None
            self._chapter_mappings_cache = mappings
        self._is_loading_chapters = False
        self._chapters_load_worker = None
        self.populate_blocks()
        self._notify_virtual_blocks_ready()

    def _on_chapters_load_failed(self, error_msg):
        """Slot for failed async loading of MemePalace chapters."""
        self._chapters_load_error = error_msg
        self._is_loading_chapters = False
        self._chapters_load_worker = None
        self.populate_blocks()
        self._notify_virtual_blocks_ready()
