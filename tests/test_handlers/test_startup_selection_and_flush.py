"""Regressions for two startup faults that fed each other.

1. The restored block was selected in the tree but showed no strings until the
   user clicked another block: the deliberate restore call to ``block_selected``
   was dropped by the "ignore selection churn while loading" guard.
2. The empty editor left by (1) was then persisted over a real translation:
   ``text_edited`` only guarded against programmatic text changes, not against
   loading, so clearing/refilling the editor scheduled a save of "".
"""
from unittest.mock import MagicMock

import pytest

from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler


class TestBlockSelectedForce:
    def _handler(self, *, loading):
        mw = MagicMock()
        mw.is_loading_data = loading
        handler = ListSelectionHandler(mw, MagicMock(), MagicMock())
        handler._restoring_selection = False
        handler._handle_physical_block_selection = MagicMock()
        return handler, mw

    def _item(self, block_index=0):
        from PyQt6.QtCore import Qt

        item = MagicMock()
        # Only the block-index role carries a value; the virtual-row, aggregate,
        # category and chapter roles stay None so the physical-block branch runs.
        item.data.side_effect = (
            lambda _col, role: block_index if role == Qt.UserRole else None
        )
        return item

    def test_selection_ignored_while_loading(self):
        """Incidental selection signals during a load stay ignored."""
        handler, _ = self._handler(loading=True)
        handler.block_selected(self._item(), None)
        handler._handle_physical_block_selection.assert_not_called()

    def test_forced_selection_runs_while_loading(self):
        """A deliberate restore must load the block even during a load."""
        handler, _ = self._handler(loading=True)
        handler.block_selected(self._item(), None, force=True)
        handler._handle_physical_block_selection.assert_called_once()

    def test_normal_selection_runs_when_not_loading(self):
        handler, _ = self._handler(loading=False)
        handler.block_selected(self._item(), None)
        handler._handle_physical_block_selection.assert_called_once()

    def test_restoring_selection_guard_still_applies(self):
        handler, _ = self._handler(loading=False)
        handler._restoring_selection = True
        handler.block_selected(self._item(), None)
        handler._handle_physical_block_selection.assert_not_called()


class TestEditorFlushGuards:
    def _handler(self, *, loading=False, programmatic=False):
        mw = MagicMock()
        mw.is_loading_data = loading
        mw.is_programmatically_changing_text = programmatic
        mw.data_store.physical_block_idx = 0
        mw.data_store.current_string_idx = 1
        handler = TextOperationHandler(mw, MagicMock(), MagicMock())
        handler.preview_update_timer = MagicMock()
        return handler, mw

    def test_text_edited_ignored_while_loading(self):
        """Clearing the editor during a load must not schedule a save."""
        handler, _ = self._handler(loading=True)
        handler.text_edited()
        handler.preview_update_timer.start.assert_not_called()

    def test_text_edited_ignored_when_programmatic(self):
        handler, _ = self._handler(programmatic=True)
        handler.text_edited()
        handler.preview_update_timer.start.assert_not_called()

    def test_text_edited_schedules_for_a_real_edit(self):
        handler, _ = self._handler()
        handler.text_edited()
        handler.preview_update_timer.start.assert_called_once()

    def test_flush_refuses_to_write_while_loading(self):
        """A timeout that fires after a load starts must not persist the editor."""
        handler, mw = self._handler(loading=True)
        handler._debounce_block_idx = 0
        handler._debounce_string_idx = 1
        handler._on_preview_update_timer_timeout()
        # Nothing was read from the editor, so nothing could be written.
        mw.edited_text_edit.toPlainText.assert_not_called()

    def test_flush_refuses_while_programmatic(self):
        handler, mw = self._handler(programmatic=True)
        handler._debounce_block_idx = 0
        handler._debounce_string_idx = 1
        handler._on_preview_update_timer_timeout()
        mw.edited_text_edit.toPlainText.assert_not_called()
