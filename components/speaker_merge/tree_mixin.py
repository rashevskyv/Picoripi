from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QMenu, QTreeWidgetItem

from core.speaker_alias_merge import NAME_SEPARATOR, is_applyable_speaker_alias
from core.i18n import tr

from components.speaker_merge.widgets import (
    _CODE_ROLE,
    _DISPLAY_ROLE,
    _STRONG_COLOR,
    _SHARED_COLOR,
    _WEAK_COLOR,
    _UNMATCHED_COLOR,
    _DISPLAY_COLOR,
    _votes_line,
    _top_name,
    extract_candidates,
    describe_code,
)


class TreeMixin:
    """Populate tree, groups, filter, and check helpers."""

    def _populate(self) -> None:
        resolved = getattr(self._result, "resolved", {}) or {}
        unproven = getattr(self._result, "unproven", {}) or {}
        all_placeholders = getattr(self._result, "all_placeholders", []) or []
        game_display_names = getattr(self._result, "game_display_names", []) or []
        is_markup = bool(getattr(self._result, "is_markup", False))

        strong_matches = []
        shared_matches = []
        applied = getattr(self._result, "applied", {}) or {}
        for code, name in sorted(resolved.items()):
            votes_str = _votes_line(unproven.get(code) or self._votes_for(code))
            preexisting = code in applied or not (
                self._result.evidence.get(code) or unproven.get(code)
            )
            if NAME_SEPARATOR in name:
                if preexisting:
                    source = f"{votes_str} • Already applied" if votes_str else "Already applied"
                else:
                    source = f"{votes_str} • Shared voice" if votes_str else "Shared voice"
                shared_matches.append((code, name, source))
            else:
                source_tag = "Markup Studio match" if is_markup else "Script match"
                if preexisting:
                    source = f"{votes_str} • Already applied" if votes_str else "Already applied"
                else:
                    source = f"{votes_str} • {source_tag}" if votes_str else source_tag
                strong_matches.append((code, name, source))

        suggested = []
        for code, counter in sorted(unproven.items()):
            if code in resolved:
                continue
            votes = self._result.evidence.get(code) or []
            is_glossary = any("glossary description" in getattr(v, "text", "") for v in votes)
            is_block = any("block name" in getattr(v, "text", "").lower() for v in votes)
            top = _top_name(counter)
            if is_glossary:
                source = "Glossary suggestion"
            elif is_block:
                source = "Block name suggestion"
            else:
                votes_str = _votes_line(counter)
                source = f"{votes_str} • Weak match" if votes_str else "Weak match"
            suggested.append((code, top, source))

        known_codes = set(resolved.keys()) | set(unproven.keys())
        unmatched = [
            (code, "", "No script match")
            for code in sorted(all_placeholders)
            if code not in known_codes
        ]

        display_items = [
            (name, name, "Provided by game data")
            for name in sorted(game_display_names)
        ]

        strong_label = (
            f"Strong Markup Studio matches ({len(strong_matches)})"
            if is_markup
            else f"Strong script matches ({len(strong_matches)})"
        )
        self._add_group(strong_label, strong_matches, _STRONG_COLOR)
        self._add_group(
            f"Shared / conflicting matches ({len(shared_matches)})",
            shared_matches,
            _SHARED_COLOR,
        )
        self._add_group(
            f"Weak or AI suggestions ({len(suggested)})", suggested, _WEAK_COLOR
        )
        self._add_group(
            f"Unmatched manual rows ({len(unmatched)})", unmatched, _UNMATCHED_COLOR
        )
        self._add_group(
            f"Game data display names ({len(display_items)})",
            display_items,
            _DISPLAY_COLOR,
            is_editable=False,
            is_display_name=True,
        )

    def _votes_for(self, code: str) -> dict:
        counter: dict = {}
        for vote in self._result.evidence.get(code) or ():
            counter[vote.speaker] = counter.get(vote.speaker, 0) + 1
        return counter

    def _add_group(
        self,
        title: str,
        rows,
        color: QColor,
        is_editable: bool = True,
        is_display_name: bool = False,
    ) -> None:
        if not rows:
            return
        group = QTreeWidgetItem(self.tree, [title, "", ""])
        font = group.font(0)
        font.setBold(True)
        group.setFont(0, font)

        if not is_display_name:
            group.setFlags(group.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            group.setCheckState(0, Qt.CheckState.Checked)

        brush = QBrush(color)
        for code, name, votes in rows:
            child = QTreeWidgetItem(group, [code, name, votes])
            child.setData(0, _CODE_ROLE, code)
            if is_display_name:
                child.setData(0, _DISPLAY_ROLE, True)
                child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            else:
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                if is_applyable_speaker_alias(name):
                    child.setCheckState(0, Qt.CheckState.Checked)
                else:
                    child.setCheckState(0, Qt.CheckState.Unchecked)

            if is_editable:
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsEditable)
            else:
                child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsEditable)
            for col in range(3):
                child.setForeground(col, brush)
        group.setExpanded(True)

    def _select_first(self) -> None:
        top = self.tree.topLevelItem(0)
        if top is not None and top.childCount():
            self.tree.setCurrentItem(top.child(0))
        elif (
            not self._result.evidence
            and not getattr(self._result, "all_placeholders", None)
            and not getattr(self._result, "game_display_names", None)
        ):
            self.details.setPlainText("Nothing was matched, so there is nothing to show.")
            self._update_inspector(None)

    def _on_selection(self, current, _previous=None) -> None:
        code = current.data(0, _CODE_ROLE) if current is not None else None
        self.details.setPlainText(describe_code(self._result, code) if code else "")
        self._update_inspector(current)

    def _filter_tree(self, query: str) -> None:
        query = (query or "").strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            group_match = not query or query in group.text(0).lower()
            visible_children = 0
            for j in range(group.childCount()):
                child = group.child(j)
                child_match = (
                    not query
                    or query in child.text(0).lower()
                    or query in child.text(1).lower()
                    or query in child.text(2).lower()
                )
                child.setHidden(not child_match)
                if child_match:
                    visible_children += 1
            group.setHidden(visible_children == 0 and not group_match)

    def _check_all(self) -> None:
        self._updating_checks = True
        try:
            for i in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(i)
                if not group.isHidden():
                    for j in range(group.childCount()):
                        child = group.child(j)
                        if not child.data(0, _DISPLAY_ROLE) and not child.isHidden():
                            child.setCheckState(0, Qt.CheckState.Checked)
                    group.setCheckState(0, Qt.CheckState.Checked)
        finally:
            self._updating_checks = False
        self._update_counts_and_buttons()

    def _uncheck_all(self) -> None:
        self._updating_checks = True
        try:
            for i in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(i)
                for j in range(group.childCount()):
                    child = group.child(j)
                    if not child.data(0, _DISPLAY_ROLE):
                        child.setCheckState(0, Qt.CheckState.Unchecked)
                group.setCheckState(0, Qt.CheckState.Unchecked)
        finally:
            self._updating_checks = False
        self._update_counts_and_buttons()

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating_checks:
            return
        self._updating_checks = True
        try:
            if column == 0:
                if item.childCount() > 0:
                    state = item.checkState(0)
                    if state != Qt.CheckState.PartiallyChecked:
                        for i in range(item.childCount()):
                            child = item.child(i)
                            if not child.data(0, _DISPLAY_ROLE):
                                child.setCheckState(0, state)
                else:
                    parent = item.parent()
                    if parent:
                        child_states = [
                            parent.child(i).checkState(0)
                            for i in range(parent.childCount())
                            if not parent.child(i).data(0, _DISPLAY_ROLE)
                        ]
                        if child_states:
                            if all(s == Qt.CheckState.Checked for s in child_states):
                                parent.setCheckState(0, Qt.CheckState.Checked)
                            elif all(s == Qt.CheckState.Unchecked for s in child_states):
                                parent.setCheckState(0, Qt.CheckState.Unchecked)
                            else:
                                parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
            elif column == 1:
                text = item.text(1).strip()
                if text and item.checkState(0) == Qt.CheckState.Unchecked:
                    item.setCheckState(0, Qt.CheckState.Checked)
                if item == self.tree.currentItem():
                    self.name_edit.blockSignals(True)
                    self.name_edit.setText(item.text(1))
                    self.name_edit.blockSignals(False)
                    self.apply_single_button.setEnabled(
                        self._on_apply is not None and is_applyable_speaker_alias(text)
                    )
                    self.reset_button.setEnabled(bool(self._default_name(item.data(0, _CODE_ROLE))))
                    self._update_candidate_buttons_style(item.text(1))
        finally:
            self._updating_checks = False
        self._update_counts_and_buttons()

    def _update_counts_and_buttons(self) -> None:
        checked_names = self.chosen_names(only_checked=True)
        all_names = self.chosen_names(only_checked=False)
        checked_count = len(checked_names)
        all_count = len(all_names)

        self.status_label.setText(
            f"Checked to apply: {checked_count} of {all_count} speaker(s) with names"
        )
        self.apply_button.setText(f"Apply Checked ({checked_count})")
        self.apply_button.setEnabled(self._on_apply is not None and checked_count > 0)

        self.apply_all_button.setText(f"Apply All Valid ({all_count})")
        self.apply_all_button.setEnabled(self._on_apply is not None and all_count > 0)

    def _show_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if not item:
            return
        self.tree.setCurrentItem(item)
        code = item.data(0, _CODE_ROLE)
        is_display = bool(item.data(0, _DISPLAY_ROLE))

        menu = QMenu(self)
        if code and not is_display:
            candidates = extract_candidates(self._result, code)
            if candidates:
                for cand_name, _ in candidates:
                    menu.addAction(
                        f'Use "{cand_name}"',
                        lambda c=cand_name: self._set_current_name(c),
                    )
                menu.addSeparator()

            name = item.text(1).strip()
            apply_action = menu.addAction(
                f"Apply '{code}' Now", self._apply_current_speaker
            )
            apply_action.setEnabled(
                self._on_apply is not None and is_applyable_speaker_alias(name)
            )

            is_checked = item.checkState(0) == Qt.CheckState.Checked
            menu.addAction(
                "Uncheck" if is_checked else "Check",
                lambda: item.setCheckState(
                    0, Qt.CheckState.Unchecked if is_checked else Qt.CheckState.Checked
                ),
            )
            reset_action = menu.addAction(tr('Clear (restore suggestion)'), self._reset_current_name)
            reset_action.setEnabled(bool(self._default_name(code)))
            menu.addSeparator()

        parent = item.parent() or item
        if parent.childCount() > 0:
            menu.addAction(
                tr('Check All in Group'),
                lambda p=parent: self._toggle_group_checks(p, Qt.CheckState.Checked),
            )
            menu.addAction(
                tr('Uncheck All in Group'),
                lambda p=parent: self._toggle_group_checks(p, Qt.CheckState.Unchecked),
            )

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _toggle_group_checks(self, group: QTreeWidgetItem, state: Qt.CheckState) -> None:
        self._updating_checks = True
        try:
            for i in range(group.childCount()):
                child = group.child(i)
                if not child.data(0, _DISPLAY_ROLE):
                    child.setCheckState(0, state)
            group.setCheckState(0, state)
        finally:
            self._updating_checks = False
        self._update_counts_and_buttons()
