"""Outline navigation, jump, rename, and mark key helpers."""
from __future__ import annotations

import re

from PyQt6 import sip
from PyQt6.QtWidgets import (
    QMessageBox, QLineEdit, QTreeWidgetItem, QInputDialog,
)
from core.script_markup import (
    HierarchyMark, HierarchyType, mark_text,
)
from core.mempalace.story_timeline import StoryVirtualMapping, story_stable_id_for_mark
from core.i18n import tr

from ui.script_markup.constants import (
    _OUTLINE_LINE_ROLE,
    _OUTLINE_ENTRY_KEY_ROLE,
    _OUTLINE_MARK_KEY_ROLE,
)


class OutlineNavMixin:
    """Outline navigation, jump, rename, and mark key helpers."""

    def _outline_item_data(self, item: QTreeWidgetItem | None, role):
        try:
            if item is None or sip.isdeleted(item):
                return None
            return item.data(0, role)
        except RuntimeError:
            return None

    def _hierarchy_mark_at_line(
        self,
        line_no: int | None,
        column: int | None = None,
    ) -> HierarchyMark | None:
        if line_no is None:
            return None
        candidates = [
            mark for mark in self.hierarchy_marks
            if mark.start_line <= line_no <= mark.end_line
            and mark.type_id not in (HierarchyType.IGNORE, HierarchyType.UNMARKED)
            and (
                column is None
                or mark.start_col is None
                or mark.start_line != mark.end_line
                or mark.start_col <= column < (mark.end_col if mark.end_col is not None else 10**9)
            )
        ]
        if not candidates:
            return None
        type_priority = {
            HierarchyType.TEXT: 4,
            HierarchyType.CONTEXT: 5,
            HierarchyType.SPEAKER: 3,
            HierarchyType.ACTION: 3,
            HierarchyType.NARRATOR: 3,
            HierarchyType.BREAKER: 3,
            HierarchyType.STRUCTURE: 1,
        }
        return max(
            candidates,
            key=lambda mark: (
                type_priority.get(mark.type_id, 2),
                mark.depth,
                -(mark.end_line - mark.start_line),
                mark.order,
            ),
        )

    def _outline_item_for_mark_key(self, mark_key: str) -> QTreeWidgetItem | None:
        matched = None

        def walk(item: QTreeWidgetItem):
            nonlocal matched
            if matched is not None or sip.isdeleted(item):
                return
            if self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE) == mark_key:
                matched = item
                return
            for idx in range(item.childCount()):
                walk(item.child(idx))

        for idx in range(self.flags_list.topLevelItemCount()):
            walk(self.flags_list.topLevelItem(idx))
        return matched

    def _jump_raw_line_to_outline(
        self,
        line_no: int | None,
        column: int | None = None,
    ) -> bool:
        mark = self._hierarchy_mark_at_line(line_no, column)
        if mark is None:
            return False
        key = self._hierarchy_mark_key(mark)
        item = self._outline_item_for_mark_key(key)
        if item is None:
            self._queue_outline_reveal(key)
            self._refresh_hierarchy()
            item = self._outline_item_for_mark_key(key)
        if item is None:
            return False
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self.flags_list.clearSelection()
        self.flags_list.setCurrentItem(item)
        item.setSelected(True)
        self.flags_list._selection_anchor_item = item
        self.flags_list.scrollToItem(item)
        self.flags_list.setFocus()
        return True

    def _outline_selection_key(self, item: QTreeWidgetItem | None):
        return (
            self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
            or self._outline_item_data(item, _OUTLINE_ENTRY_KEY_ROLE)
        )

    def _outline_item_children(self, item: QTreeWidgetItem | None) -> list[QTreeWidgetItem]:
        try:
            if item is None or sip.isdeleted(item):
                return []
            return [item.child(idx) for idx in range(item.childCount()) if item.child(idx) is not None]
        except RuntimeError:
            return []

    def _jump_to_line_no(self, line_no) -> bool:
        if line_no is None or line_no == "":
            return False
        try:
            raw_line_no = int(line_no)
        except (TypeError, ValueError):
            return False
        if raw_line_no <= 0:
            return False
        block = self.raw_edit.document().findBlockByNumber(raw_line_no - 1)
        if block.isValid():
            self._raw_navigation_line = raw_line_no - 1
            cursor = self.raw_edit.textCursor()
            cursor.setPosition(block.position())
            self.raw_edit.setTextCursor(cursor)
            self._scroll_raw_to_position(block.position())
            self._apply_raw_extra_selections()
            self.raw_edit.setFocus()
            return True
        return False

    def _jump_to_flag(self, item: QTreeWidgetItem, _column: int = 0):
        return self._jump_to_line_no(self._outline_item_data(item, _OUTLINE_LINE_ROLE))

    def _open_mark_in_game_project(self, mark: HierarchyMark | None) -> bool:
        """Open a concrete game row linked to this normalized story node."""
        if mark is None or self.mw is None or not self.current_hierarchy_project_path:
            return False
        translation = getattr(self.mw, "translation_handler", None)
        composer = getattr(translation, "prompt_composer", None)
        client = composer._get_mempalace_client() if composer else None
        if client is None:
            return False
        document_id = client.get_story_document_id(self.current_hierarchy_project_path)
        if document_id is None:
            return False
        mappings = client.get_story_mappings_for_node(
            document_id, story_stable_id_for_mark(mark)
        )
        if not mappings and mark.type_id in (HierarchyType.ITEM, HierarchyType.ITEM_DESCRIPTION):
            item_mark = mark
            if mark.type_id == HierarchyType.ITEM_DESCRIPTION:
                preceding = [
                    candidate for candidate in self.hierarchy_marks
                    if candidate.type_id == HierarchyType.ITEM
                    and candidate.order < mark.order and candidate.depth < mark.depth
                ]
                item_mark = max(preceding, key=lambda candidate: candidate.order) if preceding else mark
            item_name = mark_text(item_mark, self.raw_edit.toPlainText().splitlines()).strip()
            block_updater = getattr(getattr(self.mw, "ui_updater", None), "block_list_updater", None)
            reverse = getattr(block_updater, "_story_item_mappings_cache", {})
            mappings = tuple(
                StoryVirtualMapping(str(block_idx), "", string_idx)
                for (block_idx, string_idx), name in reverse.items()
                if name == item_name
            )
        if not mappings:
            QMessageBox.information(
                self, tr('No linked game row'),
                tr('This marked node does not have a saved game-string link yet.')
            )
            return False
        mapping = mappings[0]
        if len(mappings) > 1:
            labels = []
            by_label = {}
            data = getattr(getattr(self.mw, "data_store", None), "data", [])
            names = getattr(getattr(self.mw, "data_store", None), "block_names", {})
            for candidate in mappings:
                try:
                    block_idx = int(candidate.game_block_id)
                    text_value = str(data[block_idx][candidate.string_index]).replace("\n", " ")
                except (ValueError, IndexError, TypeError):
                    block_idx = -1
                    text_value = ""
                block_name = names.get(str(block_idx), candidate.game_block_id)
                label = f"{block_name} · row {candidate.string_index + 1} · {text_value[:90]}"
                labels.append(label)
                by_label[label] = candidate
            chosen, accepted = QInputDialog.getItem(
                self, "Open linked game row", "Choose a linked row:", labels, 0, False
            )
            if not accepted:
                return False
            mapping = by_label[chosen]
        handler = getattr(self.mw, "list_selection_handler", None)
        if handler is None or not handler.navigate_to_physical_string(
            int(mapping.game_block_id), mapping.string_index
        ):
            return False
        self.mw.show()
        self.mw.raise_()
        self.mw.activateWindow()
        return True

    def _rename_outline_item(self, item: QTreeWidgetItem | None) -> bool:
        if self.mode != "hierarchy":
            return False
        key = self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
        mark = self._hierarchy_mark_for_key(key)
        if mark is None:
            return False

        raw_lines = self.raw_edit.toPlainText().splitlines()
        current = self._hierarchy_mark_display_text(mark, limit=240, raw_lines=raw_lines)
        type_def = self.hierarchy_type_definitions.get(mark.type_id)
        label = type_def.label if type_def else str(mark.type_id).title()
        new_text, accepted = QInputDialog.getText(
            self,
            "Rename node",
            f"{label} name:",
            QLineEdit.EchoMode.Normal,
            current,
        )
        if not accepted:
            return False

        cleaned = self._clean_mark_text(new_text)
        if cleaned == (mark.text or ""):
            return False

        old_key = self._hierarchy_mark_key(mark)
        mark.text = cleaned
        new_key = self._hierarchy_mark_key(mark)
        self._replace_active_edit_key(old_key, new_key)
        self._queue_outline_reveal(new_key)
        self._refresh()
        self._record_history()
        return True

    def _approve_hierarchy_mark_keys(self, keys) -> int:
        approved = 0
        reveal_keys = []
        for key in dict.fromkeys(str(key) for key in keys if key):
            mark = self._hierarchy_mark_for_key(key)
            if mark is None or mark.approved:
                continue
            old_key = self._hierarchy_mark_key(mark)
            mark.approved = True
            new_key = self._hierarchy_mark_key(mark)
            self._replace_active_edit_key(old_key, new_key)
            reveal_keys.append(new_key)
            approved += 1
        if approved:
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return approved

    def _outline_mark_keys(self, item: QTreeWidgetItem, include_children: bool) -> list[str]:
        keys = []
        key = self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
        if key:
            keys.append(str(key))
        if include_children:
            for child in self._outline_item_children(item):
                keys.extend(self._outline_mark_keys(child, include_children=True))
        return keys

    def _outline_action_items(self, clicked_item: QTreeWidgetItem | None) -> list[QTreeWidgetItem]:
        if clicked_item is None or self._outline_item_data(clicked_item, _OUTLINE_MARK_KEY_ROLE) is None:
            return []
        selected = self.flags_list.selectedItems()
        if clicked_item not in selected:
            self.flags_list.clearSelection()
            clicked_item.setSelected(True)
            self.flags_list.setCurrentItem(clicked_item)
            selected = [clicked_item]
        return [
            item for item in selected
            if self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
        ]

    def _outline_context_items(self, clicked_item: QTreeWidgetItem | None) -> list[QTreeWidgetItem]:
        if clicked_item is None or self._outline_selection_key(clicked_item) is None:
            return []
        selected = self.flags_list.selectedItems()
        if clicked_item not in selected:
            self.flags_list.clearSelection()
            clicked_item.setSelected(True)
            self.flags_list.setCurrentItem(clicked_item)
            selected = [clicked_item]
        return [item for item in selected if self._outline_selection_key(item) is not None]

    def _outline_unmarked_range(self, item: QTreeWidgetItem) -> tuple[int, int] | None:
        entry_key = str(self._outline_item_data(item, _OUTLINE_ENTRY_KEY_ROLE) or "")
        match = re.fullmatch(r"unmarked:(\d+):(\d+)", entry_key)
        if not match:
            return None
        return int(match.group(1)), int(match.group(2))

    def _outline_item_range_groups(
        self,
        items: list[QTreeWidgetItem],
    ) -> list[tuple[int, int]]:
        ranges = []
        for item in self._outline_root_items(items):
            unmarked_range = self._outline_unmarked_range(item)
            if unmarked_range is not None:
                ranges.append(unmarked_range)
                continue
            marks = [
                self._hierarchy_mark_for_key(key)
                for key in self._outline_mark_keys(item, include_children=True)
            ]
            marks = [mark for mark in marks if mark is not None]
            if marks:
                ranges.append((
                    min(mark.start_line for mark in marks),
                    max(mark.end_line for mark in marks),
                ))
        return ranges

    def _mark_outline_items_ignored(self, items: list[QTreeWidgetItem]) -> int:
        ranges = self._outline_item_range_groups(items)
        if not ranges:
            return 0
        for start, end in ranges:
            self.hierarchy_marks.append(HierarchyMark(
                start_line=start,
                end_line=end,
                depth=0,
                type_id=HierarchyType.IGNORE,
                order=self._next_hierarchy_order(),
            ))
        self._apply_ignore_precedence()
        self._merge_adjacent_ignore_marks()
        self._refresh()
        self._record_history()
        return len(ranges)

    def _mark_outline_items_unmarked(self, items: list[QTreeWidgetItem]) -> int:
        keys = self._flatten_key_groups(
            self._outline_key_groups(items, include_children=True)
        )
        return self._delete_outline_mark_keys(keys)
