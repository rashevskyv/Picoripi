"""Undo/redo history snapshots and keyboard handling for Script Markup Studio."""
from __future__ import annotations

import copy

from PyQt6.QtGui import (
    QTextCursor,
    QKeySequence,
)
from core.script_markup import (
    HierarchyMark,
)
from core.script_markup.markup_recipe import MarkupRecipe

from ui.script_markup.constants import (
    _HISTORY_LIMIT,
)


class HistoryMixin:
    """Undo/redo history snapshots and keyboard handling for Script Markup Studio."""

    # -------------------------------------------------------------- history
    def _mark_history_payload(self, mark: HierarchyMark) -> dict:
        return {
            "start_line": mark.start_line,
            "end_line": mark.end_line,
            "depth": mark.depth,
            "type_id": mark.type_id,
            "text": mark.text,
            "label": mark.label,
            "description": mark.description,
            "color": mark.color,
            "order": mark.order,
            "start_col": mark.start_col,
            "end_col": mark.end_col,
            "origin": mark.origin,
            "approved": mark.approved,
        }

    def _history_controls_payload(self) -> dict:
        if not hasattr(self, "hierarchy_depth_spin"):
            return {}
        return {
            "depth": self.hierarchy_depth_spin.value(),
            "type_id": self._current_hierarchy_type_id(),
            "type_text": self.hierarchy_type_combo.currentText(),
            "entity_role": self.hierarchy_role_combo.currentData(),
            "label": self.hierarchy_label_edit.text(),
            "split_text_at_blank_lines": self.hierarchy_split_text_cb.isChecked(),
        }

    def _history_snapshot(self) -> dict:
        return {
            "mode": self.mode,
            "current_raw_path": self.current_raw_path,
            "current_hierarchy_project_path": self.current_hierarchy_project_path,
            "raw_text": self.raw_edit.toPlainText() if hasattr(self, "raw_edit") else "",
            "start_line": self.start_line,
            "end_line": self.end_line,
            "manual_marks": copy.deepcopy(self.manual_marks),
            "recipe": self.recipe.to_dict(),
            "hierarchy_type_definitions": self._hierarchy_type_definitions_payload()
            if hasattr(self, "hierarchy_type_combo") else [],
            "hierarchy_marks": [
                self._mark_history_payload(mark)
                for mark in self.hierarchy_marks
            ],
            "hierarchy_mark_order": self._hierarchy_mark_order,
            "range_edit_mark_key": self._range_edit_mark_key,
            "range_edit_start_line": self._range_edit_start_line,
            "range_edit_end_line": self._range_edit_end_line,
            "range_edit_start_col": self._range_edit_start_col,
            "range_edit_end_col": self._range_edit_end_col,
            "bulk_edit_mark_keys": list(self._bulk_edit_mark_keys),
            "bulk_edit_initial_controls": copy.deepcopy(self._bulk_edit_initial_controls),
            "hierarchy_controls": self._history_controls_payload(),
        }

    def _set_history_suspended(self, suspended: bool):
        self._history_suspended += 1 if suspended else -1
        self._history_suspended = max(0, self._history_suspended)

    def _queue_text_history_record(self):
        if not self._history_ready or self._history_suspended or self._restoring_history:
            return
        self._history_text_dirty = True
        self._history_text_timer.start()

    def _record_pending_text_history(self):
        if not self._history_text_dirty:
            return
        self._record_history()

    def _flush_pending_history(self):
        if self._history_text_dirty:
            self._record_history()

    def _record_history(self, *, force: bool = False) -> bool:
        if (
            not self._history_ready
            or self._history_suspended
            or self._restoring_history
            or not hasattr(self, "raw_edit")
        ):
            return False
        self._history_text_timer.stop()
        self._history_text_dirty = False
        state = self._history_snapshot()
        if not force and self._history_stack and self._history_stack[self._history_index] == state:
            return False
        if self._history_index < len(self._history_stack) - 1:
            self._history_stack = self._history_stack[:self._history_index + 1]
        self._history_stack.append(state)
        if len(self._history_stack) > _HISTORY_LIMIT:
            self._history_stack.pop(0)
        self._history_index = len(self._history_stack) - 1
        self._is_autosaved_dirty = True
        self._autosave_timer.start()
        self._update_save_status()
        return True

    def _restore_history_controls(self, controls: dict):
        if not controls or not hasattr(self, "hierarchy_depth_spin"):
            return
        self.hierarchy_depth_spin.blockSignals(True)
        self.hierarchy_type_combo.blockSignals(True)
        self.hierarchy_role_combo.blockSignals(True)
        self.hierarchy_label_edit.blockSignals(True)
        try:
            self.hierarchy_depth_spin.setValue(int(controls.get("depth", 0)))
            type_id = controls.get("type_id")
            role = str(controls.get("entity_role") or self._role_for_hierarchy_type(type_id))
            role_idx = self.hierarchy_role_combo.findData(role)
            if role_idx >= 0:
                self.hierarchy_role_combo.setCurrentIndex(role_idx)
            visible_type_id = self._visible_hierarchy_type_id(str(type_id)) if type_id else ""
            idx = self._hierarchy_type_index(visible_type_id) if visible_type_id else -1
            if idx >= 0:
                self.hierarchy_type_combo.setCurrentIndex(idx)
            elif controls.get("type_text"):
                self.hierarchy_type_combo.setEditText(str(controls.get("type_text")))
            self.hierarchy_label_edit.setText(str(controls.get("label") or ""))
            self.hierarchy_split_text_cb.setChecked(
                bool(controls.get("split_text_at_blank_lines", False))
            )
        finally:
            self.hierarchy_depth_spin.blockSignals(False)
            self.hierarchy_type_combo.blockSignals(False)
            self.hierarchy_role_combo.blockSignals(False)
            self.hierarchy_label_edit.blockSignals(False)
        self._on_hierarchy_type_changed()

    def _raw_view_state(self) -> dict[str, int]:
        cursor = self.raw_edit.textCursor()
        position_cursor = QTextCursor(self.raw_edit.document())
        position_cursor.setPosition(cursor.position())
        anchor_cursor = QTextCursor(self.raw_edit.document())
        anchor_cursor.setPosition(cursor.anchor())
        return {
            "position_block": position_cursor.blockNumber(),
            "position_column": position_cursor.positionInBlock(),
            "anchor_block": anchor_cursor.blockNumber(),
            "anchor_column": anchor_cursor.positionInBlock(),
            "vertical_scroll": self.raw_edit.verticalScrollBar().value(),
            "horizontal_scroll": self.raw_edit.horizontalScrollBar().value(),
        }

    def _restore_raw_view_state(self, view_state: dict[str, int]):
        document = self.raw_edit.document()

        def position_for(block_key: str, column_key: str) -> int:
            block_number = max(
                0,
                min(
                    int(view_state.get(block_key, 0)),
                    max(0, document.blockCount() - 1),
                ),
            )
            block = document.findBlockByNumber(block_number)
            column = max(0, min(int(view_state.get(column_key, 0)), len(block.text())))
            return block.position() + column

        position = position_for("position_block", "position_column")
        anchor = position_for("anchor_block", "anchor_column")
        cursor = self.raw_edit.textCursor()
        cursor.setPosition(anchor)
        cursor.setPosition(position, QTextCursor.MoveMode.KeepAnchor)
        self.raw_edit.setTextCursor(cursor)
        self.raw_edit.verticalScrollBar().setValue(
            int(view_state.get("vertical_scroll", 0))
        )
        self.raw_edit.horizontalScrollBar().setValue(
            int(view_state.get("horizontal_scroll", 0))
        )

    def _restore_history_state(self, state: dict):
        raw_view_state = self._raw_view_state()
        self._restoring_history = True
        self._set_history_suspended(True)
        try:
            self.mode = str(state.get("mode") or "hierarchy")
            idx = self.mode_combo.findData(self.mode)
            self.mode_combo.blockSignals(True)
            try:
                if idx >= 0:
                    self.mode_combo.setCurrentIndex(idx)
            finally:
                self.mode_combo.blockSignals(False)

            self.current_raw_path = str(state.get("current_raw_path") or "")
            self.current_hierarchy_project_path = str(
                state.get("current_hierarchy_project_path") or ""
            )
            if self.current_hierarchy_project_path and self.mw is not None:
                setattr(
                    self.mw,
                    "script_markup_studio_project_path",
                    self.current_hierarchy_project_path,
                )
            if hasattr(self, "project_state_label"):
                self.project_state_label.setText(
                    f"Markup project: {self.current_hierarchy_project_path}"
                    if self.current_hierarchy_project_path
                    else "Markup project: Not saved"
                )
            self.path_label.setText(self.current_raw_path or "No file loaded")
            self.start_line = int(state.get("start_line", 0))
            self.end_line = int(state.get("end_line", 0))
            self.recipe = MarkupRecipe.from_dict(state.get("recipe") or {})
            self.cb_gutter.blockSignals(True)
            self.cb_continuation.blockSignals(True)
            try:
                self.cb_gutter.setChecked(self.recipe.gutter_speakers)
                self.cb_continuation.setChecked(self.recipe.continuation)
            finally:
                self.cb_gutter.blockSignals(False)
                self.cb_continuation.blockSignals(False)

            self.manual_marks = copy.deepcopy(state.get("manual_marks") or {})
            controls = state.get("hierarchy_controls") or {}
            self._apply_hierarchy_type_payload(
                state.get("hierarchy_type_definitions") or [],
                str(controls.get("type_id")) if controls.get("type_id") else None,
            )
            self.hierarchy_marks = [
                self._hierarchy_mark_from_dict(item)
                for item in state.get("hierarchy_marks", [])
                if isinstance(item, dict)
            ]
            self._hierarchy_mark_order = int(state.get("hierarchy_mark_order", 0))
            self._range_edit_mark_key = state.get("range_edit_mark_key")
            self._range_edit_start_line = state.get("range_edit_start_line")
            self._range_edit_end_line = state.get("range_edit_end_line")
            self._range_edit_start_col = state.get("range_edit_start_col")
            self._range_edit_end_col = state.get("range_edit_end_col")
            self._range_edit_drag_handle = None
            self._bulk_edit_mark_keys = [
                str(key) for key in state.get("bulk_edit_mark_keys", [])
                if self._hierarchy_mark_for_key(str(key)) is not None
            ]
            self._bulk_edit_initial_controls = copy.deepcopy(
                state.get("bulk_edit_initial_controls") or {}
            )

            text = str(state.get("raw_text") or "")
            if self.raw_edit.toPlainText() != text:
                self.raw_edit.setPlainText(text)
            self._restore_history_controls(controls)
            self._update_range_label()
            self._update_mode_controls()
            self._update_range_edit_label()
            self._update_hierarchy_edit_controls()
            self._reset_search_state(clear_highlight=True)
            self._refresh()
            self._apply_raw_extra_selections()
            self._restore_raw_view_state(raw_view_state)
        finally:
            self._set_history_suspended(False)
            self._restoring_history = False
            self._history_text_dirty = False
            self._history_text_timer.stop()

    def _undo_history(self) -> bool:
        self._flush_pending_history()
        if self._history_index <= 0:
            return False
        self._history_index -= 1
        self._restore_history_state(self._history_stack[self._history_index])
        return True

    def _redo_history(self) -> bool:
        self._flush_pending_history()
        if self._history_index >= len(self._history_stack) - 1:
            return False
        self._history_index += 1
        self._restore_history_state(self._history_stack[self._history_index])
        return True

    def _handle_history_key(self, event) -> bool:
        try:
            if event.matches(QKeySequence.StandardKey.Undo):
                handled = self._undo_history()
                if handled:
                    event.accept()
                return handled
            if event.matches(QKeySequence.StandardKey.Redo):
                handled = self._redo_history()
                if handled:
                    event.accept()
                return handled
        except Exception:
            return False
        return False
