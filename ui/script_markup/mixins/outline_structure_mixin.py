"""Outline structure join, depth, delete, and drop handling."""
from __future__ import annotations


from PyQt6.QtWidgets import (
    QMessageBox, QTreeWidgetItem, QAbstractItemView,
)
from core.script_markup import (
    HierarchyMark, HierarchyType, mark_text,
)
from core.i18n import tr

from ui.script_markup.constants import (
    _OUTLINE_MARK_KEY_ROLE,
)


class OutlineStructureMixin:
    """Outline structure join, depth, delete, and drop handling."""

    def _outline_root_items(self, items: list[QTreeWidgetItem]) -> list[QTreeWidgetItem]:
        roots = []
        selected_ids = {id(item) for item in items}
        for item in items:
            parent = item.parent()
            skip = False
            while parent is not None:
                if id(parent) in selected_ids:
                    skip = True
                    break
                parent = parent.parent()
            if not skip:
                roots.append(item)
        return roots

    def _outline_key_groups(
        self,
        items: list[QTreeWidgetItem],
        include_children: bool,
    ) -> list[list[str]]:
        roots = self._outline_root_items(items) if include_children else items
        return [
            self._outline_mark_keys(
                item,
                include_children=include_children or not item.isExpanded(),
            )
            for item in roots
        ]

    def _flatten_key_groups(self, groups: list[list[str]]) -> list[str]:
        keys = []
        seen = set()
        for group in groups:
            for key in group:
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        return keys

    def _outline_direct_mark_keys(self, items: list[QTreeWidgetItem]) -> list[str]:
        keys = []
        seen = set()
        for item in items:
            key = self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
            if key and str(key) not in seen:
                keys.append(str(key))
                seen.add(str(key))
        return keys

    def _structure_join_label_key(self, mark: HierarchyMark, raw_lines: list[str]) -> str:
        return self._clean_mark_text(mark_text(mark, raw_lines)).casefold()

    def _structure_explicit_join_label_key(self, mark: HierarchyMark, raw_lines: list[str]) -> str:
        explicit = self._clean_mark_text(mark.text or mark.label)
        if explicit:
            return explicit.casefold()
        return self._structure_join_label_key(mark, raw_lines)

    def _structure_start_line_is_label(self, mark: HierarchyMark, raw_lines: list[str]) -> bool:
        if not (0 <= mark.start_line < len(raw_lines)):
            return False
        label = self._clean_mark_text(mark.text or mark.label)
        source = self._clean_mark_text(raw_lines[mark.start_line])
        return bool(label and source and label.casefold() == source.casefold())

    def _joinable_structure_marks_for_keys(self, keys) -> list[HierarchyMark]:
        key_list = [str(key) for key in keys if key]
        if len(key_list) < 2:
            return []
        raw_lines = self.raw_edit.toPlainText().splitlines()
        selected: list[tuple[str, HierarchyMark]] = []
        seen = set()
        for key in key_list:
            if key in seen:
                continue
            mark = self._hierarchy_mark_for_key(key)
            if mark is None:
                continue
            selected.append((key, mark))
            seen.add(key)
        marks = [mark for _key, mark in selected]
        if len(marks) < 2 or any(mark.type_id != HierarchyType.STRUCTURE for mark in marks):
            return []
        depth = marks[0].depth
        if any(mark.depth != depth for mark in marks):
            return []
        labels = {
            self._structure_join_label_key(mark, raw_lines)
            for mark in marks
        }
        if len(labels) != 1 or not next(iter(labels)):
            return []

        selected_keys = {key for key, _mark in selected}
        first_start = min(mark.start_line for mark in marks)
        last_start = max(mark.start_line for mark in marks)
        for mark in self.hierarchy_marks:
            key = self._hierarchy_mark_key(mark)
            if key in selected_keys or mark.type_id == HierarchyType.IGNORE:
                continue
            if mark.depth <= depth and first_start < mark.start_line < last_start:
                return []
        return sorted(marks, key=lambda mark: (mark.start_line, mark.end_line, mark.order))

    def _join_structure_mark_keys(self, keys) -> int:
        marks = self._joinable_structure_marks_for_keys(keys)
        if len(marks) < 2:
            return 0

        primary = marks[0]
        raw_lines = self.raw_edit.toPlainText().splitlines()
        old_primary_key = self._hierarchy_mark_key(primary)
        removed = marks[1:]
        removed_ids = {id(mark) for mark in removed}
        removed_keys = {self._hierarchy_mark_key(mark) for mark in removed}
        ignored_duplicate_labels = [
            HierarchyMark(
                start_line=mark.start_line,
                end_line=mark.start_line,
                depth=0,
                type_id=HierarchyType.IGNORE,
                order=mark.order,
                origin=mark.origin,
                approved=mark.approved,
            )
            for mark in removed
            if self._structure_start_line_is_label(mark, raw_lines)
        ]

        primary.start_line = min(mark.start_line for mark in marks)
        primary.end_line = max(mark.end_line for mark in marks)
        primary.order = min(mark.order for mark in marks)
        for mark in marks[1:]:
            if not primary.text and mark.text:
                primary.text = mark.text
            if not primary.label and mark.label:
                primary.label = mark.label
            if not primary.description and mark.description:
                primary.description = mark.description
            if not primary.color and mark.color:
                primary.color = mark.color

        self.hierarchy_marks = [
            mark for mark in self.hierarchy_marks
            if id(mark) not in removed_ids
        ]
        self.hierarchy_marks.extend(ignored_duplicate_labels)
        new_primary_key = self._hierarchy_mark_key(primary)
        if (
            self._range_edit_mark_key in removed_keys
            or removed_keys.intersection(self._bulk_edit_mark_keys)
        ):
            self._stop_range_edit()
        else:
            self._replace_active_edit_key(old_primary_key, new_primary_key)
        self._collapsed_hierarchy_keys.difference_update(removed_keys)
        for key in removed_keys:
            self._outline_expansion_overrides.pop(key, None)
        self._queue_outline_reveal(new_primary_key)
        self._refresh()
        self._record_history()
        return len(marks)

    def _has_breaker_between(self, start: int, end: int) -> bool:
        if start > end:
            return False
        return any(
            mark.type_id == HierarchyType.BREAKER
            and self._ranges_overlap(mark.start_line, mark.end_line, start, end)
            for mark in self.hierarchy_marks
        )

    def _structure_join_group_end(
        self,
        first: HierarchyMark,
        group: list[HierarchyMark],
        raw_lines: list[str],
    ) -> int:
        group_ids = {id(mark) for mark in group}
        boundary = None
        for mark in self.hierarchy_marks:
            if (
                id(mark) not in group_ids
                and mark.type_id == HierarchyType.STRUCTURE
                and mark.depth <= first.depth
                and mark.start_line > first.start_line
            ):
                boundary = mark.start_line - 1 if boundary is None else min(boundary, mark.start_line - 1)
        return boundary if boundary is not None else max(0, len(raw_lines) - 1)

    def _auto_join_adjacent_duplicate_structures(self) -> int:
        raw_lines = self.raw_edit.toPlainText().splitlines()
        candidates = sorted(
            [
                mark for mark in self.hierarchy_marks
                if mark.type_id == HierarchyType.STRUCTURE
                and self._structure_explicit_join_label_key(mark, raw_lines)
            ],
            key=lambda mark: (mark.depth, mark.start_line, mark.order),
        )
        changed = 0
        by_depth: dict[int, list[HierarchyMark]] = {}
        for mark in candidates:
            by_depth.setdefault(mark.depth, []).append(mark)

        for depth, marks in by_depth.items():
            index = 0
            while index < len(marks):
                first = marks[index]
                label = self._structure_explicit_join_label_key(first, raw_lines)
                group = [first]
                next_index = index + 1
                while next_index < len(marks):
                    current = marks[next_index]
                    if self._structure_explicit_join_label_key(current, raw_lines) != label:
                        break
                    if self._has_breaker_between(group[-1].end_line + 1, current.start_line - 1):
                        break
                    crosses_parent = any(
                        mark.type_id == HierarchyType.STRUCTURE
                        and mark.depth < depth
                        and group[-1].start_line < mark.start_line <= current.start_line
                        for mark in self.hierarchy_marks
                    )
                    if crosses_parent:
                        break
                    group.append(current)
                    next_index += 1

                if len(group) < 2:
                    index += 1
                    continue

                primary = group[0]
                removed = group[1:]
                removed_ids = {id(mark) for mark in removed}
                primary.end_line = max(
                    primary.end_line,
                    self._structure_join_group_end(primary, group, raw_lines),
                )
                duplicate_ignores = [
                    HierarchyMark(
                        start_line=mark.start_line,
                        end_line=mark.start_line,
                        depth=0,
                        type_id=HierarchyType.IGNORE,
                        order=mark.order,
                        origin=mark.origin,
                        approved=mark.approved,
                    )
                    for mark in removed
                    if self._structure_start_line_is_label(mark, raw_lines)
                ]
                self.hierarchy_marks = [
                    mark for mark in self.hierarchy_marks
                    if id(mark) not in removed_ids
                ]
                self.hierarchy_marks.extend(duplicate_ignores)
                changed += len(removed)
                index = next_index

        return changed

    def _join_selected_structures(self) -> int:
        if self.mode != "hierarchy":
            self._switch_to_hierarchy_mode()
        keys = self._outline_direct_mark_keys(self.flags_list.selectedItems())
        joined = self._join_structure_mark_keys(keys)
        if not joined:
            QMessageBox.information(
                self,
                tr('Join structures'),
                tr('Select two or more Structure nodes with the same label and depth.'),
            )
        return joined

    def _delete_outline_mark_keys(self, keys) -> int:
        key_set = {str(key) for key in keys if key}
        if not key_set:
            return 0
        before = len(self.hierarchy_marks)
        self.hierarchy_marks = [
            mark for mark in self.hierarchy_marks
            if self._hierarchy_mark_key(mark) not in key_set
        ]
        removed = before - len(self.hierarchy_marks)
        if removed:
            self._collapsed_hierarchy_keys.difference_update(key_set)
            for key in key_set:
                self._outline_expansion_overrides.pop(key, None)
            if self._range_edit_mark_key in key_set or key_set.intersection(self._bulk_edit_mark_keys):
                self._stop_range_edit()
            self._refresh()
            self._record_history()
        return removed

    def _ignore_mark_keys_for_range(self, start: int, end: int) -> list[str]:
        return [
            self._hierarchy_mark_key(mark)
            for mark in self.hierarchy_marks
            if mark.type_id == HierarchyType.IGNORE
            and self._ranges_overlap(mark.start_line, mark.end_line, start, end)
        ]

    def _ignore_gap_can_merge(
        self,
        start_line: int,
        end_line: int,
        raw_lines: list[str],
        non_ignore_marks: list[HierarchyMark],
    ) -> bool:
        if start_line > end_line:
            return True
        for mark in non_ignore_marks:
            if (
                self._ranges_overlap(mark.start_line, mark.end_line, start_line, end_line)
                and not (mark.start_line < start_line and end_line < mark.end_line)
            ):
                return False
        for line_no in range(start_line, end_line + 1):
            if 0 <= line_no < len(raw_lines) and raw_lines[line_no].strip():
                return False
        return True

    def _merge_adjacent_ignore_marks(self, raw_lines: list[str] | None = None) -> bool:
        raw_lines = raw_lines if raw_lines is not None else self.raw_edit.toPlainText().splitlines()
        ignore_marks = sorted(
            [mark for mark in self.hierarchy_marks if mark.type_id == HierarchyType.IGNORE],
            key=lambda mark: (mark.start_line, mark.end_line, mark.order),
        )
        if not ignore_marks:
            return False

        old_keys = {self._hierarchy_mark_key(mark) for mark in ignore_marks}
        others = [mark for mark in self.hierarchy_marks if mark.type_id != HierarchyType.IGNORE]
        merged: list[HierarchyMark] = []
        changed = False
        for mark in ignore_marks:
            if mark.depth != 0:
                mark.depth = 0
                changed = True
            if merged and self._ignore_gap_can_merge(
                merged[-1].end_line + 1,
                mark.start_line - 1,
                raw_lines,
                others,
            ):
                target = merged[-1]
                target.end_line = max(target.end_line, mark.end_line)
                target.start_line = min(target.start_line, mark.start_line)
                target.order = min(target.order, mark.order)
                if not target.text and mark.text:
                    target.text = mark.text
                changed = True
            else:
                merged.append(mark)

        new_keys = {self._hierarchy_mark_key(mark) for mark in merged}
        removed_keys = old_keys - new_keys
        if removed_keys:
            self._collapsed_hierarchy_keys.difference_update(removed_keys)
            for key in removed_keys:
                self._outline_expansion_overrides.pop(key, None)
            if self._range_edit_mark_key in removed_keys or removed_keys.intersection(self._bulk_edit_mark_keys):
                self._stop_range_edit()
        if changed:
            self.hierarchy_marks = others + merged
        return changed

    def _hierarchy_mark_for_key(self, key: str | None) -> HierarchyMark | None:
        if not key:
            return None
        return self._hierarchy_mark_by_key_map().get(str(key))

    def _change_outline_depth_keys(self, keys, delta: int) -> int:
        key_set = {str(key) for key in keys if key}
        if not key_set or delta == 0:
            return 0

        changed = 0
        reveal_keys = []
        for mark in self.hierarchy_marks:
            old_key = self._hierarchy_mark_key(mark)
            if old_key not in key_set or mark.type_id == HierarchyType.IGNORE:
                continue
            new_depth = max(0, mark.depth + delta)
            if new_depth != mark.depth:
                mark.depth = new_depth
                new_key = self._hierarchy_mark_key(mark)
                self._replace_active_edit_key(old_key, new_key)
                reveal_keys.append(new_key)
                changed += 1
        if changed:
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return changed

    def _change_selected_outline_depth(
        self,
        items: list[QTreeWidgetItem],
        delta: int,
    ) -> int:
        if self.mode != "hierarchy" or delta == 0:
            return 0
        branch_groups = self._outline_key_groups(items, include_children=True)
        root_marks = [
            self._hierarchy_mark_for_key(group[0])
            for group in branch_groups
            if group
        ]
        changed = self._change_outline_depth_keys(
            self._flatten_key_groups(branch_groups),
            delta,
        )
        if changed:
            selected_items = [
                self._outline_item_for_mark_key(self._hierarchy_mark_key(mark))
                for mark in root_marks
                if mark is not None
            ]
            selected_items = [item for item in selected_items if item is not None]
            self.flags_list.clearSelection()
            for item in selected_items:
                item.setSelected(True)
            if selected_items:
                self.flags_list._set_current_without_selection_change(selected_items[0])
                self.flags_list._selection_anchor_item = selected_items[0]
        return changed

    def _apply_outline_type_depth_keys(self, keys) -> int:
        key_set = {str(key) for key in keys if key}
        if not key_set:
            return 0

        type_def = self._current_hierarchy_type_def()
        depth = 0 if type_def.type_id == HierarchyType.IGNORE else self.hierarchy_depth_spin.value()
        changed = 0
        reveal_keys = []
        for mark in self.hierarchy_marks:
            old_key = self._hierarchy_mark_key(mark)
            if old_key not in key_set:
                continue
            if (
                mark.type_id == type_def.type_id
                and mark.depth == depth
                and mark.description == type_def.description
            ):
                continue
            mark.type_id = type_def.type_id
            mark.depth = depth
            mark.description = type_def.description
            new_key = self._hierarchy_mark_key(mark)
            self._replace_active_edit_key(old_key, new_key)
            reveal_keys.append(new_key)
            changed += 1
        if changed:
            self._apply_ignore_precedence()
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return changed

    def _set_outline_branch_depth(self, keys, target_depth: int) -> int:
        key_list = [str(key) for key in keys if key]
        if not key_list:
            return 0
        root = self._hierarchy_mark_for_key(key_list[0])
        if root is None or root.type_id == HierarchyType.IGNORE:
            return 0
        return self._change_outline_depth_keys(key_list, max(0, target_depth) - root.depth)

    def _set_outline_branch_groups_depth(self, groups: list[list[str]], target_depth: int) -> int:
        changed = 0
        reveal_keys = []
        for group in groups:
            key_list = [str(key) for key in group if key]
            if not key_list:
                continue
            root = self._hierarchy_mark_for_key(key_list[0])
            if root is None or root.type_id == HierarchyType.IGNORE:
                continue
            key_set = set(key_list)
            delta = max(0, target_depth) - root.depth
            if delta == 0:
                continue
            for mark in self.hierarchy_marks:
                old_key = self._hierarchy_mark_key(mark)
                if old_key not in key_set or mark.type_id == HierarchyType.IGNORE:
                    continue
                mark.depth = max(0, mark.depth + delta)
                self._replace_active_edit_key(old_key, self._hierarchy_mark_key(mark))
                changed += 1
            reveal_keys.extend(key_list)
        if changed:
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return changed

    def _delete_outline_item_marks(
        self,
        item: QTreeWidgetItem,
        include_children: bool = False,
    ) -> int:
        return self._delete_outline_mark_keys(
            self._outline_mark_keys(item, include_children=include_children)
        )

    def _target_depth_from_drop(
        self,
        target_item: QTreeWidgetItem | None,
        indicator,
    ) -> int | None:
        if target_item is None or indicator == QAbstractItemView.DropIndicatorPosition.OnViewport:
            return 0

        target_key = self._outline_item_data(target_item, _OUTLINE_MARK_KEY_ROLE)
        target_mark = self._hierarchy_mark_for_key(str(target_key) if target_key else None)
        if target_mark is None or target_mark.type_id == HierarchyType.IGNORE:
            return None
        return target_mark.depth + 1

    def _handle_outline_drop(
        self,
        selected_items: list[QTreeWidgetItem],
        target_item: QTreeWidgetItem | None,
        indicator,
    ) -> bool:
        if self.mode != "hierarchy" or not selected_items:
            return False
        source_items = [
            item for item in selected_items
            if self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
        ]
        branch_groups = self._outline_key_groups(source_items, include_children=False)
        if not branch_groups:
            return False

        target_key = self._outline_item_data(target_item, _OUTLINE_MARK_KEY_ROLE)
        branch_keys = set(self._flatten_key_groups(branch_groups))
        if target_key and str(target_key) in branch_keys:
            return False

        target_depth = self._target_depth_from_drop(target_item, indicator)
        if target_depth is None:
            return False
        return bool(self._set_outline_branch_groups_depth(branch_groups, target_depth))
