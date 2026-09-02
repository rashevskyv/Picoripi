"""ListSelectionHandler composition."""
from __future__ import annotations

from typing import Any, Optional
from PyQt6.QtCore import QTimer, QObject
from handlers.base_handler import BaseHandler
from handlers.list_selection.navigation_mixin import NavigationMixin
from handlers.list_selection.virtual_selection_mixin import VirtualSelectionMixin
from handlers.list_selection.physical_selection_mixin import PhysicalSelectionMixin
from handlers.list_selection.rename_mixin import RenameMixin
from handlers.list_selection.filter_mixin import FilterMixin
from handlers.list_selection.problem_mixin import ProblemMixin
from handlers.list_selection.speaker_retention_mixin import SpeakerRetentionMixin


class ListSelectionHandler(
    NavigationMixin,
    VirtualSelectionMixin,
    PhysicalSelectionMixin,
    RenameMixin,
    FilterMixin,
    ProblemMixin,
    SpeakerRetentionMixin,
    BaseHandler,
):
    """Handler for list selection operations."""

    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor, ui_updater)
        self._restoring_selection: bool = False
        self._target_string_idx: Optional[int] = None
        self._target_block_idx: Optional[int] = None
        if isinstance(self.mw, QObject):
            self._cursor_visible_timer = QTimer(self.mw)
            self._selection_timer = QTimer(self.mw)
        else:
            self._cursor_visible_timer = QTimer()
            self._selection_timer = QTimer()
        self._cursor_visible_timer.setSingleShot(True)
        self._cursor_visible_timer.timeout.connect(self._on_cursor_visible_timeout)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.timeout.connect(self._on_selection_timer_timeout)
        self._pending_selection_line: Optional[int] = None

        # Sub-handlers for Single Responsibility Principle
        # First, import them locally to avoid circular import issues
        from handlers.category_handler import CategoryHandler
        from handlers.speaker_handler import SpeakerHandler
        from handlers.virtual_folder_handler import VirtualFolderHandler

        self.category_handler = getattr(self.mw, 'category_handler', None)
        if not isinstance(self.category_handler, CategoryHandler):
            self.category_handler = CategoryHandler(self.mw, self.data_processor, self.ui_updater)
            try:
                self.mw.category_handler = self.category_handler
            except AttributeError:
                pass

        self.speaker_handler = getattr(self.mw, 'speaker_handler', None)
        if not isinstance(self.speaker_handler, SpeakerHandler):
            self.speaker_handler = SpeakerHandler(self.mw, self.data_processor, self.ui_updater)
            try:
                self.mw.speaker_handler = self.speaker_handler
            except AttributeError:
                pass

        self.virtual_folder_handler = getattr(self.mw, 'virtual_folder_handler', None)
        if not isinstance(self.virtual_folder_handler, VirtualFolderHandler):
            self.virtual_folder_handler = VirtualFolderHandler(self.mw, self.data_processor, self.ui_updater)
            try:
                self.mw.virtual_folder_handler = self.virtual_folder_handler
            except AttributeError:
                pass

    def cleanup(self) -> None:
        """Stop deferred UI timers owned by this handler."""
        for t_name in ('_cursor_visible_timer', '_selection_timer'):
            timer = getattr(self, t_name, None)
            if timer:
                try:
                    timer.stop()
                except RuntimeError:
                    pass
        self._pending_selection_line = None
