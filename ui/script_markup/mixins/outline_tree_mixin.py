"""Outline tree refresh, fill, expansion, and filter helpers."""
from __future__ import annotations


from PyQt6 import sip
from PyQt6.QtWidgets import (
    QTreeWidgetItem,
)
from PyQt6.QtGui import (
    QColor,
)
from core.script_markup import (
    convert, LineKind,
    parse_with_rules, transcript_to_psm, summarize_transcript,
    annotate_source_lines,
    HierarchyMark, HierarchyType, mark_text,
    render_hierarchy_markdown,
)
from core.script_markup.markup_engine import render_psm

from ui.script_markup.constants import (
    _MAX_UNMARKED_HIGHLIGHT_LINES,
    _UNMARKED_GROUP_THRESHOLD,
    _MAX_UNMARKED_TREE_CHILDREN,
    _MAX_IGNORED_TREE_CHILDREN,
    _OUTLINE_LINE_ROLE,
    _OUTLINE_ENTRY_KEY_ROLE,
    _OUTLINE_MARK_KEY_ROLE,
    _ASSIGNED_SPEAKER_ORIGIN,
)


class OutlineTreeMixin:
    """Outline tree refresh, fill, expansion, and filter helpers."""

    # ------------------------------------------------------------- refresh
    def _refresh(self):
        self._invalidate_hierarchy_mark_caches()
        if self.mode == "picoripi":
            self._refresh_picoripi()
        elif self.mode == "hierarchy":
            self._refresh_hierarchy()
        else:
            self._refresh_custom()
        self._update_preview_dialog()
        self._restore_search_highlight()
        self._update_progress_and_next_action()
        self._update_save_status()

    def _refresh_hierarchy(self):
        text = self.raw_edit.toPlainText()
        raw_lines = text.splitlines()
        self._apply_ignore_precedence(raw_lines)
        self._normalize_text_marks_around_content_nodes(raw_lines)
        self._psm_text = render_hierarchy_markdown(
            self.hierarchy_marks,
            text,
            self.hierarchy_type_definitions,
        )

        styles = dict(self._hierarchy_base_line_styles())
        unmarked_def = self.hierarchy_type_definitions[HierarchyType.UNMARKED]
        unmarked_ranges = self._unmarked_ranges(raw_lines)
        self._has_unmarked_hierarchy_lines = bool(unmarked_ranges)
        unmarked_line_count = sum(end - start + 1 for start, end in unmarked_ranges)
        if unmarked_line_count <= _MAX_UNMARKED_HIGHLIGHT_LINES:
            for start, end in unmarked_ranges:
                for idx in range(start, end + 1):
                    styles[idx] = (HierarchyType.UNMARKED, unmarked_def.color)
        line_kinds = {idx: type_id for idx, (type_id, _color) in styles.items()}
        line_colors = {idx: color for idx, (_type_id, color) in styles.items()}
        self.highlighter.set_line_kinds(line_kinds, line_colors=line_colors)
        self._update_raw_minimap()
        self._apply_raw_hierarchy_view(raw_lines)

        max_depth = max((mark.depth for mark in self.hierarchy_marks), default=0)
        type_counts: dict[str, int] = {}
        for mark in self.hierarchy_marks:
            type_counts[mark.type_id] = type_counts.get(mark.type_id, 0) + 1
        typed = ", ".join(
            f"{self.hierarchy_type_definitions.get(type_id).label if self.hierarchy_type_definitions.get(type_id) else type_id}: {count}"
            for type_id, count in sorted(type_counts.items())
        )
        self.stats_label.setText(
            f"Nodes: {len(self.hierarchy_marks)} | Max depth: {max_depth}"
            + (f" | {typed}" if typed else "")
        )
        self._update_legend()
        self._fill_hierarchy_outline(raw_lines, unmarked_ranges)
        self._apply_raw_extra_selections()

    def _short_source_text(
        self,
        start: int,
        end: int,
        limit: int = 96,
        raw_lines: list[str] | None = None,
    ) -> str:
        text = self._source_text_for_lines(start, end, raw_lines)
        if len(text) <= limit:
            return text
        return text[:limit - 1].rstrip() + "..."

    def _hierarchy_mark_display_text(
        self,
        mark: HierarchyMark,
        limit: int = 96,
        raw_lines: list[str] | None = None,
    ) -> str:
        lines = raw_lines if raw_lines is not None else self.raw_edit.toPlainText().splitlines()
        text = mark_text(mark, lines)
        if len(text) <= limit:
            return text
        return text[:limit - 1].rstrip() + "..."

    def _hierarchy_mark_key(self, mark: HierarchyMark) -> str:
        return (
            f"mark:{mark.order}:{mark.start_line}:{mark.end_line}:"
            f"{mark.depth}:{mark.type_id}:{mark.start_col}:{mark.end_col}:{mark.text}"
        )

    def _collect_outline_expansion_state(self) -> dict[str, bool]:
        state: dict[str, bool] = {}

        def walk(item: QTreeWidgetItem):
            if sip.isdeleted(item):
                return
            key = item.data(0, _OUTLINE_ENTRY_KEY_ROLE)
            if key:
                state[str(key)] = item.isExpanded()
            for idx in range(item.childCount()):
                child = item.child(idx)
                if not sip.isdeleted(child):
                    walk(child)

        for idx in range(self.flags_list.topLevelItemCount()):
            item = self.flags_list.topLevelItem(idx)
            if not sip.isdeleted(item):
                walk(item)
        return state

    def _set_outline_expansion_signals_suspended(self, suspended: bool):
        self._outline_expansion_signal_suspended += 1 if suspended else -1
        self._outline_expansion_signal_suspended = max(0, self._outline_expansion_signal_suspended)

    def _on_outline_item_expanded(self, item: QTreeWidgetItem):
        if self._outline_expansion_signal_suspended:
            return
        key = self._outline_item_data(item, _OUTLINE_ENTRY_KEY_ROLE)
        if key:
            self._outline_expansion_overrides[str(key)] = True

    def _on_outline_item_collapsed(self, item: QTreeWidgetItem):
        if self._outline_expansion_signal_suspended:
            return
        key = self._outline_item_data(item, _OUTLINE_ENTRY_KEY_ROLE)
        if key:
            self._outline_expansion_overrides[str(key)] = False
            self._outline_reveal_keys.clear()

    def _restore_outline_expansion_state(self, state: dict[str, bool]):
        def walk(item: QTreeWidgetItem):
            if sip.isdeleted(item):
                return
            key = item.data(0, _OUTLINE_ENTRY_KEY_ROLE)
            key_text = str(key) if key else ""
            if key_text in self._outline_expansion_overrides:
                item.setExpanded(self._outline_expansion_overrides[key_text])
            elif key_text in state:
                item.setExpanded(state[key_text])
            elif (
                item.parent() is None
                and not item.text(0).startswith("Unmarked:")
                and key_text != "ignored-group"
            ):
                item.setExpanded(True)
            for idx in range(item.childCount()):
                child = item.child(idx)
                if not sip.isdeleted(child):
                    walk(child)

        for idx in range(self.flags_list.topLevelItemCount()):
            item = self.flags_list.topLevelItem(idx)
            if not sip.isdeleted(item):
                walk(item)

    def _collect_outline_selection_state(self) -> dict[str, object]:
        selected_keys = []
        for item in self.flags_list.selectedItems():
            key = self._outline_selection_key(item)
            if key:
                selected_keys.append(str(key))
        current_key = self._outline_selection_key(self.flags_list.currentItem())
        anchor_key = self._outline_selection_key(self.flags_list._selection_anchor_item)
        return {
            "selected": selected_keys,
            "current": str(current_key) if current_key else "",
            "anchor": str(anchor_key) if anchor_key else "",
        }

    def _restore_outline_selection_state(self, state: dict[str, object]):
        selected_keys = {str(key) for key in state.get("selected", []) if key}
        current_key = str(state.get("current") or "")
        anchor_key = str(state.get("anchor") or "")
        if not selected_keys and not current_key and not anchor_key:
            return

        items_by_key: dict[str, QTreeWidgetItem] = {}

        def walk(item: QTreeWidgetItem):
            if sip.isdeleted(item):
                return
            key = self._outline_selection_key(item)
            if key:
                items_by_key[str(key)] = item
            for idx in range(item.childCount()):
                child = item.child(idx)
                if not sip.isdeleted(child):
                    walk(child)

        for idx in range(self.flags_list.topLevelItemCount()):
            item = self.flags_list.topLevelItem(idx)
            if not sip.isdeleted(item):
                walk(item)

        self.flags_list.clearSelection()
        for key in selected_keys:
            item = items_by_key.get(key)
            if item is not None:
                item.setSelected(True)
        current_item = items_by_key.get(current_key)
        if current_item is not None:
            self.flags_list._set_current_without_selection_change(current_item)
        self.flags_list._selection_anchor_item = items_by_key.get(anchor_key)

    def _expand_outline_all(self):
        self.flags_list.expandAll()

    def _collapse_outline_all(self):
        self.flags_list.collapseAll()

    def _on_outline_search_changed(self, text: str):
        query = str(text or "").strip()
        if query and self._outline_search_expansion_state is None:
            self._outline_search_expansion_state = self._collect_outline_expansion_state()
        self._apply_outline_tree_filter(query)
        if not query and self._outline_search_expansion_state is not None:
            state = self._outline_search_expansion_state
            self._outline_search_expansion_state = None
            self._restore_outline_search_expansion_state(state)

    def _apply_outline_tree_filter(self, query: str | None = None):
        if query is None:
            query = self.outline_search_edit.text()
        needle = str(query or "").strip().casefold()

        def filter_item(item: QTreeWidgetItem, ancestor_matches: bool = False) -> bool:
            own_match = bool(needle) and needle in item.text(0).casefold()
            child_visible = False
            for index in range(item.childCount()):
                child_visible = filter_item(
                    item.child(index), ancestor_matches or own_match
                ) or child_visible
            visible = not needle or ancestor_matches or own_match or child_visible
            item.setHidden(not visible)
            if needle and visible and (own_match or child_visible):
                item.setExpanded(True)
            return visible

        self._set_outline_expansion_signals_suspended(True)
        try:
            for index in range(self.flags_list.topLevelItemCount()):
                filter_item(self.flags_list.topLevelItem(index))
        finally:
            self._set_outline_expansion_signals_suspended(False)

    def _restore_outline_search_expansion_state(self, state: dict[str, bool]):
        def walk(item: QTreeWidgetItem):
            key = self._outline_item_data(item, _OUTLINE_ENTRY_KEY_ROLE)
            if key is not None and str(key) in state:
                item.setExpanded(bool(state[str(key)]))
            for index in range(item.childCount()):
                walk(item.child(index))

        self._set_outline_expansion_signals_suspended(True)
        try:
            for index in range(self.flags_list.topLevelItemCount()):
                walk(self.flags_list.topLevelItem(index))
        finally:
            self._set_outline_expansion_signals_suspended(False)

    def _queue_outline_reveal(self, *keys: str | None):
        for key in keys:
            if key:
                self._outline_reveal_keys.add(str(key))

    def _reveal_queued_outline_items(self):
        if not self._outline_reveal_keys:
            return
        matched_item = None

        def walk(item: QTreeWidgetItem):
            nonlocal matched_item
            if sip.isdeleted(item):
                return
            key = item.data(0, _OUTLINE_ENTRY_KEY_ROLE)
            if key in self._outline_reveal_keys:
                matched_item = item
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
                item.setExpanded(True)
            for idx in range(item.childCount()):
                child = item.child(idx)
                if not sip.isdeleted(child):
                    walk(child)

        for idx in range(self.flags_list.topLevelItemCount()):
            item = self.flags_list.topLevelItem(idx)
            if not sip.isdeleted(item):
                walk(item)
        if matched_item is not None:
            self.flags_list._set_current_without_selection_change(matched_item)
            self.flags_list.scrollToItem(matched_item)
        self._outline_reveal_keys.clear()

    def _make_tree_item(
        self,
        depth: int,
        type_id: str,
        text: str,
        line_no: int,
        entry_key: str,
        mark_key: str | None = None,
    ) -> QTreeWidgetItem:
        type_def = self.hierarchy_type_definitions.get(type_id)
        label = type_def.label if type_def else str(type_id).title()
        prefix = f"[{depth}] " if type_id not in (HierarchyType.UNMARKED, HierarchyType.IGNORE) else ""
        mark = self._hierarchy_mark_for_key(mark_key) if mark_key else None
        if mark is not None and mark.origin not in {"manual", _ASSIGNED_SPEAKER_ORIGIN}:
            source = "AI" if mark.origin == "ai" else "Auto"
            prefix = f"[{source}] {prefix}"
        item = QTreeWidgetItem([f"{prefix}{label}: {text}".rstrip()])
        item.setData(0, _OUTLINE_LINE_ROLE, line_no)
        item.setData(0, _OUTLINE_ENTRY_KEY_ROLE, entry_key)
        if mark_key:
            item.setData(0, _OUTLINE_MARK_KEY_ROLE, mark_key)
        color = type_def.color if type_def else "#ffffff"
        item.setBackground(0, QColor(color))
        return item

    def _hierarchy_outline_signature_for_entries(
        self,
        entries: list[dict[str, object]],
        unmarked_ranges: list[tuple[int, int]],
        grouped_unmarked_previews: tuple[tuple[int, int, str], ...],
    ) -> tuple:
        type_defs = tuple(
            sorted(
                (
                    type_id,
                    definition.label,
                    definition.color,
                )
                for type_id, definition in self.hierarchy_type_definitions.items()
            )
        )
        entry_signature = tuple(
            (
                int(entry["start"]),
                int(entry["end"]),
                int(entry["depth"]),
                str(entry["type_id"]),
                str(entry["text"]),
                int(entry["order"]),
                str(entry["entry_key"]),
                str(entry["mark_key"]),
            )
            for entry in entries
        )
        return (
            self.mode,
            type_defs,
            entry_signature,
            tuple(unmarked_ranges),
            grouped_unmarked_previews,
            self._has_unmarked_hierarchy_lines,
        )

    def _fill_hierarchy_outline(
        self,
        raw_lines: list[str] | None = None,
        unmarked_ranges: list[tuple[int, int]] | None = None,
    ):
        raw_lines = raw_lines if raw_lines is not None else self.raw_edit.toPlainText().splitlines()
        unmarked_ranges = unmarked_ranges if unmarked_ranges is not None else self._unmarked_ranges(raw_lines)
        entries: list[dict[str, object]] = []
        for mark in sorted(self.hierarchy_marks, key=lambda m: (m.start_line, m.depth, -m.end_line, m.order)):
            mark_key = self._hierarchy_mark_key(mark)
            text = self._hierarchy_mark_display_text(mark, raw_lines=raw_lines)
            entries.append({
                "start": mark.start_line,
                "end": mark.end_line,
                "depth": 0 if mark.type_id == HierarchyType.IGNORE else mark.depth,
                "type_id": mark.type_id,
                "text": text,
                "order": mark.order,
                "entry_key": mark_key,
                "mark_key": mark_key,
            })
        if len(unmarked_ranges) <= _UNMARKED_GROUP_THRESHOLD:
            for start, end in unmarked_ranges:
                entries.append({
                    "start": start,
                    "end": end,
                    "depth": 0,
                    "type_id": HierarchyType.UNMARKED,
                    "text": self._short_source_text(start, end, raw_lines=raw_lines),
                    "order": -1,
                    "entry_key": f"unmarked:{start}:{end}",
                    "mark_key": "",
                })

        entries.sort(
            key=lambda e: (
                int(e["start"]),
                int(e["depth"]),
                -int(e["end"]),
                int(e["order"]),
            )
        )
        grouped_unmarked_previews = (
            tuple(
                (
                    start,
                    end,
                    self._short_source_text(start, end, raw_lines=raw_lines),
                )
                for start, end in unmarked_ranges[:_MAX_UNMARKED_TREE_CHILDREN]
            )
            if len(unmarked_ranges) > _UNMARKED_GROUP_THRESHOLD
            else ()
        )
        signature = self._hierarchy_outline_signature_for_entries(
            entries,
            unmarked_ranges,
            grouped_unmarked_previews,
        )
        reveal_requested = bool(self._outline_reveal_keys)
        if (
            not reveal_requested
            and self.flags_list.topLevelItemCount() > 0
            and self._hierarchy_outline_signature == signature
        ):
            return

        expansion_state = self._collect_outline_expansion_state()
        selection_state = self._collect_outline_selection_state()
        vertical_scroll = self.flags_list.verticalScrollBar().value()
        horizontal_scroll = self.flags_list.horizontalScrollBar().value()
        self.flags_list.setUpdatesEnabled(False)
        self.flags_list._selection_anchor_item = None
        self.flags_list.clear()

        try:
            stack: list[tuple[int, QTreeWidgetItem]] = []
            ignore_entries = [
                entry for entry in entries
                if str(entry["type_id"]) == HierarchyType.IGNORE
            ]
            for entry in entries:
                type_id = str(entry["type_id"])
                if type_id == HierarchyType.IGNORE:
                    continue
                depth = int(entry["depth"])
                item = self._make_tree_item(
                    depth,
                    type_id,
                    str(entry["text"]),
                    int(entry["start"]) + 1,
                    str(entry["entry_key"]),
                    str(entry["mark_key"]) or None,
                )
                if type_id == HierarchyType.UNMARKED:
                    self.flags_list.addTopLevelItem(item)
                    continue

                while stack and stack[-1][0] >= depth:
                    stack.pop()
                if stack:
                    stack[-1][1].addChild(item)
                else:
                    self.flags_list.addTopLevelItem(item)
                stack.append((depth, item))

            if ignore_entries:
                ignored_def = self.hierarchy_type_definitions[HierarchyType.IGNORE]
                ignored_line_count = sum(
                    int(entry["end"]) - int(entry["start"]) + 1
                    for entry in ignore_entries
                )
                range_count = len(ignore_entries)
                ignored_root = QTreeWidgetItem([
                    f"Ignored: {ignored_line_count} lines in {range_count} "
                    f"{'range' if range_count == 1 else 'ranges'}"
                ])
                ignored_root.setData(0, _OUTLINE_ENTRY_KEY_ROLE, "ignored-group")
                ignored_root.setData(
                    0,
                    _OUTLINE_LINE_ROLE,
                    min(int(entry["start"]) for entry in ignore_entries) + 1,
                )
                ignored_root.setBackground(0, QColor(ignored_def.color))
                first_ignored_line = min(
                    int(entry["start"]) for entry in ignore_entries
                ) + 1
                insert_at = self.flags_list.topLevelItemCount()
                for top_index in range(self.flags_list.topLevelItemCount()):
                    top_line = self._outline_item_data(
                        self.flags_list.topLevelItem(top_index),
                        _OUTLINE_LINE_ROLE,
                    )
                    if top_line is not None and int(top_line) > first_ignored_line:
                        insert_at = top_index
                        break
                self.flags_list.insertTopLevelItem(insert_at, ignored_root)

                shown = 0
                for entry in ignore_entries:
                    mark_key = str(entry["mark_key"])
                    for line_index in range(int(entry["start"]), int(entry["end"]) + 1):
                        if shown >= _MAX_IGNORED_TREE_CHILDREN:
                            break
                        source = raw_lines[line_index].strip() or "(blank line)"
                        child = QTreeWidgetItem([f"Line {line_index + 1}: {source}"])
                        child.setData(0, _OUTLINE_LINE_ROLE, line_index + 1)
                        child.setData(
                            0,
                            _OUTLINE_ENTRY_KEY_ROLE,
                            f"ignored-line:{line_index}:{mark_key}",
                        )
                        child.setData(0, _OUTLINE_MARK_KEY_ROLE, mark_key)
                        child.setBackground(0, QColor(ignored_def.color))
                        ignored_root.addChild(child)
                        shown += 1
                    if shown >= _MAX_IGNORED_TREE_CHILDREN:
                        break
                hidden_count = ignored_line_count - shown
                if hidden_count > 0:
                    more = QTreeWidgetItem([
                        f"{hidden_count} more ignored lines hidden for speed"
                    ])
                    more.setData(0, _OUTLINE_ENTRY_KEY_ROLE, "ignored-more")
                    more.setBackground(0, QColor(ignored_def.color))
                    ignored_root.addChild(more)

            if len(unmarked_ranges) > _UNMARKED_GROUP_THRESHOLD:
                unmarked_def = self.hierarchy_type_definitions[HierarchyType.UNMARKED]
                root_text = f"Unmarked: {len(unmarked_ranges)} ranges"
                unmarked_root = QTreeWidgetItem([root_text])
                unmarked_root.setData(0, _OUTLINE_ENTRY_KEY_ROLE, "unmarked-group")
                unmarked_root.setBackground(0, QColor(unmarked_def.color))
                self.flags_list.addTopLevelItem(unmarked_root)
                for start, end in unmarked_ranges[:_MAX_UNMARKED_TREE_CHILDREN]:
                    child = self._make_tree_item(
                        0,
                        HierarchyType.UNMARKED,
                        self._short_source_text(start, end, raw_lines=raw_lines),
                        start + 1,
                        f"unmarked:{start}:{end}",
                    )
                    unmarked_root.addChild(child)
                hidden_count = len(unmarked_ranges) - _MAX_UNMARKED_TREE_CHILDREN
                if hidden_count > 0:
                    more = QTreeWidgetItem([f"{hidden_count} more unmarked ranges hidden for speed"])
                    more.setData(0, _OUTLINE_ENTRY_KEY_ROLE, "unmarked-more")
                    more.setBackground(0, QColor(unmarked_def.color))
                    unmarked_root.addChild(more)

            self._set_outline_expansion_signals_suspended(True)
            try:
                self._restore_outline_expansion_state(expansion_state)
            finally:
                self._set_outline_expansion_signals_suspended(False)
            self._restore_outline_selection_state(selection_state)
            self._set_outline_expansion_signals_suspended(True)
            try:
                self._reveal_queued_outline_items()
            finally:
                self._set_outline_expansion_signals_suspended(False)
        finally:
            self.flags_list.setUpdatesEnabled(True)
            if not reveal_requested:
                self.flags_list.verticalScrollBar().setValue(
                    min(vertical_scroll, self.flags_list.verticalScrollBar().maximum())
                )
                self.flags_list.horizontalScrollBar().setValue(
                    min(horizontal_scroll, self.flags_list.horizontalScrollBar().maximum())
                )
        if self.outline_search_edit.text().strip():
            self._apply_outline_tree_filter()
        self._hierarchy_outline_signature = signature

    def _refresh_custom(self):
        self._reset_raw_hierarchy_view()
        text = self.raw_edit.toPlainText()
        result = convert(text, self.recipe, start_line=self.start_line, end_line=self.end_line)
        raw_lines = text.splitlines()
        self._apply_manual_marks_to_classified(result.classified, raw_lines)
        self._psm_text = render_psm(result.classified, self.recipe)

        line_kinds, line_speakers = self._line_maps_from_classified(result.classified)
        self.highlighter.set_line_kinds(
            line_kinds,
            self._block_parity(line_speakers),
            line_speakers,
        )
        self._update_raw_minimap()

        speakers, s = self._classified_summary(result.classified)
        self.stats_label.setText(
            f"Speakers: {len(speakers)} | "
            f"Dialogue: {s.get(LineKind.SPEAKER, 0) + s.get(LineKind.GUTTER_SPEAKER, 0)} | "
            f"Chapters: {s.get(LineKind.CHAPTER, 0)} | "
            f"Locations: {s.get(LineKind.LOCATION, 0)} | "
            f"Flags: {len(result.flags)}"
        )
        self._fill_flags(result.flags)

    def _refresh_picoripi(self):
        self._reset_raw_hierarchy_view()
        full_text = self.raw_edit.toPlainText()
        sliced, offset = self._sliced_text(full_text)
        rules = self._resolve_game_rules()
        parse_text = self._apply_manual_marks_to_parse_text(sliced, base_offset=offset)
        transcript = parse_with_rules(rules, parse_text)
        self._psm_text = transcript_to_psm(transcript)

        raw_lines = full_text.splitlines()
        ann = annotate_source_lines(raw_lines[offset:], transcript)
        line_kinds = {}
        line_speakers = {}
        for rel_i, (kind, speaker) in ann.items():
            idx = rel_i + offset
            line_kinds[idx] = kind
            if speaker:
                line_speakers[idx] = speaker
        for i in range(len(raw_lines)):
            if (self.start_line and i + 1 < self.start_line) or (self.end_line and i + 1 > self.end_line):
                line_kinds[i] = LineKind.IGNORE
                line_speakers.pop(i, None)
        self._overlay_manual_marks_on_lines(line_kinds, line_speakers, raw_lines)
        self.highlighter.set_line_kinds(
            line_kinds,
            self._block_parity(line_speakers),
            line_speakers,
        )
        self._update_raw_minimap()

        speakers, stats = summarize_transcript(transcript)
        self.stats_label.setText(
            f"Speakers: {len(speakers)} | "
            f"Dialogue: {stats.get(LineKind.SPEAKER, 0)} | "
            f"Chapters/Rooms: {stats.get(LineKind.CHAPTER, 0)} | "
            f"Actions: {stats.get(LineKind.ACTION, 0)} | "
            f"(via Picoripi rules)"
        )
        self._fill_flags([])

    def _block_parity(self, line_speakers: dict) -> dict:
        """Assign an alternating 0/1 to each speech line so consecutive lines of
        one speaker share a tint and the tint flips when the speaker changes."""
        parity = {}
        prev_speaker = None
        cur = 0
        for idx in sorted(line_speakers):
            spk = line_speakers[idx]
            if spk != prev_speaker:
                cur ^= 1
                prev_speaker = spk
            parity[idx] = cur
        return parity

    def _fill_flags(self, flags):
        self.flags_list.clear()
        for line_no, reason in flags:
            item = QTreeWidgetItem([f"Line {line_no}: {reason}"])
            item.setData(0, _OUTLINE_LINE_ROLE, line_no)
            item.setData(0, _OUTLINE_ENTRY_KEY_ROLE, f"flag:{line_no}:{reason}")
            self.flags_list.addTopLevelItem(item)
        if self.outline_search_edit.text().strip():
            self._apply_outline_tree_filter()
