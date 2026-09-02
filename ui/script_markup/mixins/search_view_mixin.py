"""Search, extra selections, raw folds, and gutter/overlay paint helpers."""
from __future__ import annotations

import re

from PyQt6.QtWidgets import (
    QTextEdit,
)
from PyQt6.QtGui import (
    QTextCharFormat, QColor, QTextCursor,
    QTextFormat, QPainter, QPen,
)
from PyQt6.QtCore import Qt, QPoint, QRect
from core.script_markup import (
    LineKind,
    HierarchyMark, HierarchyType, line_styles_for_marks,
)
from core.i18n import tr

from ui.script_markup.constants import (
    _MAX_SEARCH_EXTRA_HIGHLIGHTS,
    _RAW_HIERARCHY_GUTTER_WIDTH,
    _RAW_HIERARCHY_MAX_VISUAL_DEPTH,
)


class SearchViewMixin:
    """Search, extra selections, raw folds, and gutter/overlay paint helpers."""

    # ------------------------------------------------------------ raw search
    def _on_raw_contents_change(self, _position: int, chars_removed: int, chars_added: int):
        if chars_removed or chars_added:
            self._raw_text_revision += 1

    def _on_raw_text_changed(self):
        self._debounce.start()
        self._invalidate_search_matches()
        self._queue_text_history_record()

    def _activate_mark_shortcut(self):
        if self.mode == "hierarchy":
            self._mark_selection_as_hierarchy()
        else:
            self._mark_selection_as(LineKind.ACTION)

    def _raw_editor_has_selection(self) -> bool:
        cursor = self.raw_edit.textCursor()
        return cursor.hasSelection() and cursor.selectionStart() != cursor.selectionEnd()

    def _activate_hierarchy_type_shortcut(self, type_id: str):
        if self.mode != "hierarchy":
            return
        self._select_hierarchy_type_id(type_id)
        if self._raw_editor_has_selection():
            self._mark_selection_as_hierarchy()

    def _activate_ignore_shortcut(self):
        if self.mode == "hierarchy":
            self._activate_hierarchy_type_shortcut(HierarchyType.IGNORE)
        else:
            self._mark_selection_as(LineKind.IGNORE)

    def _focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _search_flags(self) -> tuple[bool, bool, bool]:
        return (
            self.search_case_cb.isChecked(),
            self.search_word_cb.isChecked(),
            self.search_regex_cb.isChecked(),
        )

    def _current_search_signature(self) -> tuple[str, bool, bool, bool]:
        match_case, whole_word, regex = self._search_flags()
        return (self.search_edit.text(), match_case, whole_word, regex)

    def _reset_search_state(self, *, clear_highlight: bool = True):
        self._search_signature = None
        self._search_matches = []
        self._search_index = None
        self._search_error = ""
        if clear_highlight:
            self._apply_raw_extra_selections()

    def _raw_search_fingerprint(self, text: str | None = None) -> tuple[int, int]:
        text = self.raw_edit.toPlainText() if text is None else text
        return (len(text), hash(text))

    def _invalidate_search_matches(self):
        revision = self._raw_text_revision
        if self._search_document_revision == revision:
            return
        self._search_document_revision = revision
        self._search_text_fingerprint = None
        self._reset_search_state(clear_highlight=True)
        if self.search_edit.text().strip():
            self.search_status_label.setText("")

    def _on_search_text_changed(self, _text: str):
        self._reset_search_state(clear_highlight=True)
        self._find_search_match(forward=True, advance=False)

    def _on_search_options_changed(self, _checked: bool = False):
        self._reset_search_state(clear_highlight=True)
        self._find_search_match(forward=True, advance=False)

    def _find_next_search_match(self, _checked: bool = False):
        self._find_search_match(forward=True, advance=True)

    def _find_previous_search_match(self, _checked: bool = False):
        self._find_search_match(forward=False, advance=True)

    def _compile_search_pattern(self, query: str):
        match_case, whole_word, regex = self._search_flags()
        pattern = query if regex else re.escape(query)
        if whole_word:
            pattern = rf"(?<!\w)(?:{pattern})(?!\w)"
        flags = 0 if match_case else re.IGNORECASE
        try:
            return re.compile(pattern, flags)
        except re.error as exc:
            self._search_error = str(exc)
            return None

    def _rebuild_search_matches(self, signature: tuple[str, bool, bool, bool]):
        if signature == self._search_signature:
            return

        self._search_signature = signature
        self._search_matches = []
        self._search_index = None
        self._search_error = ""

        query = signature[0]
        if not query:
            return

        pattern = self._compile_search_pattern(query)
        if pattern is None:
            return

        text = self.raw_edit.toPlainText()
        self._search_matches = [
            (match.start(), match.end())
            for match in pattern.finditer(text)
            if match.end() > match.start()
        ]
        self._search_document_revision = self._raw_text_revision
        self._search_text_fingerprint = self._raw_search_fingerprint(text)

    def _search_index_after(self, position: int) -> int:
        for idx, (start, _end) in enumerate(self._search_matches):
            if start >= position:
                return idx
        return 0

    def _search_index_before(self, position: int) -> int:
        for idx in range(len(self._search_matches) - 1, -1, -1):
            start, _end = self._search_matches[idx]
            if start < position:
                return idx
        return len(self._search_matches) - 1

    def _find_search_match(self, forward: bool, advance: bool):
        query = self.search_edit.text()
        if not query:
            self.search_status_label.setText("")
            self._reset_search_state(clear_highlight=False)
            self._apply_raw_extra_selections()
            return

        self._rebuild_search_matches(self._current_search_signature())
        if self._search_error:
            self.search_status_label.setText(tr('Bad regex'))
            self._apply_raw_extra_selections()
            return
        if not self._search_matches:
            self.search_status_label.setText("0")
            self._apply_raw_extra_selections()
            return

        if self._search_index is None:
            cursor = self.raw_edit.textCursor()
            position = cursor.selectionEnd() if forward else cursor.selectionStart()
            idx = self._search_index_after(position) if forward else self._search_index_before(position)
        elif advance:
            step = 1 if forward else -1
            idx = (self._search_index + step) % len(self._search_matches)
        else:
            idx = self._search_index

        self._show_search_match(idx)

    def _search_extra_selection(self, start: int, end: int, active: bool) -> QTextEdit.ExtraSelection:
        cursor = QTextCursor(self.raw_edit.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        selection = QTextEdit.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#ffc94a" if active else "#fff2a8"))
        fmt.setForeground(QColor("#111111"))
        selection.format = fmt
        selection.cursor = cursor
        return selection

    def _search_extra_selections(self) -> list[QTextEdit.ExtraSelection]:
        if self._search_index is None or not self._search_matches:
            return []
        idx = min(self._search_index, len(self._search_matches) - 1)
        start, end = self._search_matches[idx]
        selections = [self._search_extra_selection(start, end, active=True)]
        for match_idx, (match_start, match_end) in enumerate(self._search_matches):
            if match_idx == idx:
                continue
            if len(selections) >= _MAX_SEARCH_EXTRA_HIGHLIGHTS:
                break
            selections.append(self._search_extra_selection(match_start, match_end, active=False))
        return selections

    def _range_line_extra_selection(self, line_no: int, color: str) -> QTextEdit.ExtraSelection | None:
        block = self.raw_edit.document().findBlockByNumber(line_no)
        if not block.isValid():
            return None
        selection = QTextEdit.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(color))
        fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.format = fmt
        selection.cursor = QTextCursor(block)
        return selection

    def _range_edit_extra_selections(self) -> list[QTextEdit.ExtraSelection]:
        if self._is_bulk_hierarchy_editing():
            selections = []
            for mark in self._bulk_edit_marks():
                for line_no in range(mark.start_line, mark.end_line + 1):
                    selection = self._range_line_extra_selection(line_no, "#dbeafe")
                    if selection is not None:
                        selections.append(selection)
            return selections
        if self._range_edit_start_line is None or self._range_edit_end_line is None:
            return []
        start = min(self._range_edit_start_line, self._range_edit_end_line)
        end = max(self._range_edit_start_line, self._range_edit_end_line)
        if start == end:
            columns = self._range_edit_columns()
            if columns is None:
                return []
            start_col, end_col = columns
            block = self.raw_edit.document().findBlockByNumber(start)
            cursor = QTextCursor(self.raw_edit.document())
            cursor.setPosition(block.position() + start_col)
            cursor.setPosition(block.position() + end_col, QTextCursor.MoveMode.KeepAnchor)
            only = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#c7d2fe"))
            only.format = fmt
            only.cursor = cursor
            return [only] if only is not None else []

        selections = []
        start_sel = self._range_line_extra_selection(start, "#93c5fd")
        end_sel = self._range_line_extra_selection(end, "#fdba74")
        if start_sel is not None:
            selections.append(start_sel)
        if end_sel is not None:
            selections.append(end_sel)
        return selections

    def _navigation_extra_selections(self) -> list[QTextEdit.ExtraSelection]:
        if self._raw_navigation_line is None:
            return []
        selection = self._range_line_extra_selection(self._raw_navigation_line, "#fff3a3")
        if selection is None:
            return []
        fmt = selection.format
        fmt.setForeground(QColor("#111111"))
        selection.format = fmt
        return [selection]

    def _partial_mark_extra_selections(self) -> list[QTextEdit.ExtraSelection]:
        selections = []
        doc = self.raw_edit.document()
        for mark in self.hierarchy_marks:
            if mark.start_line != mark.end_line or mark.start_col is None:
                continue
            block = doc.findBlockByNumber(mark.start_line)
            if not block.isValid():
                continue
            start_col = max(0, min(mark.start_col, len(block.text())))
            end_col = len(block.text()) if mark.end_col is None else max(
                start_col, min(mark.end_col, len(block.text()))
            )
            cursor = QTextCursor(doc)
            cursor.setPosition(block.position() + start_col)
            cursor.setPosition(block.position() + end_col, QTextCursor.MoveMode.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            type_def = self.hierarchy_type_definitions.get(mark.type_id)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(mark.color or (type_def.color if type_def else "#e0e7ff")))
            selection.format = fmt
            selection.cursor = cursor
            selections.append(selection)
        return selections

    def _raw_fold_extra_selections(self) -> list[QTextEdit.ExtraSelection]:
        if not self._collapsed_hierarchy_keys:
            return []
        mark_by_key = self._hierarchy_mark_by_key_map()
        selections = []
        for key in self._collapsed_hierarchy_keys:
            mark = mark_by_key.get(key)
            if mark is None:
                continue
            selection = self._range_line_extra_selection(mark.start_line, "#eef3f8")
            if selection is not None:
                fmt = selection.format
                fmt.setForeground(QColor("#1f2937"))
                fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)
                selection.format = fmt
                selections.append(selection)
        return selections

    def _apply_raw_extra_selections(self):
        self.raw_edit.setExtraSelections(
            self._raw_fold_extra_selections()
            + self._navigation_extra_selections()
            + self._partial_mark_extra_selections()
            + self._search_extra_selections()
            + self._range_edit_extra_selections()
        )
        self.raw_edit.viewport().update()
        self.raw_edit.hierarchy_gutter.update()

    def _set_raw_hierarchy_block_format(self, line_depths: dict[int, int], hidden_lines: set[int]):
        doc = self.raw_edit.document()
        old_blocked = self.raw_edit.blockSignals(True)
        old_undo = doc.isUndoRedoEnabled()
        cursor = self.raw_edit.textCursor()
        cursor_anchor = cursor.anchor()
        cursor_position = cursor.position()
        vertical_scroll = self.raw_edit.verticalScrollBar().value()
        horizontal_scroll = self.raw_edit.horizontalScrollBar().value()
        doc.setUndoRedoEnabled(False)
        try:
            edit_cursor = QTextCursor(doc)
            edit_cursor.beginEditBlock()
            for line_no in range(doc.blockCount()):
                block = doc.findBlockByNumber(line_no)
                if not block.isValid():
                    continue
                hidden = line_no in hidden_lines
                block.setVisible(not hidden)
                try:
                    block.setLineCount(0 if hidden else max(1, block.lineCount()))
                except AttributeError:
                    pass
                fmt = block.blockFormat()
                fmt.setLeftMargin(0)
                edit_cursor.setPosition(block.position())
                edit_cursor.mergeBlockFormat(fmt)
            edit_cursor.endEditBlock()
        finally:
            doc.setUndoRedoEnabled(old_undo)
            self.raw_edit.blockSignals(old_blocked)
        restored = self.raw_edit.textCursor()
        text_len = len(self.raw_edit.toPlainText())
        restored.setPosition(max(0, min(cursor_anchor, text_len)))
        restored.setPosition(max(0, min(cursor_position, text_len)), QTextCursor.MoveMode.KeepAnchor)
        self.raw_edit.setTextCursor(restored)
        self.raw_edit.verticalScrollBar().setValue(min(vertical_scroll, self.raw_edit.verticalScrollBar().maximum()))
        self.raw_edit.horizontalScrollBar().setValue(min(horizontal_scroll, self.raw_edit.horizontalScrollBar().maximum()))
        doc.markContentsDirty(0, doc.characterCount())
        self.raw_edit.viewport().update()
        self.raw_edit.hierarchy_gutter.update()

    def _reset_raw_hierarchy_view(self):
        if (
            not self._raw_line_depths
            and not self._raw_fold_headers
            and self._raw_hierarchy_view_signature is None
        ):
            return
        self._raw_line_depths = {}
        self._raw_fold_headers = {}
        self._raw_hierarchy_view_signature = None
        self._set_raw_hierarchy_block_format({}, set())

    def _hierarchy_mark_by_key_map(self) -> dict[str, HierarchyMark]:
        if self._hierarchy_mark_by_key_cache is None:
            self._hierarchy_mark_by_key_cache = {
                self._hierarchy_mark_key(mark): mark
                for mark in self.hierarchy_marks
            }
        return self._hierarchy_mark_by_key_cache

    def _invalidate_hierarchy_mark_caches(self):
        self._hierarchy_mark_by_key_cache = None
        self._hierarchy_paths_by_key_cache = None

    def _hierarchy_marks_signature(self) -> tuple:
        marks = tuple(
            (
                int(mark.start_line),
                int(mark.end_line),
                int(mark.depth),
                str(mark.type_id),
                str(mark.text),
                str(mark.label),
                str(mark.color),
                int(mark.order),
                mark.start_col,
                mark.end_col,
                str(mark.origin),
                bool(mark.approved),
            )
            for mark in self.hierarchy_marks
        )
        type_defs = tuple(
            sorted(
                (
                    str(type_id),
                    str(definition.label),
                    str(definition.color),
                )
                for type_id, definition in self.hierarchy_type_definitions.items()
            )
        )
        return marks, type_defs

    def _hierarchy_base_line_styles(self) -> dict[int, tuple[str, str]]:
        key = self._hierarchy_marks_signature()
        if self._hierarchy_line_styles_cache_key != key:
            styles = line_styles_for_marks(
                self.hierarchy_marks,
                self.hierarchy_type_definitions,
            )
            self._hierarchy_line_styles_cache_key = key
            self._hierarchy_line_styles_cache = styles
        return self._hierarchy_line_styles_cache or {}

    def _raw_hierarchy_view_data(self, raw_lines: list[str]) -> tuple[dict[int, int], dict[int, str], set[int]]:
        mark_by_key = self._hierarchy_mark_by_key_map()
        self._collapsed_hierarchy_keys = {
            key for key in self._collapsed_hierarchy_keys
            if key in mark_by_key
        }
        line_count = len(raw_lines)
        cache_key = (
            line_count,
            self._hierarchy_marks_signature(),
            tuple(sorted(self._collapsed_hierarchy_keys)),
        )
        if self._raw_hierarchy_view_data_cache_key == cache_key and self._raw_hierarchy_view_data_cache is not None:
            line_depths, fold_headers, hidden_lines = self._raw_hierarchy_view_data_cache
            return dict(line_depths), dict(fold_headers), set(hidden_lines)

        line_depths: dict[int, int] = {}
        fold_candidates: dict[int, tuple[int, int, str]] = {}
        hidden_lines: set[int] = set()

        for mark in self.hierarchy_marks:
            if mark.type_id in (HierarchyType.IGNORE, HierarchyType.UNMARKED):
                continue
            start = max(0, min(mark.start_line, max(0, line_count - 1)))
            end = max(start, min(mark.end_line, max(0, line_count - 1)))
            for line_no in range(start, end + 1):
                line_depths[line_no] = max(line_depths.get(line_no, 0), mark.depth)

            if end > start:
                key = self._hierarchy_mark_key(mark)
                current = fold_candidates.get(start)
                priority = (mark.depth, end - start)
                if current is None or priority > (current[0], current[1]):
                    fold_candidates[start] = (mark.depth, end - start, key)

        for key in self._collapsed_hierarchy_keys:
            mark = mark_by_key.get(key)
            if mark is None:
                continue
            start = max(0, min(mark.start_line, max(0, line_count - 1)))
            end = max(start, min(mark.end_line, max(0, line_count - 1)))
            hidden_lines.update(range(start + 1, end + 1))

        fold_headers = {
            line_no: key
            for line_no, (_depth, _span, key) in fold_candidates.items()
            if line_no not in hidden_lines
        }
        self._raw_hierarchy_view_data_cache_key = cache_key
        self._raw_hierarchy_view_data_cache = (
            dict(line_depths),
            dict(fold_headers),
            set(hidden_lines),
        )
        return line_depths, fold_headers, hidden_lines

    def _apply_raw_hierarchy_view(self, raw_lines: list[str]):
        if self.mode != "hierarchy":
            self._reset_raw_hierarchy_view()
            return
        line_depths, fold_headers, hidden_lines = self._raw_hierarchy_view_data(raw_lines)
        signature = (tuple(sorted(line_depths.items())), tuple(sorted(hidden_lines)))
        self._raw_line_depths = line_depths
        self._raw_fold_headers = fold_headers
        if signature != self._raw_hierarchy_view_signature:
            self._raw_hierarchy_view_signature = signature
            self._set_raw_hierarchy_block_format(line_depths, hidden_lines)

    def _raw_fold_key_at_pos(self, pos: QPoint, *, require_gutter: bool = True) -> str | None:
        if self.mode != "hierarchy":
            return None
        if require_gutter and pos.x() > _RAW_HIERARCHY_GUTTER_WIDTH:
            return None
        block = self.raw_edit.cursorForPosition(pos).block()
        if not block.isValid():
            return None
        return self._raw_fold_headers.get(block.blockNumber())

    def _toggle_raw_hierarchy_fold(self, key: str | None) -> bool:
        if not key:
            return False
        if key in self._collapsed_hierarchy_keys:
            self._collapsed_hierarchy_keys.remove(key)
        else:
            self._collapsed_hierarchy_keys.add(key)
        self._apply_raw_hierarchy_view(self.raw_edit.toPlainText().splitlines())
        self._apply_raw_extra_selections()
        return True

    def _expand_all_raw_hierarchy_folds(self):
        if not self._collapsed_hierarchy_keys:
            return
        self._collapsed_hierarchy_keys.clear()
        self._apply_raw_hierarchy_view(self.raw_edit.toPlainText().splitlines())
        self._apply_raw_extra_selections()

    def _raw_hierarchy_gutter_mouse_press(self, event) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        try:
            pos = event.position().toPoint()
        except AttributeError:
            pos = event.pos()
        key = self._raw_fold_key_at_pos(pos, require_gutter=True)
        if not key:
            return False
        self._toggle_raw_hierarchy_fold(key)
        event.accept()
        return True

    def _paint_raw_hierarchy_gutter(self, gutter, rect):
        if self.mode != "hierarchy":
            return
        painter = QPainter(gutter)
        painter.fillRect(rect, QColor("#f6f8fa"))
        painter.setPen(QPen(QColor("#d0d7de"), 1))
        painter.drawLine(_RAW_HIERARCHY_GUTTER_WIDTH - 1, rect.top(), _RAW_HIERARCHY_GUTTER_WIDTH - 1, rect.bottom())

        block = self.raw_edit.firstVisibleBlock()
        offset = self.raw_edit.contentOffset()
        mark_by_key = self._hierarchy_mark_by_key_map()
        while block.isValid():
            geom = self.raw_edit.blockBoundingGeometry(block).translated(offset)
            top = int(geom.top())
            bottom = int(geom.bottom())
            if top > rect.bottom():
                break
            if bottom >= rect.top() and block.isVisible():
                line_no = block.blockNumber()
                actual_depth = max(0, int(self._raw_line_depths.get(line_no, 0)))
                depth = min(_RAW_HIERARCHY_MAX_VISUAL_DEPTH, actual_depth)
                painter.setPen(QPen(QColor("#c7d2de"), 1))
                for level in range(depth + 1):
                    x = 6 + level * 5
                    painter.drawLine(x, top, x, bottom)

                if line_no == self._raw_navigation_line:
                    marker = QRect(1, top + max(1, (bottom - top - 14) // 2), 27, 14)
                    painter.setPen(QPen(QColor("#9a6700"), 1))
                    painter.setBrush(QColor("#ffd33d"))
                    painter.drawRoundedRect(marker, 3, 3)
                    painter.setPen(QPen(QColor("#111111"), 1))
                    painter.drawText(marker, Qt.AlignmentFlag.AlignCenter, "➜")

                key = self._raw_fold_headers.get(line_no)
                if key:
                    collapsed = key in self._collapsed_hierarchy_keys
                    hidden_count = 0
                    mark = mark_by_key.get(key)
                    if mark is not None:
                        hidden_count = max(0, mark.end_line - mark.start_line)
                    center_y = top + max(10, int(geom.height()) // 2)
                    button_rect = QRect(30, center_y - 7, 13, 13)
                    painter.setPen(QPen(QColor("#8c959f"), 1))
                    painter.setBrush(QColor("#ffffff" if not collapsed else "#dbeafe"))
                    painter.drawRoundedRect(button_rect, 2, 2)
                    painter.setPen(QPen(QColor("#1f2937"), 1))
                    painter.drawText(button_rect, Qt.AlignmentFlag.AlignCenter, "+" if collapsed else "-")
                    if mark is not None:
                        painter.setPen(QPen(QColor("#6b7280"), 1))
                        painter.drawText(46, center_y + 4, f"d{mark.depth}")
                        if collapsed:
                            painter.drawText(62, center_y + 4, str(hidden_count))
            block = block.next()

    def _range_handle_geometry(self, line_no: int, *, edge: str) -> tuple[int, int] | None:
        block = self.raw_edit.document().findBlockByNumber(line_no)
        if not block.isValid() or not block.isVisible():
            return None
        geom = self.raw_edit.blockBoundingGeometry(block).translated(self.raw_edit.contentOffset())
        y = int(geom.top()) if edge == "start" else int(geom.bottom()) - 1
        leading = len(block.text()) - len(block.text().lstrip())
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + leading)
        x = max(2, self.raw_edit.cursorRect(cursor).left())
        return x, y

    def _range_column_handle_geometry(
        self,
        line_no: int,
        column: int,
    ) -> tuple[int, int, int] | None:
        block = self.raw_edit.document().findBlockByNumber(line_no)
        if not block.isValid() or not block.isVisible():
            return None
        column = max(0, min(column, len(block.text())))
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + column)
        cursor_rect = self.raw_edit.cursorRect(cursor)
        return cursor_rect.left(), cursor_rect.top(), cursor_rect.bottom()

    def _paint_raw_edit_overlays(self, viewport, rect):
        if self._range_edit_start_line is None or self._range_edit_end_line is None:
            return
        painter = QPainter(viewport)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        specs = (
            (self._range_edit_start_line, "start", QColor("#0969da")),
            (self._range_edit_end_line, "end", QColor("#cf5c00")),
        )
        for line_no, edge, color in specs:
            geometry = self._range_handle_geometry(line_no, edge=edge)
            if geometry is None:
                continue
            x, y = geometry
            if y < rect.top() - 6 or y > rect.bottom() + 6:
                continue
            painter.setPen(QPen(color, 2))
            painter.drawLine(x, y, max(x, viewport.width() - 3), y)
            painter.setBrush(color)
            painter.drawEllipse(QPoint(x, y), 4, 4)
        if self._range_edit_start_line == self._range_edit_end_line:
            columns = self._range_edit_columns()
            if columns is not None:
                line_no = self._range_edit_start_line
                for column, color in (
                    (columns[0], QColor("#0969da")),
                    (columns[1], QColor("#cf5c00")),
                ):
                    geometry = self._range_column_handle_geometry(line_no, column)
                    if geometry is None:
                        continue
                    x, top, bottom = geometry
                    painter.setPen(QPen(color, 2))
                    painter.drawLine(x, top, x, bottom)
                    painter.setBrush(color)
                    painter.drawEllipse(QPoint(x, (top + bottom) // 2), 4, 4)

    def _restore_search_highlight(self):
        if self._search_index is None or not self._search_matches:
            return
        if self._search_index >= len(self._search_matches):
            self._search_index = len(self._search_matches) - 1
        self._show_search_match(self._search_index, scroll=False)

    def _show_search_match(self, idx: int, *, scroll: bool = True):
        self._search_index = idx
        start, end = self._search_matches[idx]

        self._apply_raw_extra_selections()

        if scroll:
            self._scroll_raw_to_position(start)
        self.search_status_label.setText(f"{idx + 1}/{len(self._search_matches)}")

    def _scroll_raw_to_position(self, position: int):
        block = self.raw_edit.document().findBlock(position)
        if not block.isValid():
            return

        line_height = max(1, self.raw_edit.fontMetrics().lineSpacing())
        visible_lines = max(1, self.raw_edit.viewport().height() // line_height)
        target_line = max(0, block.blockNumber() - visible_lines // 3)
        bar = self.raw_edit.verticalScrollBar()
        bar.setValue(min(target_line, bar.maximum()))
