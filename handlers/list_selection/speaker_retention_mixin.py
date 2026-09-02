"""Speaker retention and save helpers delegated to SpeakerHandler."""
from __future__ import annotations

from typing import Optional, Tuple
from PyQt6.QtWidgets import QTreeWidgetItem


class SpeakerRetentionMixin:
    """Speaker retention and save helpers delegated to SpeakerHandler."""

    @property
    def _pending_speaker_retention(self) -> Optional[Tuple[str, Tuple[int, int], int]]:
        return self.speaker_handler._pending_speaker_retention

    @_pending_speaker_retention.setter
    def _pending_speaker_retention(self, val: Optional[Tuple[str, Tuple[int, int], int]]) -> None:
        self.speaker_handler._pending_speaker_retention = val

    def _clear_pending_speaker_retention(self, next_tuple: Optional[Tuple[int, int]] = None) -> None:
        """Drop a temporarily retained speaker row once the user navigates away from it."""
        self.speaker_handler._clear_pending_speaker_retention(next_tuple)

    def _restore_editor_focus_after_speaker_save(self) -> None:
        """Return focus from the editable speaker combobox to the main editor."""
        self.speaker_handler._restore_editor_focus_after_speaker_save()

    def _expand_item_ancestors(self, item: QTreeWidgetItem) -> None:
        """Ensure the selected virtual folder remains visible after a tree rebuild."""
        self.speaker_handler._expand_item_ancestors(item)

    def save_speaker_for_current_string(self, char_name: str) -> None:
        """Save speaker assignment for the current string and refresh UI."""
        self.speaker_handler.save_speaker_for_current_string(char_name)

    def save_chapter_for_current_string(self, structure_id=None) -> None:
        """Save a manual Story structure assignment for the current string."""
        self.speaker_handler.save_chapter_for_current_string(structure_id)

    def save_character_for_current_string(self, char_name: str) -> None:
        """Alias for save_speaker_for_current_string to maintain compatibility."""
        self.speaker_handler.save_character_for_current_string(char_name)
