from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QPushButton, QTreeWidgetItem, QTreeWidgetItemIterator

from core.speaker_alias_merge import (
    NAME_SEPARATOR,
    is_applyable_speaker_alias,
    split_shared_speaker_names,
)
from core.i18n import tr

from components.speaker_merge.widgets import (
    _CODE_ROLE,
    _DISPLAY_ROLE,
    _APPLIED_NAME_ROLE,
    _STRONG_COLOR,
    _SHARED_COLOR,
    _top_name,
    extract_candidates,
)


class InspectorMixin:
    """Inspector, name editing, and apply actions."""

    def chosen_names(self, only_checked: bool = True) -> dict:
        """``{code: name}`` as the tree now reads, blanks left out."""
        names = {}
        walker = QTreeWidgetItemIterator(self.tree)
        while walker.value():
            item = walker.value()
            code = item.data(0, _CODE_ROLE)
            is_display = bool(item.data(0, _DISPLAY_ROLE))
            name = item.text(1).strip()
            if code and is_applyable_speaker_alias(name) and not is_display:
                if not only_checked or item.checkState(0) == Qt.CheckState.Checked:
                    names[code] = name
            walker += 1
        return names

    def _update_inspector(self, item: Optional[QTreeWidgetItem]) -> None:
        while self.candidates_layout.count():
            w_item = self.candidates_layout.takeAt(0)
            widget = w_item.widget()
            if widget:
                widget.deleteLater()
        self._candidate_buttons.clear()

        if item is None:
            self.inspector_title.setText(tr('Select a speaker'))
            self.inspector_badge.setText("")
            self.name_edit.setEnabled(False)
            self.name_edit.setText("")
            self.reset_button.setEnabled(False)
            self.apply_single_button.setEnabled(False)
            self.candidates_widget.setVisible(False)
            self.feedback_label.setText("")
            return

        code = item.data(0, _CODE_ROLE)
        is_display = bool(item.data(0, _DISPLAY_ROLE))
        name = item.text(1).strip()

        if is_display or not code:
            self.inspector_title.setText(f"Display Name: {code or item.text(0)}")
            self.inspector_badge.setText(tr('Game Data (Read-only)'))
            self.inspector_badge.setStyleSheet("color: #00695c; font-weight: bold;")
            self.name_edit.setEnabled(False)
            self.name_edit.setText(name)
            self.reset_button.setEnabled(False)
            self.apply_single_button.setEnabled(False)
            self.candidates_widget.setVisible(False)
            self.feedback_label.setText("")
            return

        parent = item.parent()
        group_title = parent.text(0) if parent else ""
        self.inspector_title.setText(f"Voice Code: {code}")

        if item.data(0, _APPLIED_NAME_ROLE) == name:
            self.inspector_badge.setText(tr('Applied'))
            self.inspector_badge.setStyleSheet("color: #2e7d32; font-weight: bold;")
        elif "Shared" in group_title:
            self.inspector_badge.setText(tr('Shared Voice / Multiple Candidates'))
            self.inspector_badge.setStyleSheet("color: #e65100; font-weight: bold;")
        elif "Weak" in group_title:
            self.inspector_badge.setText(tr('Weak / AI Suggestion'))
            self.inspector_badge.setStyleSheet("color: #1565c0; font-weight: bold;")
        elif "Strong" in group_title:
            self.inspector_badge.setText(tr('Strong Match'))
            self.inspector_badge.setStyleSheet("color: #2e7d32; font-weight: bold;")
        else:
            self.inspector_badge.setText(tr('Unmatched Placeholder'))
            self.inspector_badge.setStyleSheet("color: #6a1b9a; font-weight: bold;")

        self.name_edit.setEnabled(True)
        self.name_edit.blockSignals(True)
        self.name_edit.setText(name)
        self.name_edit.blockSignals(False)
        self.apply_single_button.setEnabled(
            self._on_apply is not None and is_applyable_speaker_alias(name)
        )
        self.reset_button.setEnabled(bool(self._default_name(code)))
        self.feedback_label.setText("")

        candidates = extract_candidates(self._result, code)
        if candidates:
            self.candidates_widget.setVisible(True)
            for cand_name, vote_count in candidates:
                label = f"{cand_name} ({vote_count})" if vote_count > 1 else cand_name
                btn = QPushButton(label, self.candidates_widget)
                btn.setProperty("candidate_name", cand_name)
                btn.setToolTip(
                    f"Toggle '{cand_name}' on this shared voice. "
                    "Several names can stay assigned at once."
                )
                btn.clicked.connect(lambda _, n=cand_name: self._toggle_candidate(n))
                self.candidates_layout.addWidget(btn)
                self._candidate_buttons.append(btn)

            if len(candidates) > 1:
                all_names = NAME_SEPARATOR.join(c[0] for c in candidates)
                btn_all = QPushButton(tr('All candidates'), self.candidates_widget)
                btn_all.setProperty("candidate_name", all_names)
                btn_all.setToolTip(tr('Keep every candidate on this shared voice'))
                btn_all.clicked.connect(lambda: self._set_current_name(all_names))
                self.candidates_layout.addWidget(btn_all)
                self._candidate_buttons.append(btn_all)

            btn_clear = QPushButton(tr('Clear'), self.candidates_widget)
            btn_clear.setProperty("candidate_name", "__reset__")
            btn_clear.setToolTip(
                tr('Restore the suggested name. Delete the text to leave this voice unnamed.')
            )
            btn_clear.clicked.connect(self._reset_current_name)
            self.candidates_layout.addWidget(btn_clear)
            self._candidate_buttons.append(btn_clear)

            self._update_candidate_buttons_style(name)
        else:
            self.candidates_widget.setVisible(False)

    def _default_name(self, code: str) -> str:
        """The name the join proposed, which Clear restores."""
        proposed = getattr(self._result, "proposed", None) or {}
        text = str(proposed.get(code) or "").strip()
        if text:
            return text
        resolved = str((self._result.resolved or {}).get(code) or "").strip()
        if resolved:
            return resolved
        return _top_name((self._result.unproven or {}).get(code) or {})

    def _reset_current_name(self) -> None:
        current = self.tree.currentItem()
        if not current:
            return
        code = current.data(0, _CODE_ROLE)
        if not code:
            return
        self._set_current_name(self._default_name(code))
        current = self.tree.currentItem()
        if current is None:
            return
        name = current.text(1).strip()
        if current.data(0, _APPLIED_NAME_ROLE) == name:
            self._paint_item(current, _STRONG_COLOR)
            if NAME_SEPARATOR not in name:
                self._move_item_to_group(current, "Strong")
        elif NAME_SEPARATOR in name:
            self._move_item_to_group(current, "Shared")
            self._paint_item(current, _SHARED_COLOR)

    def _paint_item(self, item: QTreeWidgetItem, color: QColor) -> None:
        brush = QBrush(color)
        for col in range(3):
            item.setForeground(col, brush)

    def _find_group(self, prefix: str) -> Optional[QTreeWidgetItem]:
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group.text(0).startswith(prefix):
                return group
        return None

    def _refresh_group_title(self, group: Optional[QTreeWidgetItem]) -> None:
        if group is None:
            return
        title = group.text(0)
        base = title.rsplit(" (", 1)[0] if " (" in title else title
        count = group.childCount()
        group.setText(0, f"{base} ({count})")
        group.setHidden(count == 0)

    def _move_item_to_group(self, item: QTreeWidgetItem, prefix: str) -> None:
        parent = item.parent()
        if parent is not None and parent.text(0).startswith(prefix):
            return
        target = self._find_group(prefix)
        if target is None and prefix == "Strong":
            is_markup = bool(getattr(self._result, "is_markup", False))
            title = (
                "Strong Markup Studio matches (0)"
                if is_markup
                else "Strong script matches (0)"
            )
            target = QTreeWidgetItem(["", "", ""])
            target.setText(0, title)
            font = target.font(0)
            font.setBold(True)
            target.setFont(0, font)
            target.setFlags(
                target.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsAutoTristate
            )
            target.setCheckState(0, Qt.CheckState.Checked)
            self.tree.insertTopLevelItem(0, target)
        if target is None or parent is None:
            return
        self._updating_checks = True
        try:
            taken = parent.takeChild(parent.indexOfChild(item))
            if taken is None:
                return
            target.addChild(taken)
            target.setExpanded(True)
            self.tree.setCurrentItem(taken)
        finally:
            self._updating_checks = False
        self._refresh_group_title(parent)
        self._refresh_group_title(target)

    def _update_candidate_buttons_style(self, current_name: str) -> None:
        selected = set(split_shared_speaker_names(current_name))
        joined = NAME_SEPARATOR.join(split_shared_speaker_names(current_name))
        for btn in self._candidate_buttons:
            cand = btn.property("candidate_name")
            if not cand or cand == "__reset__":
                btn.setStyleSheet("padding: 3px 8px;")
                continue
            if cand == joined or cand in selected:
                btn.setStyleSheet(
                    "font-weight: bold; background-color: #d1e7dd; border: 1px solid #0f5132; border-radius: 3px; padding: 3px 8px;"
                )
            else:
                btn.setStyleSheet("padding: 3px 8px;")

    def _toggle_candidate(self, cand_name: str) -> None:
        current = split_shared_speaker_names(self.name_edit.text())
        if cand_name in current:
            current = [name for name in current if name != cand_name]
        else:
            current.append(cand_name)
        self._set_current_name(NAME_SEPARATOR.join(current))

    def _set_current_name(self, name: str) -> None:
        current = self.tree.currentItem()
        if not current:
            return
        self.name_edit.blockSignals(True)
        self.name_edit.setText(name)
        self.name_edit.blockSignals(False)
        current.setText(1, name)
        if is_applyable_speaker_alias(name):
            current.setCheckState(0, Qt.CheckState.Checked)
        self.apply_single_button.setEnabled(
            self._on_apply is not None and is_applyable_speaker_alias(name)
        )
        code = current.data(0, _CODE_ROLE)
        self.reset_button.setEnabled(bool(self._default_name(code)))
        self._update_counts_and_buttons()
        self._update_candidate_buttons_style(name)

    def _on_name_edit_changed(self, text: str) -> None:
        current = self.tree.currentItem()
        if not current:
            return
        current.setText(1, text)
        if is_applyable_speaker_alias(text):
            current.setCheckState(0, Qt.CheckState.Checked)
        self.apply_single_button.setEnabled(
            self._on_apply is not None and is_applyable_speaker_alias(text)
        )
        code = current.data(0, _CODE_ROLE)
        self.reset_button.setEnabled(bool(self._default_name(code)))
        self._update_counts_and_buttons()
        self._update_candidate_buttons_style(text)

    def _apply_checked(self) -> None:
        if self._on_apply is None:
            return
        names = self.chosen_names(only_checked=True)
        if not names:
            return
        if self._on_apply(names) is not False:
            self.accept()

    def _apply_all(self) -> None:
        if self._on_apply is None:
            return
        names = self.chosen_names(only_checked=False)
        if not names:
            return
        if self._on_apply(names) is not False:
            self.accept()

    def _apply(self) -> None:
        """Alias for backward compatibility."""
        self._apply_checked()

    def _apply_current_speaker(self) -> None:
        if self._on_apply is None:
            return
        current = self.tree.currentItem()
        if not current:
            return
        code = current.data(0, _CODE_ROLE)
        is_display = bool(current.data(0, _DISPLAY_ROLE))
        name = current.text(1).strip()
        if not code or is_display or not is_applyable_speaker_alias(name):
            return
        if self._on_apply({code: name}) is False:
            self.feedback_label.setStyleSheet("color: #b71c1c; font-weight: bold;")
            self.feedback_label.setText(f"Could not save '{code}'.")
            return
        current.setData(0, _APPLIED_NAME_ROLE, name)
        current_votes = current.text(2)
        if "[Applied]" not in current_votes:
            current.setText(2, f"{current_votes} • [Applied]" if current_votes else "[Applied]")
        self._paint_item(current, _STRONG_COLOR)
        if NAME_SEPARATOR not in name:
            self._move_item_to_group(current, "Strong")
        self._update_inspector(self.tree.currentItem())
        self.feedback_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
        self.feedback_label.setText(f"✓ Saved '{code}' → '{name}'")
        self._update_counts_and_buttons()
