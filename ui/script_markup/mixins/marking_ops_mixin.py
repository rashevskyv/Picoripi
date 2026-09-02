"""Hierarchy mark geometry, ignore precedence, and selection apply helpers."""
from __future__ import annotations

from bisect import bisect_left, bisect_right

from PyQt6.QtWidgets import (
    QMessageBox,
)
from core.script_markup import (
    HierarchyMark, HierarchyType, HierarchyTypeDefinition,
    resolve_structure_name_iterator,
)
from core.i18n import tr

from ui.script_markup.constants import (
    _TEXT_CONTAINER_TYPES,
)


class HierarchyMarkOpsMixin:
    """Hierarchy mark geometry, ignore precedence, and selection apply helpers."""

    def _ranges_overlap(self, a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
        return a_start <= b_end and b_start <= a_end

    def _covered_hierarchy_lines(self) -> set[int]:
        covered: set[int] = set()
        for mark in self.hierarchy_marks:
            if mark.type_id in (HierarchyType.STRUCTURE, HierarchyType.SPEAKER):
                covered.add(mark.start_line)
            else:
                covered.update(range(mark.start_line, mark.end_line + 1))
        return covered

    def _unmarked_ranges(self, raw_lines: list[str]) -> list[tuple[int, int]]:
        covered = self._covered_hierarchy_lines()
        ranges: list[tuple[int, int]] = []
        start: int | None = None
        end: int | None = None

        def flush():
            nonlocal start, end
            if start is not None and end is not None:
                ranges.append((start, end))
            start = None
            end = None

        for idx, raw in enumerate(raw_lines):
            if idx in covered or not raw.strip():
                flush()
                continue
            if start is None:
                start = idx
            end = idx
        flush()
        return ranges

    def _selected_hierarchy_marks(self) -> list[HierarchyMark]:
        span = self._selected_line_span()
        if not span:
            return []
        start, end = span
        return [
            mark for mark in self.hierarchy_marks
            if start <= mark.start_line and mark.end_line <= end
        ]

    def _next_hierarchy_order(self) -> int:
        order = self._hierarchy_mark_order
        self._hierarchy_mark_order += 1
        return order

    def _text_fragment_from_mark(
        self,
        mark: HierarchyMark,
        start: int,
        end: int,
        order: int,
        *,
        start_col: int | None = None,
        end_col: int | None = None,
        depth: int | None = None,
    ) -> HierarchyMark:
        return HierarchyMark(
            start_line=start,
            end_line=end,
            depth=mark.depth if depth is None else depth,
            type_id=HierarchyType.TEXT,
            text="",
            label=mark.label,
            description=mark.description,
            color=mark.color,
            order=order,
            start_col=start_col,
            end_col=end_col,
            origin=mark.origin,
            approved=mark.approved,
        )

    def _fragment_from_mark(self, mark: HierarchyMark, start: int, end: int, order: int) -> HierarchyMark:
        return HierarchyMark(
            start_line=start,
            end_line=end,
            depth=mark.depth,
            type_id=mark.type_id,
            text=mark.text,
            label=mark.label,
            description=mark.description,
            color=mark.color,
            order=order,
            start_col=mark.start_col,
            end_col=mark.end_col,
            origin=mark.origin,
            approved=mark.approved,
        )

    def _subtract_range_from_ignore_marks(self, start: int, end: int) -> bool:
        updated: list[HierarchyMark] = []
        changed = False
        removed_keys: set[str] = set()
        for mark in self.hierarchy_marks:
            if (
                mark.type_id != HierarchyType.IGNORE
                or not self._ranges_overlap(mark.start_line, mark.end_line, start, end)
            ):
                updated.append(mark)
                continue

            changed = True
            removed_keys.add(self._hierarchy_mark_key(mark))
            if mark.start_line < start:
                updated.append(self._fragment_from_mark(
                    mark,
                    mark.start_line,
                    start - 1,
                    mark.order,
                ))
            if end < mark.end_line:
                updated.append(self._fragment_from_mark(
                    mark,
                    end + 1,
                    mark.end_line,
                    self._next_hierarchy_order(),
                ))

        if not changed:
            return False
        self.hierarchy_marks = updated
        self._collapsed_hierarchy_keys.difference_update(removed_keys)
        for key in removed_keys:
            self._outline_expansion_overrides.pop(key, None)
        if (
            self._range_edit_mark_key in removed_keys
            or removed_keys.intersection(self._bulk_edit_mark_keys)
        ):
            self._stop_range_edit()
        return True

    def _mark_segments_after_ignore_ranges(
        self,
        mark: HierarchyMark,
        ignore_ranges: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        if mark.type_id == HierarchyType.IGNORE:
            return [(mark.start_line, mark.end_line)]

        for start, end in ignore_ranges:
            if start <= mark.start_line and mark.end_line <= end:
                return []

        if mark.type_id in (HierarchyType.STRUCTURE, HierarchyType.SPEAKER):
            return [(mark.start_line, mark.end_line)]

        segments = [(mark.start_line, mark.end_line)]
        for ignore_start, ignore_end in ignore_ranges:
            next_segments: list[tuple[int, int]] = []
            for start, end in segments:
                if not self._ranges_overlap(start, end, ignore_start, ignore_end):
                    next_segments.append((start, end))
                    continue
                if start < ignore_start:
                    next_segments.append((start, ignore_start - 1))
                if ignore_end < end:
                    next_segments.append((ignore_end + 1, end))
            segments = next_segments
            if not segments:
                break
        return segments

    def _apply_ignore_precedence(self, raw_lines: list[str] | None = None) -> bool:
        ignore_ranges = sorted(
            (mark.start_line, mark.end_line)
            for mark in self.hierarchy_marks
            if mark.type_id == HierarchyType.IGNORE
        )
        if not ignore_ranges:
            return False

        updated: list[HierarchyMark] = []
        changed = False
        removed_keys: set[str] = set()
        for mark in self.hierarchy_marks:
            old_key = self._hierarchy_mark_key(mark)
            if mark.type_id == HierarchyType.IGNORE:
                if mark.depth != 0:
                    mark.depth = 0
                    changed = True
                updated.append(mark)
                continue

            segments = self._mark_segments_after_ignore_ranges(mark, ignore_ranges)
            if not segments:
                removed_keys.add(old_key)
                changed = True
                continue
            if segments == [(mark.start_line, mark.end_line)]:
                updated.append(mark)
                continue

            changed = True
            removed_keys.add(old_key)
            for idx, (start, end) in enumerate(segments):
                updated.append(
                    self._fragment_from_mark(
                        mark,
                        start,
                        end,
                        mark.order if idx == 0 else self._next_hierarchy_order(),
                    )
                )

        if changed:
            self.hierarchy_marks = updated
            self._collapsed_hierarchy_keys.difference_update(removed_keys)
            for key in removed_keys:
                self._outline_expansion_overrides.pop(key, None)
            if self._range_edit_mark_key in removed_keys or removed_keys.intersection(self._bulk_edit_mark_keys):
                self._stop_range_edit()
        return self._merge_adjacent_ignore_marks(raw_lines) or changed

    def _split_text_marks_around_mark(self, new_mark: HierarchyMark) -> bool:
        if new_mark.type_id in _TEXT_CONTAINER_TYPES:
            return False

        changed = False
        updated: list[HierarchyMark] = []
        for existing in self.hierarchy_marks:
            if (
                existing.type_id == HierarchyType.TEXT
                and existing.start_line == existing.end_line == new_mark.start_line == new_mark.end_line
                and new_mark.start_col is not None
            ):
                block = self.raw_edit.document().findBlockByNumber(existing.start_line)
                line_length = len(block.text()) if block.isValid() else 0
                existing_start = existing.start_col or 0
                existing_end = line_length if existing.end_col is None else existing.end_col
                new_start = max(existing_start, new_mark.start_col)
                new_end = min(existing_end, new_mark.end_col or line_length)
                if new_start < new_end:
                    if existing_start < new_start:
                        updated.append(self._text_fragment_from_mark(
                            existing,
                            existing.start_line,
                            existing.end_line,
                            existing.order,
                            start_col=existing_start,
                            end_col=new_start,
                        ))
                    if new_end < existing_end:
                        updated.append(self._text_fragment_from_mark(
                            existing,
                            existing.start_line,
                            existing.end_line,
                            self._next_hierarchy_order(),
                            start_col=new_end,
                            end_col=existing_end,
                            depth=(new_mark.depth + 1 if new_mark.type_id == HierarchyType.CONTEXT else existing.depth),
                        ))
                    changed = True
                    continue
            if (
                existing.type_id == HierarchyType.TEXT
                and existing.start_line <= new_mark.start_line
                and new_mark.end_line <= existing.end_line
                and (
                    new_mark.depth >= existing.depth
                    or (
                        new_mark.type_id == HierarchyType.CONTEXT
                        and new_mark.depth + 1 >= existing.depth
                    )
                )
            ):
                if new_mark.type_id != HierarchyType.CONTEXT:
                    new_mark.depth = existing.depth
                if existing.start_line < new_mark.start_line:
                    updated.append(
                        self._text_fragment_from_mark(
                            existing,
                            existing.start_line,
                            new_mark.start_line - 1,
                            existing.order,
                        )
                    )
                if new_mark.end_line < existing.end_line:
                    updated.append(
                        self._text_fragment_from_mark(
                            existing,
                            new_mark.end_line + 1,
                            existing.end_line,
                            self._next_hierarchy_order(),
                            depth=(
                                new_mark.depth + 1
                                if new_mark.type_id == HierarchyType.CONTEXT
                                else existing.depth
                            ),
                        )
                    )
                changed = True
            else:
                updated.append(existing)

        if changed:
            self.hierarchy_marks = updated
        return changed

    def _text_and_content_node_overlap(
        self,
        text_mark: HierarchyMark,
        content_node: HierarchyMark,
        raw_lines: list[str],
    ) -> bool:
        if not self._ranges_overlap(
            text_mark.start_line,
            text_mark.end_line,
            content_node.start_line,
            content_node.end_line,
        ):
            return False
        if not (
            text_mark.start_line == text_mark.end_line
            == content_node.start_line == content_node.end_line
        ):
            return True
        line_no = text_mark.start_line
        line_length = len(raw_lines[line_no]) if 0 <= line_no < len(raw_lines) else 0
        text_start = text_mark.start_col or 0
        text_end = line_length if text_mark.end_col is None else text_mark.end_col
        node_start = content_node.start_col or 0
        node_end = line_length if content_node.end_col is None else content_node.end_col
        return max(text_start, node_start) < min(text_end, node_end)

    def _normalize_text_marks_around_content_nodes(self, raw_lines: list[str]) -> int:
        content_nodes = sorted(
            (
                mark
                for mark in self.hierarchy_marks
                if mark.type_id not in _TEXT_CONTAINER_TYPES
            ),
            key=lambda mark: (mark.start_line, mark.end_line, mark.order),
        )
        if not content_nodes:
            return 0
        content_starts = [mark.start_line for mark in content_nodes]
        updated: list[HierarchyMark] = []
        removed_keys: set[str] = set()
        changed = 0

        for text_mark in self.hierarchy_marks:
            if text_mark.type_id != HierarchyType.TEXT:
                updated.append(text_mark)
                continue
            lo = bisect_left(content_starts, text_mark.start_line)
            if lo > 0 and content_nodes[lo - 1].end_line >= text_mark.start_line:
                lo -= 1
            hi = bisect_right(content_starts, text_mark.end_line)
            overlapping = [
                node
                for node in content_nodes[lo:hi]
                if node.end_line >= text_mark.start_line
                and self._text_and_content_node_overlap(text_mark, node, raw_lines)
            ]
            if not overlapping:
                updated.append(text_mark)
                continue

            changed += 1
            removed_keys.add(self._hierarchy_mark_key(text_mark))
            if text_mark.start_line == text_mark.end_line:
                self._append_text_fragments_around_inline_content_nodes(
                    updated,
                    text_mark,
                    overlapping,
                    raw_lines,
                )
                continue

            cursor = text_mark.start_line
            fragment_index = 0
            active_depth = text_mark.depth
            for node in overlapping:
                start = max(text_mark.start_line, node.start_line)
                end = min(text_mark.end_line, node.end_line)
                if end < cursor:
                    continue
                if cursor < start:
                    updated.append(self._text_fragment_from_mark(
                        text_mark,
                        cursor,
                        start - 1,
                        text_mark.order if fragment_index == 0 else self._next_hierarchy_order(),
                        depth=active_depth,
                    ))
                    fragment_index += 1
                if node.type_id == HierarchyType.CONTEXT:
                    node.depth = min(node.depth, active_depth)
                    active_depth = node.depth + 1
                else:
                    node.depth = active_depth
                cursor = max(cursor, end + 1)
            if cursor <= text_mark.end_line:
                updated.append(self._text_fragment_from_mark(
                    text_mark,
                    cursor,
                    text_mark.end_line,
                    text_mark.order if fragment_index == 0 else self._next_hierarchy_order(),
                    depth=active_depth,
                ))

        if not changed:
            return 0
        self.hierarchy_marks = updated
        self._collapsed_hierarchy_keys.difference_update(removed_keys)
        for key in removed_keys:
            self._outline_expansion_overrides.pop(key, None)
        if (
            self._range_edit_mark_key in removed_keys
            or removed_keys.intersection(self._bulk_edit_mark_keys)
        ):
            self._stop_range_edit()
        return changed

    def _append_text_fragments_around_inline_content_nodes(
        self,
        target: list[HierarchyMark],
        text_mark: HierarchyMark,
        content_nodes: list[HierarchyMark],
        raw_lines: list[str],
    ) -> None:
        line_no = text_mark.start_line
        line_length = len(raw_lines[line_no]) if 0 <= line_no < len(raw_lines) else 0
        text_start = text_mark.start_col or 0
        text_end = line_length if text_mark.end_col is None else text_mark.end_col
        cursor = text_start
        fragment_index = 0
        active_depth = text_mark.depth
        for node in sorted(
            content_nodes,
            key=lambda mark: (mark.start_col or 0, mark.end_col or line_length, mark.order),
        ):
            node_start = max(text_start, node.start_col or 0)
            node_end = min(
                text_end,
                line_length if node.end_col is None else node.end_col,
            )
            if node_end <= cursor:
                continue
            if cursor < node_start:
                target.append(self._text_fragment_from_mark(
                    text_mark,
                    line_no,
                    line_no,
                    text_mark.order if fragment_index == 0 else self._next_hierarchy_order(),
                    start_col=cursor,
                    end_col=node_start,
                    depth=active_depth,
                ))
                fragment_index += 1
            if node.type_id == HierarchyType.CONTEXT:
                node.depth = min(node.depth, active_depth)
                active_depth = node.depth + 1
            else:
                node.depth = active_depth
            cursor = max(cursor, node_end)
        if cursor < text_end:
            target.append(self._text_fragment_from_mark(
                text_mark,
                line_no,
                line_no,
                text_mark.order if fragment_index == 0 else self._next_hierarchy_order(),
                start_col=cursor,
                end_col=text_end,
                depth=active_depth,
            ))

    def _paragraph_ranges(
        self,
        raw_lines: list[str],
        start: int,
        end: int,
    ) -> list[tuple[int, int]]:
        ranges = []
        paragraph_start = None
        for line_no in range(start, end + 1):
            if raw_lines[line_no].strip():
                if paragraph_start is None:
                    paragraph_start = line_no
            elif paragraph_start is not None:
                ranges.append((paragraph_start, line_no - 1))
                paragraph_start = None
        if paragraph_start is not None:
            ranges.append((paragraph_start, end))
        return ranges

    def _paragraph_text_depth(
        self,
        start: int,
        end: int,
        requested_text_depth: int,
    ) -> int:
        containing_structures = [
            mark.depth
            for mark in self.hierarchy_marks
            if mark.type_id == HierarchyType.STRUCTURE
            and mark.start_line <= start
            and end <= mark.end_line
        ]
        minimum = max(containing_structures, default=-1) + 1
        return max(minimum, requested_text_depth, 0)

    def _speaker_anchor_for_text(
        self,
        text_mark: HierarchyMark,
    ) -> int:
        # A synthetic speaker belongs at the exact source position of its Text.
        # Using the preceding blank line can place it before a Structure that
        # begins on the Text line, making it a child of the previous sibling.
        # At the same line, depth sorting keeps Structure -> Speaker -> Text.
        return text_mark.start_line

    def _mark_text_paragraph_selection(
        self,
        start: int,
        end: int,
        requested_text_depth: int,
        type_def: HierarchyTypeDefinition,
    ) -> int:
        raw_lines = self.raw_edit.toPlainText().splitlines()
        paragraph_ranges = self._paragraph_ranges(raw_lines, start, end)
        if not paragraph_ranges:
            return 0

        removed_keys = set()
        updated = []
        for mark in self.hierarchy_marks:
            old_key = self._hierarchy_mark_key(mark)
            if (
                mark.type_id != HierarchyType.TEXT
                or not self._ranges_overlap(mark.start_line, mark.end_line, start, end)
            ):
                updated.append(mark)
                continue
            removed_keys.add(old_key)
            if mark.start_line < start:
                updated.append(self._text_fragment_from_mark(
                    mark,
                    mark.start_line,
                    start - 1,
                    mark.order,
                ))
            if end < mark.end_line:
                updated.append(self._text_fragment_from_mark(
                    mark,
                    end + 1,
                    mark.end_line,
                    self._next_hierarchy_order(),
                ))
        self.hierarchy_marks = updated

        reveal_keys = []
        for paragraph_start, paragraph_end in paragraph_ranges:
            text_depth = self._paragraph_text_depth(
                paragraph_start,
                paragraph_end,
                requested_text_depth,
            )
            text_mark = HierarchyMark(
                paragraph_start,
                paragraph_end,
                text_depth,
                HierarchyType.TEXT,
                description=type_def.description,
                order=self._next_hierarchy_order(),
            )
            self.hierarchy_marks.append(text_mark)
            reveal_keys.append(self._hierarchy_mark_key(text_mark))

        self._collapsed_hierarchy_keys.difference_update(removed_keys)
        for key in removed_keys:
            self._outline_expansion_overrides.pop(key, None)
        if (
            self._range_edit_mark_key in removed_keys
            or removed_keys.intersection(self._bulk_edit_mark_keys)
        ):
            self._stop_range_edit()
        self._apply_ignore_precedence()
        self._queue_outline_reveal(*reveal_keys)
        self._refresh()
        self._record_history()
        return len(paragraph_ranges)

    def _mark_selection_as_hierarchy(self):
        if self._is_hierarchy_editing():
            self._save_hierarchy_edit()
            return

        span = self._selected_line_span()
        if not span:
            return
        start, end = span
        start_col = None
        end_col = None
        cursor = self.raw_edit.textCursor()
        if cursor.hasSelection() and start == end:
            block = self.raw_edit.document().findBlockByNumber(start)
            if block.isValid():
                selection_start = min(cursor.selectionStart(), cursor.selectionEnd())
                selection_end = max(cursor.selectionStart(), cursor.selectionEnd())
                start_col = max(0, selection_start - block.position())
                end_col = max(start_col, selection_end - block.position())
                if start_col == 0 and end_col >= len(block.text()):
                    start_col = None
                    end_col = None
        type_def = self._current_hierarchy_type_def()
        explicit_text = self.hierarchy_label_edit.text().strip()
        depth = 0 if type_def.type_id == HierarchyType.IGNORE else self.hierarchy_depth_spin.value()
        if (
            type_def.type_id == HierarchyType.TEXT
            and self.hierarchy_split_text_cb.isChecked()
        ):
            self._mark_text_paragraph_selection(start, end, depth, type_def)
            return
        if type_def.type_id == HierarchyType.STRUCTURE:
            explicit_text = resolve_structure_name_iterator(
                explicit_text,
                self.hierarchy_marks,
                start_line=start,
                end_line=end,
                depth=depth,
            )
        mark = HierarchyMark(
            start_line=start,
            end_line=end,
            depth=depth,
            type_id=type_def.type_id,
            text=explicit_text,
            description=type_def.description,
            order=self._next_hierarchy_order(),
            start_col=start_col,
            end_col=end_col,
        )
        if mark.type_id != HierarchyType.IGNORE:
            self._subtract_range_from_ignore_marks(start, end)
        self._split_text_marks_around_mark(mark)
        self.hierarchy_marks = [
            existing for existing in self.hierarchy_marks
            if not (
                existing.start_line == start
                and existing.end_line == end
                and existing.depth == depth
                and existing.start_col == start_col
                and existing.end_col == end_col
            )
        ]
        self.hierarchy_marks.append(mark)
        if mark.type_id == HierarchyType.IGNORE:
            self._apply_ignore_precedence()
            self._queue_outline_reveal(*self._ignore_mark_keys_for_range(start, end))
        else:
            self._queue_outline_reveal(self._hierarchy_mark_key(mark))
        self._refresh()
        self._record_history()

    def _clear_selected_hierarchy_marks(self):
        if self._is_hierarchy_editing():
            self._stop_range_edit()
            return

        span = self._selected_line_span()
        if not span:
            return
        start, end = span
        kept = [
            mark for mark in self.hierarchy_marks
            if not (start <= mark.start_line and mark.end_line <= end)
        ]
        if len(kept) != len(self.hierarchy_marks):
            self.hierarchy_marks = kept
            self._refresh()
            self._record_history()

    def _reset_current_markup(self):
        if self.mode != "hierarchy":
            return

        if not any(mark.approved for mark in self.hierarchy_marks):
            QMessageBox.information(
                self,
                tr('Reset marks'),
                tr('There are no hierarchy marks to reset.'),
            )
            return

        answer = QMessageBox.question(
            self,
            tr('Reset marks?'),
            tr('Clear all hierarchy marks from the current script?\n\nThe raw script and hierarchy templates will stay unchanged.'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.hierarchy_marks = []
        self._hierarchy_mark_order = 0
        self._outline_reveal_keys.clear()
        self._outline_expansion_overrides.clear()
        self._collapsed_hierarchy_keys.clear()
        self._stop_range_edit()
        self._reset_raw_hierarchy_view()
        self._refresh()
        self._record_history()
