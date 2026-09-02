"""Hierarchy range and bulk edit controls for Script Markup Studio."""
from __future__ import annotations


from PyQt6.QtCore import Qt, QPoint
from core.script_markup import (
    HierarchyMark, HierarchyType, HierarchyTypeDefinition,
)
from core.i18n import tr

from ui.script_markup.constants import (
    _SAVE_EDIT_BUTTON_STYLE,
    _STOP_EDIT_BUTTON_STYLE,
)


class RangeEditMixin:
    """Hierarchy range and bulk edit controls for Script Markup Studio."""

    # -------------------------------------------------------- range editing
    def _range_edit_mark(self) -> HierarchyMark | None:
        return self._hierarchy_mark_for_key(self._range_edit_mark_key)

    def _bulk_edit_marks(self) -> list[HierarchyMark]:
        return [
            mark for key in self._bulk_edit_mark_keys
            if (mark := self._hierarchy_mark_for_key(key)) is not None
        ]

    def _is_bulk_hierarchy_editing(self) -> bool:
        return bool(self._bulk_edit_mark_keys)

    def _is_hierarchy_editing(self) -> bool:
        return self._range_edit_mark_key is not None or self._is_bulk_hierarchy_editing()

    def _update_hierarchy_edit_controls(self):
        if not hasattr(self, "hierarchy_mark_btn"):
            return
        editing = self._is_hierarchy_editing()
        bulk = self._is_bulk_hierarchy_editing()
        self.hierarchy_mark_btn.setText("Save edit" if editing else "Mark selection")
        self.hierarchy_mark_btn.setToolTip(
            "Save changed fields to the selected nodes."
            if bulk else
            "Save the edited node type, label, depth, and range."
            if editing else
            "Mark the current selection as a new hierarchy node (Ctrl+M). Quick types: "
            "Ctrl+S Structure, Ctrl+P Speaker, Ctrl+T Text, Ctrl+B Breaker, Ctrl+I Ignore."
        )
        self.hierarchy_mark_btn.setStyleSheet(_SAVE_EDIT_BUTTON_STYLE if editing else "")
        self.hierarchy_clear_btn.setText("Stop edit" if editing else "Clear")
        self.hierarchy_clear_btn.setToolTip(
            "Leave editor mode without saving pending edits."
            if editing else
            "Clear hierarchy marks fully inside the current selection."
        )
        self.hierarchy_clear_btn.setStyleSheet(_STOP_EDIT_BUTTON_STYLE if editing else "")
        self.hierarchy_split_text_cb.setEnabled(
            not editing and self._current_hierarchy_type_id() == HierarchyType.TEXT
        )

    def _update_range_edit_label(self):
        if self._is_bulk_hierarchy_editing():
            self.raw_label.setText(f"✏️ Editing {len(self._bulk_edit_mark_keys)} nodes")
            self.raw_label.setStyleSheet("color: #d97706; font-weight: bold;")
        elif self._range_edit_mark_key and self._range_edit_start_line is not None and self._range_edit_end_line is not None:
            range_text = f"lines {self._range_edit_start_line + 1}-{self._range_edit_end_line + 1}"
            columns = self._range_edit_columns()
            if columns is not None:
                range_text = (
                    f"line {self._range_edit_start_line + 1}, "
                    f"char {columns[0] + 1}-{columns[1]}"
                )
            self.raw_label.setText(f"✏️ Editing node ({range_text})")
            self.raw_label.setStyleSheet("color: #2563eb; font-weight: bold;")
        else:
            if self.mode == "hierarchy":
                self.raw_label.setText("")
            else:
                self.raw_label.setText(tr('⚙️ Automatic rule preview'))
                self.raw_label.setStyleSheet("color: #4b5563; font-style: italic;")

    def _select_hierarchy_type_id(self, type_id: str):
        actual_type_id = str(type_id)
        role = self._role_for_hierarchy_type(actual_type_id)
        role_idx = self.hierarchy_role_combo.findData(role)
        if role_idx >= 0:
            old_blocked = self.hierarchy_role_combo.blockSignals(True)
            try:
                self.hierarchy_role_combo.setCurrentIndex(role_idx)
            finally:
                self.hierarchy_role_combo.blockSignals(old_blocked)
        type_id = self._visible_hierarchy_type_id(actual_type_id)
        type_def = self.hierarchy_type_definitions.get(type_id)
        if type_def is None:
            label = str(type_id).removeprefix("custom:").replace("_", " ").title()
            type_def = HierarchyTypeDefinition(
                type_id,
                label,
                f"Custom hierarchy type: {label}.",
                self._default_custom_type_color(label),
            )
            self.hierarchy_type_definitions[type_id] = type_def
        idx = self._add_hierarchy_type_item(type_def)
        if idx >= 0:
            self.hierarchy_type_combo.setCurrentIndex(idx)
        self._on_hierarchy_type_changed()

    def _load_hierarchy_edit_fields(self, mark: HierarchyMark):
        self.hierarchy_depth_spin.setValue(mark.depth)
        self._select_hierarchy_type_id(mark.type_id)
        text = self._hierarchy_mark_display_text(mark, limit=240)
        self.hierarchy_label_edit.setText(text)

    def _common_value(self, values):
        values = list(values)
        if not values:
            return None
        first = values[0]
        return first if all(value == first for value in values) else None

    def _set_hierarchy_type_mixed(self):
        self.hierarchy_type_combo.blockSignals(True)
        try:
            self.hierarchy_type_combo.setCurrentIndex(-1)
            self.hierarchy_type_combo.setEditText("")
            if self.hierarchy_type_combo.lineEdit() is not None:
                self.hierarchy_type_combo.lineEdit().setPlaceholderText(tr('Mixed'))
        finally:
            self.hierarchy_type_combo.blockSignals(False)
        self.hierarchy_type_combo.setStyleSheet("")

    def _bulk_edit_controls_payload(self) -> dict[str, object]:
        return {
            "depth": self.hierarchy_depth_spin.value(),
            "type_id": self._current_hierarchy_type_id(),
            "type_text": self.hierarchy_type_combo.currentText(),
            "entity_role": self.hierarchy_role_combo.currentData(),
            "label": self.hierarchy_label_edit.text(),
        }

    def _load_bulk_hierarchy_edit_fields(self, marks: list[HierarchyMark]):
        common_depth = self._common_value(mark.depth for mark in marks)
        common_type_id = self._common_value(mark.type_id for mark in marks)
        common_label = self._common_value((mark.text or "").strip() for mark in marks)

        self.hierarchy_depth_spin.setValue(
            int(common_depth) if common_depth is not None else marks[0].depth
        )
        if common_depth is None:
            self.hierarchy_depth_spin.setToolTip(tr('Mixed depth; change this value to apply one depth to all selected nodes.'))
        else:
            self.hierarchy_depth_spin.setToolTip(tr('0 is the top level; higher numbers are nested deeper.'))

        if common_type_id is not None:
            self._select_hierarchy_type_id(str(common_type_id))
        else:
            self._set_hierarchy_type_mixed()

        self.hierarchy_label_edit.setText(str(common_label) if common_label is not None else "")
        self.hierarchy_label_edit.setPlaceholderText(
            "Mixed labels - leave empty to keep existing"
            if common_label is None else
            "Label/text (optional)"
        )
        self._bulk_edit_initial_controls = self._bulk_edit_controls_payload()
        self._bulk_edit_initial_controls.update({
            "depth_common": common_depth is not None,
            "type_common": common_type_id is not None,
            "label_common": common_label is not None,
        })

    def _start_range_edit(self, mark_key: str | None) -> bool:
        mark = self._hierarchy_mark_for_key(mark_key)
        if mark is None:
            return False
        self._bulk_edit_mark_keys = []
        self._bulk_edit_initial_controls = {}
        self._range_edit_mark_key = self._hierarchy_mark_key(mark)
        self._range_edit_start_line = mark.start_line
        self._range_edit_end_line = mark.end_line
        if mark.start_line == mark.end_line:
            block = self.raw_edit.document().findBlockByNumber(mark.start_line)
            line_length = len(block.text()) if block.isValid() else 0
            self._range_edit_start_col = max(
                0,
                min(mark.start_col if mark.start_col is not None else 0, line_length),
            )
            self._range_edit_end_col = max(
                self._range_edit_start_col,
                min(mark.end_col if mark.end_col is not None else line_length, line_length),
            )
        else:
            self._range_edit_start_col = None
            self._range_edit_end_col = None
        self._range_edit_drag_handle = None
        self._load_hierarchy_edit_fields(mark)
        self._update_range_edit_label()
        self._update_hierarchy_edit_controls()
        self._apply_raw_extra_selections()

        block = self.raw_edit.document().findBlockByNumber(mark.start_line)
        if block.isValid():
            self._scroll_raw_to_position(block.position())
        self.raw_edit.setFocus()
        return True

    def _start_bulk_hierarchy_edit(self, mark_keys: list[str]) -> bool:
        seen = set()
        keys = []
        marks = []
        for key in mark_keys:
            key = str(key)
            if key in seen:
                continue
            mark = self._hierarchy_mark_for_key(key)
            if mark is None:
                continue
            seen.add(key)
            keys.append(key)
            marks.append(mark)
        if not marks:
            return False

        self._range_edit_mark_key = None
        self._range_edit_start_line = None
        self._range_edit_end_line = None
        self._range_edit_start_col = None
        self._range_edit_end_col = None
        self._range_edit_drag_handle = None
        self._bulk_edit_mark_keys = keys
        self._load_bulk_hierarchy_edit_fields(marks)
        self._update_range_edit_label()
        self._update_hierarchy_edit_controls()
        self._apply_raw_extra_selections()
        self.flags_list.setFocus()
        return True

    def _stop_range_edit(self):
        self._range_edit_mark_key = None
        self._range_edit_start_line = None
        self._range_edit_end_line = None
        self._range_edit_start_col = None
        self._range_edit_end_col = None
        self._range_edit_drag_handle = None
        self._bulk_edit_mark_keys = []
        self._bulk_edit_initial_controls = {}
        self.hierarchy_depth_spin.setToolTip(tr('0 is the top level; higher numbers are nested deeper.'))
        self.hierarchy_label_edit.setPlaceholderText(tr('Label/text (optional)'))
        self._update_range_edit_label()
        self._update_hierarchy_edit_controls()
        self._apply_raw_extra_selections()

    def _clamp_raw_line(self, line_no: int) -> int:
        return max(0, min(line_no, max(0, self.raw_edit.document().blockCount() - 1)))

    def _raw_event_pos(self, event):
        try:
            return event.position().toPoint()
        except AttributeError:
            return event.pos()

    def _raw_line_at_pos(self, pos: QPoint) -> int | None:
        block = self.raw_edit.cursorForPosition(pos).block()
        if not block.isValid():
            return None
        return block.blockNumber()

    def _raw_column_at_pos(self, pos: QPoint, line_no: int) -> int | None:
        block = self.raw_edit.document().findBlockByNumber(line_no)
        if not block.isValid():
            return None
        cursor = self.raw_edit.cursorForPosition(pos)
        return max(0, min(cursor.position() - block.position(), len(block.text())))

    def _range_edit_columns(self) -> tuple[int, int] | None:
        if (
            self._range_edit_start_line is None
            or self._range_edit_end_line is None
            or self._range_edit_start_line != self._range_edit_end_line
        ):
            return None
        block = self.raw_edit.document().findBlockByNumber(self._range_edit_start_line)
        if not block.isValid():
            return None
        line_length = len(block.text())
        start_col = max(0, min(self._range_edit_start_col or 0, line_length))
        end_col = line_length if self._range_edit_end_col is None else max(
            start_col,
            min(self._range_edit_end_col, line_length),
        )
        return start_col, end_col

    def _range_edit_saved_columns(self) -> tuple[int | None, int | None]:
        columns = self._range_edit_columns()
        if columns is None:
            return None, None
        block = self.raw_edit.document().findBlockByNumber(self._range_edit_start_line)
        start_col, end_col = columns
        if start_col == 0 and end_col >= len(block.text()):
            return None, None
        return start_col, end_col

    def _range_edit_handle_at_pos(self, pos: QPoint) -> str | None:
        if self._range_edit_start_line is None or self._range_edit_end_line is None:
            return None
        start = self._range_edit_start_line
        end = self._range_edit_end_line
        if start == end:
            columns = self._range_edit_columns()
            if columns is not None:
                for handle, column in (("left", columns[0]), ("right", columns[1])):
                    geometry = self._range_column_handle_geometry(start, column)
                    if geometry is None:
                        continue
                    x, top, bottom = geometry
                    if abs(pos.x() - x) <= 6 and top - 3 <= pos.y() <= bottom + 3:
                        return handle
        handles = []
        for handle, line_no in (("start", start), ("end", end)):
            geometry = self._range_handle_geometry(line_no, edge=handle)
            if geometry is None:
                continue
            x, y = geometry
            if pos.x() >= x - 7 and abs(pos.y() - y) <= 6:
                handles.append((abs(pos.y() - y), handle))
        if handles:
            return min(handles)[1]
        return None

    def _update_range_edit_preview(
        self,
        handle: str,
        line_no: int,
        column: int | None = None,
    ) -> bool:
        if self._range_edit_start_line is None or self._range_edit_end_line is None:
            return False
        line_no = self._clamp_raw_line(line_no)
        start = self._range_edit_start_line
        end = self._range_edit_end_line
        if handle == "start":
            start = min(line_no, end)
        elif handle == "end":
            end = max(line_no, start)
        elif handle in ("left", "right"):
            if start != end or line_no != start or column is None:
                return False
            columns = self._range_edit_columns()
            if columns is None:
                return False
            start_col, end_col = columns
            line_length = len(
                self.raw_edit.document().findBlockByNumber(line_no).text()
            )
            column = max(0, min(column, line_length))
            if handle == "left":
                start_col = min(column, end_col)
            else:
                end_col = max(column, start_col)
            if (
                start_col == self._range_edit_start_col
                and end_col == self._range_edit_end_col
            ):
                return True
            self._range_edit_start_col = start_col
            self._range_edit_end_col = end_col
            self._update_range_edit_label()
            self._apply_raw_extra_selections()
            return True
        else:
            return False

        if start == self._range_edit_start_line and end == self._range_edit_end_line:
            return True
        self._range_edit_start_line = start
        self._range_edit_end_line = end
        self._update_range_edit_label()
        self._apply_raw_extra_selections()
        return True

    def _commit_range_edit_preview(self) -> bool:
        mark = self._range_edit_mark()
        if mark is None or self._range_edit_start_line is None or self._range_edit_end_line is None:
            self._stop_range_edit()
            return False
        mark.start_line = min(self._range_edit_start_line, self._range_edit_end_line)
        mark.end_line = max(self._range_edit_start_line, self._range_edit_end_line)
        mark.start_col, mark.end_col = self._range_edit_saved_columns()
        self._range_edit_mark_key = self._hierarchy_mark_key(mark)
        self._range_edit_start_line = mark.start_line
        self._range_edit_end_line = mark.end_line
        self._refresh()
        self._update_range_edit_label()
        return True

    def _replace_active_edit_key(self, old_key: str, new_key: str):
        if self._range_edit_mark_key == old_key:
            self._range_edit_mark_key = new_key
        if old_key in self._collapsed_hierarchy_keys:
            self._collapsed_hierarchy_keys.remove(old_key)
            self._collapsed_hierarchy_keys.add(new_key)
        if old_key in self._outline_expansion_overrides:
            self._outline_expansion_overrides[new_key] = self._outline_expansion_overrides.pop(old_key)
        self._bulk_edit_mark_keys = [
            new_key if key == old_key else key
            for key in self._bulk_edit_mark_keys
        ]

    def _constrain_descendants_to_edited_range(
        self,
        parent: HierarchyMark,
        *,
        old_start: int,
        old_end: int,
        old_depth: int,
    ) -> tuple[int, int]:
        """Clamp former descendants to an edited parent's new line range.

        Descendants that no longer intersect the parent cannot retain a valid
        nested range, so they and their nested children are removed.
        """

        if parent.type_id != HierarchyType.STRUCTURE:
            return 0, 0
        if parent.start_line <= old_start and parent.end_line >= old_end:
            return 0, 0

        descendants = [
            mark for mark in self.hierarchy_marks
            if mark is not parent
            and mark.depth > old_depth
            and old_start <= mark.start_line
            and mark.end_line <= old_end
        ]
        if not descendants:
            return 0, 0

        removed_ids: set[int] = set()
        adjusted = 0
        for mark in descendants:
            new_start = max(mark.start_line, parent.start_line)
            new_end = min(mark.end_line, parent.end_line)
            if new_start > new_end:
                removed_ids.add(id(mark))
                continue
            if new_start == mark.start_line and new_end == mark.end_line:
                continue
            old_key = self._hierarchy_mark_key(mark)
            mark.start_line = new_start
            mark.end_line = new_end
            self._replace_active_edit_key(old_key, self._hierarchy_mark_key(mark))
            adjusted += 1

        if removed_ids:
            removed_keys = {
                self._hierarchy_mark_key(mark)
                for mark in descendants
                if id(mark) in removed_ids
            }
            self.hierarchy_marks = [
                mark for mark in self.hierarchy_marks if id(mark) not in removed_ids
            ]
            self._collapsed_hierarchy_keys.difference_update(removed_keys)
            self._outline_reveal_keys.difference_update(removed_keys)
            for key in removed_keys:
                self._outline_expansion_overrides.pop(key, None)

        return adjusted, len(removed_ids)

    def _save_bulk_hierarchy_edit(self) -> bool:
        marks = self._bulk_edit_marks()
        if not marks:
            self._stop_range_edit()
            return False

        initial = dict(self._bulk_edit_initial_controls)
        current = self._bulk_edit_controls_payload()
        depth_changed = current["depth"] != initial.get("depth")
        label_changed = current["label"] != initial.get("label")
        current_type_id = current.get("type_id")
        current_type_text = str(current.get("type_text") or "").strip()
        initial_type_id = initial.get("type_id")
        type_changed = (
            bool(current_type_id or current_type_text)
            and (
                current_type_id != initial_type_id
                or current_type_text != str(initial.get("type_text") or "")
            )
        )

        type_def = self._current_hierarchy_type_def() if type_changed else None
        changed = 0
        reveal_keys = []
        for mark in marks:
            old_key = self._hierarchy_mark_key(mark)
            mark_changed = False
            if type_def is not None:
                mark.type_id = type_def.type_id
                mark.description = type_def.description
                mark_changed = True
            if depth_changed or (type_def is not None and type_def.type_id == HierarchyType.IGNORE):
                active_type_id = type_def.type_id if type_def is not None else mark.type_id
                mark.depth = 0 if active_type_id == HierarchyType.IGNORE else int(current["depth"])
                mark_changed = True
            if label_changed:
                mark.text = str(current["label"]).strip()
                mark_changed = True
            if mark_changed:
                new_key = self._hierarchy_mark_key(mark)
                self._replace_active_edit_key(old_key, new_key)
                reveal_keys.append(new_key)
                changed += 1

        self._stop_range_edit()
        if changed:
            self._apply_ignore_precedence()
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return True

    def _save_hierarchy_edit(self) -> bool:
        if self._is_bulk_hierarchy_editing():
            return self._save_bulk_hierarchy_edit()

        mark = self._range_edit_mark()
        if mark is None or self._range_edit_start_line is None or self._range_edit_end_line is None:
            self._stop_range_edit()
            return False

        old_key = self._hierarchy_mark_key(mark)
        old_start = mark.start_line
        old_end = mark.end_line
        old_depth = mark.depth
        old_type_id = mark.type_id
        type_def = self._current_hierarchy_type_def()
        role_children = self._direct_role_children_for_conversion(
            old_key,
            old_type_id,
            type_def.type_id,
        )
        mark.start_line = min(self._range_edit_start_line, self._range_edit_end_line)
        mark.end_line = max(self._range_edit_start_line, self._range_edit_end_line)
        mark.start_col, mark.end_col = self._range_edit_saved_columns()
        mark.depth = 0 if type_def.type_id == HierarchyType.IGNORE else self.hierarchy_depth_spin.value()
        mark.type_id = type_def.type_id
        mark.text = self.hierarchy_label_edit.text().strip()
        mark.description = type_def.description
        child_target_type = {
            (HierarchyType.SPEAKER, HierarchyType.ITEM): HierarchyType.ITEM_DESCRIPTION,
            (HierarchyType.ITEM, HierarchyType.SPEAKER): HierarchyType.TEXT,
        }.get((old_type_id, type_def.type_id))
        if child_target_type is not None:
            child_def = self.hierarchy_type_definitions[child_target_type]
            for child in role_children:
                child_old_key = self._hierarchy_mark_key(child)
                child.type_id = child_target_type
                child.description = child_def.description
                child.origin = "manual"
                child.approved = True
                self._replace_active_edit_key(
                    child_old_key,
                    self._hierarchy_mark_key(child),
                )
        self._constrain_descendants_to_edited_range(
            mark,
            old_start=old_start,
            old_end=old_end,
            old_depth=old_depth,
        )
        new_key = self._hierarchy_mark_key(mark)
        self._replace_active_edit_key(old_key, new_key)
        if mark.type_id == HierarchyType.IGNORE:
            self._apply_ignore_precedence()
            reveal_keys = self._ignore_mark_keys_for_range(mark.start_line, mark.end_line)
        else:
            reveal_keys = [new_key]

        self._range_edit_mark_key = None
        self._range_edit_start_line = None
        self._range_edit_end_line = None
        self._range_edit_start_col = None
        self._range_edit_end_col = None
        self._range_edit_drag_handle = None
        self._update_range_edit_label()
        self._update_hierarchy_edit_controls()
        self._queue_outline_reveal(*reveal_keys)
        self._refresh()
        self._record_history()
        return True

    def _direct_role_children_for_conversion(
        self,
        parent_key: str,
        old_type_id: str,
        new_type_id: str,
    ) -> list[HierarchyMark]:
        child_type = {
            (HierarchyType.SPEAKER, HierarchyType.ITEM): HierarchyType.TEXT,
            (HierarchyType.ITEM, HierarchyType.SPEAKER): HierarchyType.ITEM_DESCRIPTION,
        }.get((old_type_id, new_type_id))
        if child_type is None:
            return []
        paths = self._hierarchy_paths_by_key()
        children = []
        for child in self.hierarchy_marks:
            if child.type_id != child_type:
                continue
            path = paths.get(self._hierarchy_mark_key(child), ())
            if len(path) >= 2 and self._hierarchy_mark_key(path[-2]) == parent_key:
                children.append(child)
        return children

    def _range_edit_mouse_press(self, event) -> bool:
        if self._range_edit_mark_key is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        handle = self._range_edit_handle_at_pos(self._raw_event_pos(event))
        if handle is None:
            return False
        self._range_edit_drag_handle = handle
        cursor_shape = (
            Qt.CursorShape.SizeHorCursor
            if handle in ("left", "right")
            else Qt.CursorShape.SizeVerCursor
        )
        self.raw_edit.viewport().setCursor(cursor_shape)
        event.accept()
        return True

    def _range_edit_mouse_move(self, event) -> bool:
        if self._range_edit_mark_key is None:
            return False
        pos = self._raw_event_pos(event)
        if self._range_edit_drag_handle:
            line_no = self._raw_line_at_pos(pos)
            if line_no is not None:
                column = (
                    self._raw_column_at_pos(pos, line_no)
                    if self._range_edit_drag_handle in ("left", "right")
                    else None
                )
                self._update_range_edit_preview(
                    self._range_edit_drag_handle,
                    line_no,
                    column,
                )
            event.accept()
            return True
        handle = self._range_edit_handle_at_pos(pos)
        if handle:
            cursor_shape = (
                Qt.CursorShape.SizeHorCursor
                if handle in ("left", "right")
                else Qt.CursorShape.SizeVerCursor
            )
            self.raw_edit.viewport().setCursor(cursor_shape)
        else:
            self.raw_edit.viewport().unsetCursor()
        return False

    def _range_edit_mouse_release(self, event) -> bool:
        if not self._range_edit_drag_handle or event.button() != Qt.MouseButton.LeftButton:
            return False
        self._range_edit_drag_handle = None
        self.raw_edit.viewport().unsetCursor()
        self._update_range_edit_label()
        self._apply_raw_extra_selections()
        event.accept()
        return True
