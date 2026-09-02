"""Outline context menu and speaker/role conversion actions."""
from __future__ import annotations


from PyQt6.QtWidgets import (
    QMenu,
    QInputDialog,
)
from PyQt6.QtCore import QPoint
from core.script_markup import (
    HierarchyMark, HierarchyType, mark_text,
)
from core.i18n import tr

from ui.script_markup.constants import (
    _OUTLINE_LINE_ROLE,
    _OUTLINE_MARK_KEY_ROLE,
    _ASSIGNED_SPEAKER_ORIGIN,
)


class OutlineContextMixin:
    """Outline context menu and speaker/role conversion actions."""

    def _known_speaker_names(self) -> list[str]:
        raw_lines = self.raw_edit.toPlainText().splitlines()
        names = {
            self._clean_mark_text(mark.text or mark_text(mark, raw_lines))
            for mark in self.hierarchy_marks
            if mark.type_id == HierarchyType.SPEAKER
        }
        names.discard("")
        return sorted(names, key=str.casefold)

    def _assign_text_marks_to_speaker(
        self,
        keys,
        speaker_name: str | None = None,
    ) -> int:
        text_marks = [
            mark
            for key in dict.fromkeys(str(key) for key in keys if key)
            if (mark := self._hierarchy_mark_for_key(key)) is not None
            and mark.type_id == HierarchyType.TEXT
        ]
        if not text_marks:
            return 0

        if speaker_name is None:
            speaker_name, accepted = QInputDialog.getItem(
                self,
                "Assign to speaker",
                "Speaker:",
                self._known_speaker_names(),
                0,
                True,
            )
            if not accepted:
                return 0
        speaker_name = self._clean_mark_text(speaker_name)
        if not speaker_name:
            return 0

        raw_lines = self.raw_edit.toPlainText().splitlines()
        speaker_def = self.hierarchy_type_definitions[HierarchyType.SPEAKER]
        reveal_keys = []
        changed = 0
        for text_mark in text_marks:
            anchor = self._speaker_anchor_for_text(text_mark)
            speaker_mark = next(
                (
                    mark
                    for mark in self.hierarchy_marks
                    if mark.type_id == HierarchyType.SPEAKER
                    and mark.start_line == anchor
                    and mark.depth == max(0, text_mark.depth - 1)
                    and mark.origin == _ASSIGNED_SPEAKER_ORIGIN
                ),
                None,
            )
            if speaker_mark is None and text_mark.depth > 0:
                # Repair speakers created by the previous implementation on the
                # blank line before this Text. After the Text was deepened, that
                # stale speaker has exactly Text.depth - 1 but may sit outside a
                # Structure that starts on the Text line.
                previous = anchor - 1
                if previous >= 0 and not raw_lines[previous].strip():
                    speaker_mark = next(
                        (
                            mark
                            for mark in self.hierarchy_marks
                            if mark.type_id == HierarchyType.SPEAKER
                            and mark.start_line == previous
                            and mark.end_line == previous
                            and mark.depth == text_mark.depth - 1
                            and mark.origin == _ASSIGNED_SPEAKER_ORIGIN
                        ),
                        None,
                    )
                    if speaker_mark is not None:
                        speaker_mark.start_line = anchor
                        speaker_mark.end_line = anchor
            if speaker_mark is None:
                speaker_depth = text_mark.depth
                speaker_mark = HierarchyMark(
                    anchor,
                    anchor,
                    speaker_depth,
                    HierarchyType.SPEAKER,
                    description=speaker_def.description,
                    order=self._next_hierarchy_order(),
                    origin=_ASSIGNED_SPEAKER_ORIGIN,
                )
                self.hierarchy_marks.append(speaker_mark)
            speaker_mark.text = speaker_name
            speaker_mark.origin = _ASSIGNED_SPEAKER_ORIGIN
            speaker_mark.approved = True
            text_mark.depth = speaker_mark.depth + 1
            text_mark.origin = "manual"
            text_mark.approved = True
            reveal_keys.append(self._hierarchy_mark_key(text_mark))
            changed += 1

        if changed:
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return changed

    def _convert_role_blocks(
        self,
        block_keys,
        *,
        source_block_type: str,
        target_block_type: str,
        source_child_type: str,
        target_child_type: str,
    ) -> int:
        """Convert selected role branches while preserving their ranges and depths."""
        selected = {
            str(key)
            for key in block_keys
            if key
            and (mark := self._hierarchy_mark_for_key(str(key))) is not None
            and mark.type_id == source_block_type
        }
        if not selected:
            return 0

        paths = self._hierarchy_paths_by_key()
        block_def = self.hierarchy_type_definitions[target_block_type]
        child_def = self.hierarchy_type_definitions[target_child_type]
        converted = 0
        reveal_keys = []
        for mark in self.hierarchy_marks:
            old_key = self._hierarchy_mark_key(mark)
            if old_key in selected:
                mark.type_id = target_block_type
                mark.description = block_def.description
                mark.origin = "manual"
                mark.approved = True
                reveal_keys.append(self._hierarchy_mark_key(mark))
                converted += 1
                continue
            if mark.type_id != source_child_type:
                continue
            path = paths.get(old_key, ())
            if len(path) < 2 or self._hierarchy_mark_key(path[-2]) not in selected:
                continue
            mark.type_id = target_child_type
            mark.description = child_def.description
            mark.origin = "manual"
            mark.approved = True
            reveal_keys.append(self._hierarchy_mark_key(mark))
            converted += 1

        if converted:
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return converted

    def _convert_speaker_blocks_to_items(self, speaker_keys) -> int:
        """Convert selected Speaker -> Text branches into Item -> Item Description."""
        return self._convert_role_blocks(
            speaker_keys,
            source_block_type=HierarchyType.SPEAKER,
            target_block_type=HierarchyType.ITEM,
            source_child_type=HierarchyType.TEXT,
            target_child_type=HierarchyType.ITEM_DESCRIPTION,
        )

    def _convert_item_blocks_to_speakers(self, item_keys) -> int:
        """Convert selected Item -> Item Description branches into Speaker -> Text."""
        return self._convert_role_blocks(
            item_keys,
            source_block_type=HierarchyType.ITEM,
            target_block_type=HierarchyType.SPEAKER,
            source_child_type=HierarchyType.ITEM_DESCRIPTION,
            target_child_type=HierarchyType.TEXT,
        )

    def _show_outline_context_menu(self, pos: QPoint):
        item = self.flags_list.itemAt(pos)
        if item is None:
            return
        line_no = self._outline_item_data(item, _OUTLINE_LINE_ROLE)
        context_items = self._outline_context_items(item)
        action_items = [
            selected for selected in context_items
            if self._outline_item_data(selected, _OUTLINE_MARK_KEY_ROLE)
        ]
        selected_groups = self._outline_key_groups(action_items, include_children=False)
        mark_keys = self._flatten_key_groups(selected_groups)
        context_mark_keys = self._flatten_key_groups(
            self._outline_key_groups(context_items, include_children=True)
        )
        direct_mark_keys = self._outline_direct_mark_keys(action_items)
        text_mark_keys = [
            key
            for key in direct_mark_keys
            if (
                (mark := self._hierarchy_mark_for_key(key)) is not None
                and mark.type_id == HierarchyType.TEXT
            )
        ]
        speaker_mark_keys = [
            key
            for key in direct_mark_keys
            if (
                (mark := self._hierarchy_mark_for_key(key)) is not None
                and mark.type_id == HierarchyType.SPEAKER
            )
        ]
        item_mark_keys = [
            key
            for key in direct_mark_keys
            if (
                (mark := self._hierarchy_mark_for_key(key)) is not None
                and mark.type_id == HierarchyType.ITEM
            )
        ]
        branch_groups = self._outline_key_groups(action_items, include_children=True)
        branch_keys = self._flatten_key_groups(branch_groups)
        primary_key = mark_keys[0] if mark_keys else None
        primary_mark = self._hierarchy_mark_for_key(primary_key)
        selected_count = len(mark_keys)

        menu = QMenu(self)
        jump_action = menu.addAction(tr('Jump to source'))
        open_game_action = None
        delete_action = None
        delete_branch_action = None
        rename_action = None
        approve_action = None
        edit_range_action = None
        stop_range_action = None
        join_structures_action = None
        depth_up_action = None
        depth_down_action = None
        depth_actions = {}
        mark_ignored_action = None
        mark_unmarked_action = None
        assign_speaker_action = None
        convert_items_action = None
        convert_speakers_action = None
        if self.mode == "hierarchy" and context_items:
            context_count = len(context_items)
            mark_ignored_action = menu.addAction(
                "Mark as IGNORED"
                if context_count == 1 else
                f"Mark {context_count} selected as IGNORED"
            )
            mark_unmarked_action = menu.addAction(
                "Mark as UNMARKED"
                if context_count == 1 else
                f"Mark {context_count} selected as UNMARKED"
            )
            mark_unmarked_action.setEnabled(bool(context_mark_keys))
            menu.addSeparator()
        if self.mode == "hierarchy" and mark_keys:
            if selected_count == 1:
                open_game_action = menu.addAction(tr('Open linked game row'))
            if speaker_mark_keys:
                convert_items_action = menu.addAction(
                    "Convert Speaker Block to Item"
                    if len(speaker_mark_keys) == 1 else
                    "Convert Speaker Blocks to Items"
                )
            if item_mark_keys:
                convert_speakers_action = menu.addAction(
                    "Convert Item Block to Speaker"
                    if len(item_mark_keys) == 1 else
                    "Convert Item Blocks to Speakers"
                )
            if text_mark_keys:
                assign_speaker_action = menu.addAction(
                    "Assign to speaker..."
                    if len(text_mark_keys) == 1
                    else f"Assign {len(text_mark_keys)} Text blocks to speaker..."
                )
            if any(
                (mark := self._hierarchy_mark_for_key(key)) is not None and not mark.approved
                for key in mark_keys
            ):
                approve_action = menu.addAction(
                    "Approve as Auto-fill example"
                    if selected_count == 1 else
                    f"Approve {selected_count} as Auto-fill examples"
                )
            if selected_count == 1:
                rename_action = menu.addAction(tr('Rename node...'))
                edit_range_action = menu.addAction(tr('Edit node'))
            else:
                edit_range_action = menu.addAction(f"Edit {selected_count} selected nodes")
            if (
                primary_key and self._range_edit_mark_key == primary_key
                or set(mark_keys).intersection(self._bulk_edit_mark_keys)
            ):
                stop_range_action = menu.addAction(tr('Stop editing'))
            if len(self._joinable_structure_marks_for_keys(direct_mark_keys)) >= 2:
                join_structures_action = menu.addAction(tr('Join selected structures'))
            movable_marks = [
                self._hierarchy_mark_for_key(key)
                for key in mark_keys
            ]
            movable_marks = [
                mark for mark in movable_marks
                if mark is not None and mark.type_id != HierarchyType.IGNORE
            ]
            if movable_marks:
                branch_label = "selection" if selected_count > 1 else (
                    "branch" if len(mark_keys) > 1 else "node"
                )
                depth_title = "Depth" if selected_count > 1 else f"Depth ({primary_mark.depth})"
                depth_menu = menu.addMenu(depth_title)
                depth_up_action = depth_menu.addAction(f"Move {branch_label} shallower")
                depth_up_action.setEnabled(any(mark.depth > 0 for mark in movable_marks))
                depth_down_action = depth_menu.addAction(f"Move {branch_label} deeper")
                set_depth_menu = depth_menu.addMenu(tr('Set depth'))
                max_depth = max(
                    6,
                    max((m.depth for m in self.hierarchy_marks), default=0) + 2,
                )
                for depth in range(max_depth + 1):
                    action = set_depth_menu.addAction(str(depth))
                    action.setCheckable(True)
                    action.setChecked(selected_count == 1 and primary_mark is not None and depth == primary_mark.depth)
                    depth_actions[action] = depth
            menu.addSeparator()
            delete_label = "Delete selected nodes" if selected_count > 1 else "Delete node"
            delete_action = menu.addAction(delete_label)
            if len(branch_keys) > len(mark_keys):
                delete_branch_action = menu.addAction(
                    "Delete selected nodes and children"
                    if selected_count > 1 else
                    "Delete node and children"
                )

        chosen = menu.exec(self.flags_list.viewport().mapToGlobal(pos))
        if chosen == jump_action:
            self._jump_to_line_no(line_no)
        elif open_game_action is not None and chosen == open_game_action:
            self._open_mark_in_game_project(primary_mark)
        elif mark_ignored_action is not None and chosen == mark_ignored_action:
            self._mark_outline_items_ignored(context_items)
        elif mark_unmarked_action is not None and chosen == mark_unmarked_action:
            self._mark_outline_items_unmarked(context_items)
        elif approve_action is not None and chosen == approve_action:
            self._approve_hierarchy_mark_keys(mark_keys)
        elif assign_speaker_action is not None and chosen == assign_speaker_action:
            self._assign_text_marks_to_speaker(text_mark_keys)
        elif convert_items_action is not None and chosen == convert_items_action:
            self._convert_speaker_blocks_to_items(speaker_mark_keys)
        elif convert_speakers_action is not None and chosen == convert_speakers_action:
            self._convert_item_blocks_to_speakers(item_mark_keys)
        elif rename_action is not None and chosen == rename_action:
            self._rename_outline_item(item)
        elif edit_range_action is not None and chosen == edit_range_action:
            if selected_count == 1:
                self._start_range_edit(primary_key)
            else:
                self._start_bulk_hierarchy_edit(mark_keys)
        elif stop_range_action is not None and chosen == stop_range_action:
            self._stop_range_edit()
        elif join_structures_action is not None and chosen == join_structures_action:
            self._join_structure_mark_keys(direct_mark_keys)
        elif depth_up_action is not None and chosen == depth_up_action:
            self._change_outline_depth_keys(mark_keys, -1)
        elif depth_down_action is not None and chosen == depth_down_action:
            self._change_outline_depth_keys(mark_keys, 1)
        elif chosen in depth_actions:
            self._set_outline_branch_groups_depth(selected_groups, depth_actions[chosen])
        elif delete_action is not None and chosen == delete_action:
            self._delete_outline_mark_keys(mark_keys)
        elif delete_branch_action is not None and chosen == delete_branch_action:
            self._delete_outline_mark_keys(branch_keys)
