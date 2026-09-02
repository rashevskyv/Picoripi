"""Virtual tree row/folder/chapter/speaker selection handlers."""
from __future__ import annotations

from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt
from core.data_store import ViewKind
from handlers.list_selection.physical_selection_mixin import _refresh_string_settings_panel


class VirtualSelectionMixin:
    """Virtual tree row/folder/chapter/speaker selection handlers."""

    def refresh_empty_virtual_view_on_click(self, item: QTreeWidgetItem, _column: int) -> None:
        """Recover a restored virtual selection whose indices exist but editor text was not built."""
        mappings = item.data(0, Qt.UserRole + 13) or []
        displayed = getattr(self.mw.data_store, "displayed_string_indices", [])
        preview = getattr(self.mw, "preview_text_edit", None)
        if not mappings or not displayed or preview is None:
            return
        current_text = preview.toPlainText()
        if isinstance(current_text, str) and not current_text:
            self.ui_updater.populate_current_view(force=True)

    def _handle_virtual_row_selection(self, current_item: QTreeWidgetItem) -> None:
        b_idx = current_item.data(0, Qt.UserRole)
        s_idx = current_item.data(0, Qt.UserRole + 1)
        ch_id = current_item.data(0, Qt.UserRole + 11)
        self._clear_pending_speaker_retention((b_idx, s_idx))

        self.mw.data_store.current_block_idx = b_idx
        self.mw.data_store.physical_block_idx = b_idx
        self.mw.data_store.set_view_kind(ViewKind.CHAPTER)
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

        self.ui_updater.populate_current_view(force=True)

        # Find relative index for preview
        target_tuple = (b_idx, s_idx)
        rel_idx = self._get_relative_index(target_tuple)

        if rel_idx != -1:
            if not getattr(self.mw, '_restoring_session_state', False):
                self._schedule_string_selection(rel_idx)
        else:
            self.ui_updater.update_text_views()

        self.ui_updater.update_statusbar_paths()
        self._update_block_toolbar_button_states(-2)

    def _handle_speaker_selection(self, current_item: QTreeWidgetItem) -> None:
        char_name = current_item.data(0, Qt.UserRole + 15)
        pending = self._pending_speaker_retention
        if not pending or pending[0] != char_name:
            self._clear_pending_speaker_retention()

        self.mw.data_store.set_view_kind(ViewKind.SPEAKER)
        self.mw.data_store.current_category_name = None
        self.mw.data_store.current_chapter_id = None
        self.mw.data_store.current_speaker_name = char_name

        # Retrieve pre-calculated mappings from the tree item
        char_mappings = current_item.data(0, Qt.UserRole + 13) or []
        self.mw.data_store.chapter_mappings = char_mappings

        self.ui_updater.populate_current_view(force=True)

        if char_mappings:
            target_idx = -1
            if self._target_string_idx is not None and self._target_block_idx is not None:
                target_tuple = (self._target_block_idx, self._target_string_idx)
                if target_tuple in char_mappings:
                    target_idx = char_mappings.index(target_tuple)

            if target_idx != -1:
                first_mapping = char_mappings[target_idx]
                self.mw.data_store.physical_block_idx = first_mapping[0]
                self.mw.data_store.current_block_idx = first_mapping[0]
                self.mw.data_store.current_string_idx = first_mapping[1]
                self._target_block_idx = None
                self._target_string_idx = None
                if not getattr(self.mw, '_restoring_session_state', False):
                    self._schedule_string_selection(target_idx)
            else:
                first_mapping = char_mappings[0]
                self.mw.data_store.physical_block_idx = first_mapping[0]
                self.mw.data_store.current_block_idx = first_mapping[0]
                self.mw.data_store.current_string_idx = first_mapping[1]
                if not getattr(self.mw, '_restoring_session_state', False):
                    self._schedule_string_selection(0)
        else:
            self.mw.data_store.physical_block_idx = -1
            self.mw.data_store.current_block_idx = -1
            self.mw.data_store.current_string_idx = -1
            self.ui_updater.update_text_views()

        self.ui_updater.update_statusbar_paths()
        self._update_block_toolbar_button_states(-3)

    def _handle_item_selection(self, current_item: QTreeWidgetItem) -> None:
        """Show a reference item as a virtual block without treating it as dialogue."""
        item_name = current_item.data(0, Qt.UserRole + 16)
        mappings = current_item.data(0, Qt.UserRole + 13) or []
        self._clear_pending_speaker_retention()
        self.mw.data_store.set_view_kind(ViewKind.ITEM)
        self.mw.data_store.current_category_name = None
        self.mw.data_store.current_chapter_id = None
        self.mw.data_store.current_speaker_name = item_name
        self.mw.data_store.chapter_mappings = mappings
        self.ui_updater.populate_current_view(force=True)
        if mappings:
            target = (self._target_block_idx, self._target_string_idx)
            target_idx = mappings.index(target) if target in mappings else 0
            block_idx, string_idx = mappings[target_idx]
            self.mw.data_store.physical_block_idx = block_idx
            self.mw.data_store.current_block_idx = block_idx
            self.mw.data_store.current_string_idx = string_idx
            self._target_block_idx = None
            self._target_string_idx = None
            if not getattr(self.mw, '_restoring_session_state', False):
                self._schedule_string_selection(target_idx)
        else:
            self.mw.data_store.physical_block_idx = -1
            self.mw.data_store.current_block_idx = -1
            self.mw.data_store.current_string_idx = -1
            self.ui_updater.update_text_views()
        self.ui_updater.update_statusbar_paths()
        self._update_block_toolbar_button_states(-4)

    def _handle_notated_selection(self, current_item: QTreeWidgetItem) -> None:
        """Show strings grouped by the presence of a translator note."""
        label = current_item.data(0, Qt.UserRole + 19)
        mappings = current_item.data(0, Qt.UserRole + 13) or []
        self._clear_pending_speaker_retention()
        self.mw.data_store.set_view_kind(ViewKind.NOTATED)
        self.mw.data_store.current_category_name = None
        self.mw.data_store.current_chapter_id = None
        self.mw.data_store.current_speaker_name = label
        self.mw.data_store.chapter_mappings = mappings
        self.ui_updater.populate_current_view(force=True)
        if mappings:
            target = (self._target_block_idx, self._target_string_idx)
            target_idx = mappings.index(target) if target in mappings else 0
            block_idx, string_idx = mappings[target_idx]
            self.mw.data_store.physical_block_idx = block_idx
            self.mw.data_store.current_block_idx = block_idx
            self.mw.data_store.current_string_idx = string_idx
            self._target_block_idx = None
            self._target_string_idx = None
            if not getattr(self.mw, '_restoring_session_state', False):
                self._schedule_string_selection(target_idx)
        else:
            self.mw.data_store.physical_block_idx = -1
            self.mw.data_store.current_block_idx = -1
            self.mw.data_store.current_string_idx = -1
            self.ui_updater.update_text_views()
        self.ui_updater.update_statusbar_paths()
        self._update_block_toolbar_button_states(-5)

    def _handle_chapter_selection(self, chapter_id: int, stored_mappings=None) -> None:
        self._clear_pending_speaker_retention()
        self.mw.data_store.set_view_kind(ViewKind.CHAPTER)
        self.mw.data_store.current_category_name = None
        self.mw.data_store.current_chapter_id = chapter_id
        self.mw.data_store.current_speaker_name = None

        # Fetch mappings from MemePalace client
        chapter_mappings = list(stored_mappings) if stored_mappings is not None else []
        if stored_mappings is None:
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

        self.ui_updater.populate_current_view(force=True)

        if chapter_mappings:
            target_idx = -1
            if self._target_string_idx is not None and self._target_block_idx is not None:
                target_tuple = (self._target_block_idx, self._target_string_idx)
                if target_tuple in chapter_mappings:
                    target_idx = chapter_mappings.index(target_tuple)

            if target_idx != -1:
                first_mapping = chapter_mappings[target_idx]
                self.mw.data_store.physical_block_idx = first_mapping[0]
                self.mw.data_store.current_block_idx = first_mapping[0]
                self.mw.data_store.current_string_idx = first_mapping[1]
                self._target_block_idx = None
                self._target_string_idx = None
                if not getattr(self.mw, '_restoring_session_state', False):
                    self._schedule_string_selection(target_idx)
            else:
                first_mapping = chapter_mappings[0]
                self.mw.data_store.physical_block_idx = first_mapping[0]
                self.mw.data_store.current_block_idx = first_mapping[0]
                self.mw.data_store.current_string_idx = first_mapping[1]
                if not getattr(self.mw, '_restoring_session_state', False):
                    self._schedule_string_selection(0)
        else:
            self.mw.data_store.physical_block_idx = -1
            self.mw.data_store.current_block_idx = -1
            self.mw.data_store.current_string_idx = -1
            self.ui_updater.update_text_views()

        self.ui_updater.update_statusbar_paths()
        self._update_block_toolbar_button_states(-2)

    def _handle_folder_selection(self) -> None:
        self._clear_pending_speaker_retention()
        self.mw.data_store.current_block_idx = -1
        self.mw.data_store.physical_block_idx = -1
        self.mw.data_store.set_view_kind(ViewKind.PHYSICAL)
        self.mw.data_store.current_string_idx = -1
        self.mw.data_store.current_category_name = None
        self.mw.data_store.current_chapter_id = None
        self.mw.data_store.current_speaker_name = None
        self.mw.data_store.chapter_mappings = []
        self.ui_updater.populate_strings_for_block(-1)
        if hasattr(self.mw, 'string_settings_updater'):
            _refresh_string_settings_panel(self.mw)
        self._update_block_toolbar_button_states(-1)

    def _handle_aggregate_virtual_selection(self, current_item: QTreeWidgetItem) -> None:
        """Show every unique game row contained in a virtual parent folder."""
        mappings = list(current_item.data(0, Qt.UserRole + 13) or [])
        self._clear_pending_speaker_retention()
        self.mw.data_store.set_view_kind(ViewKind.CHAPTER)
        self.mw.data_store.current_category_name = None
        self.mw.data_store.current_chapter_id = None
        self.mw.data_store.current_speaker_name = None
        self.mw.data_store.chapter_mappings = mappings

        if mappings:
            target = (self._target_block_idx, self._target_string_idx)
            target_idx = mappings.index(target) if target in mappings else 0
            block_idx, string_idx = mappings[target_idx]
            self.mw.data_store.physical_block_idx = block_idx
            self.mw.data_store.current_block_idx = block_idx
            self.mw.data_store.current_string_idx = string_idx
        else:
            self.mw.data_store.physical_block_idx = -1
            self.mw.data_store.current_block_idx = -1
            self.mw.data_store.current_string_idx = -1

        self.ui_updater.populate_current_view(force=True)
        if mappings and not getattr(self.mw, '_restoring_session_state', False):
            self._schedule_string_selection(target_idx)
        elif not mappings:
            self.ui_updater.update_text_views()
        self._target_block_idx = None
        self._target_string_idx = None
        self.ui_updater.update_statusbar_paths()
        self._update_block_toolbar_button_states(-2)
