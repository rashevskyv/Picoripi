from __future__ import annotations

from collections import Counter
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStyledItemDelegate,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from core.speaker_alias_merge import NAME_SEPARATOR, is_confirmed_speaker_alias

_CODE_ROLE = Qt.ItemDataRole.UserRole
_DISPLAY_ROLE = Qt.ItemDataRole.UserRole + 1


class NameOnlyDelegate(QStyledItemDelegate):
    """Allow inline editing only on column 1 (Name column)."""

    def createEditor(self, parent, option, index):
        if index.column() == 1:
            return super().createEditor(parent, option, index)
        return None


def _votes_line(counter) -> str:
    return ", ".join(
        f"{name} x{n}" for name, n in sorted((counter or {}).items(), key=lambda kv: -kv[1])
    )


def _top_name(counter) -> str:
    """The name with the most votes: the suggestion to confirm or correct."""
    if not counter:
        return ""
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def extract_candidates(result, code: str) -> List[Tuple[str, int]]:
    """Return [(candidate_name, vote_count), ...] for the given speaker code."""
    if not code:
        return []
    votes = result.evidence.get(code) or []
    counter: Counter[str] = Counter(
        vote.speaker for vote in votes if getattr(vote, "speaker", None)
    )
    unproven = result.unproven.get(code) or {}
    for name, cnt in unproven.items():
        if name and name not in counter:
            counter[name] = cnt
    resolved = result.resolved.get(code) or ""
    resolved_order = {}
    if resolved:
        for idx, part in enumerate(resolved.split(NAME_SEPARATOR)):
            part = part.strip()
            if part:
                resolved_order[part] = idx
                if part not in counter:
                    counter[part] = 1
    return sorted(
        counter.items(),
        key=lambda kv: (-kv[1], resolved_order.get(kv[0], 999), kv[0]),
    )


def describe_code(result, code: str) -> str:
    """The evidence behind one code, as plain text for the right-hand pane."""
    if hasattr(result, "game_display_names") and code in (
        getattr(result, "game_display_names", ()) or ()
    ):
        return (
            f"{code}\n\n"
            "Real display name supplied directly by game data. Excluded from merge "
            "and not saved as an alias."
        )

    name = result.resolved.get(code)
    unproven = result.unproven.get(code)

    if name:
        head = [f"{code}  →  {name}", ""]
        if NAME_SEPARATOR in name:
            head += [
                "This voice is shared by more than one character. That is what "
                "the game does -- a pair of children, a street of townspeople "
                "and a coop of cuccos each speak with one voice -- and the "
                "lines below fall on different rows, so all of these names are "
                "kept rather than one being chosen over the others.",
                "",
            ]
    elif unproven:
        head = [
            f"{code}  →  suggested: {_top_name(unproven)}",
            "",
            "Too few matching lines to decide this on its own -- a single short "
            "line is said by half the cast. Read the line below: if it is "
            "unmistakably this character, keep the name and Apply. If not, type "
            "the right one over it, or clear it to leave the voice unnamed.",
            f"Votes: {_votes_line(unproven)}",
            "",
        ]
    else:
        return f"{code}\n\nNo script line matched this voice."

    votes = result.evidence.get(code) or []
    head.append(f"Decided from {len(votes)} matching script line(s):")
    head.append("")
    for vote in votes:
        where = " ".join(f"[Block {b} • String {s}]" for b, s in vote.rows)
        head.append(f"{vote.speaker}: {vote.text}")
        head.append(f"    {where}")
    return "\n".join(head)


class SpeakerMergeDialog(QDialog):
    """Merged names on the left; the lines behind the selected one on the right."""

    def __init__(self, result, parent=None, on_apply=None):
        if parent is not None and (
            not isinstance(parent, QWidget) or bool(getattr(parent, "_is_test_mode", False))
        ):
            parent = None
        super().__init__(parent)
        self.setWindowTitle("Merge Speakers")
        self.resize(1080, 680)
        self._result = result
        self._on_apply = on_apply
        self._updating_checks = False
        self._candidate_buttons: List[QPushButton] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header summary & hint
        layout.addWidget(QLabel(result.summary, self))
        hint = QLabel(
            "Select which speaker names to apply using checkboxes or choose candidates in the inspector. "
            "Double-click a Name cell to edit inline.",
            self,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666666;")
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # --- Left panel: Filter + Tree ---
        left_widget = QWidget(splitter)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit(left_widget)
        self.search_edit.setPlaceholderText("Filter voices or names...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_tree)
        search_layout.addWidget(self.search_edit, 1)

        self.check_all_btn = QPushButton("Check All", left_widget)
        self.check_all_btn.clicked.connect(self._check_all)
        search_layout.addWidget(self.check_all_btn)

        self.uncheck_all_btn = QPushButton("Uncheck All", left_widget)
        self.uncheck_all_btn.clicked.connect(self._uncheck_all)
        search_layout.addWidget(self.uncheck_all_btn)
        left_layout.addLayout(search_layout)

        self.tree = QTreeWidget(left_widget)
        self.tree.setHeaderLabels(["Voice", "Name", "Votes / Source"])
        self.tree.setColumnWidth(0, 160)
        self.tree.setColumnWidth(1, 200)
        self.tree.setRootIsDecorated(True)
        self.tree.setItemDelegate(NameOnlyDelegate(self.tree))
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemChanged.connect(self._on_item_changed)
        left_layout.addWidget(self.tree, 1)

        # --- Right panel: Inspector + Evidence ---
        right_widget = QWidget(splitter)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # Inspector Card
        self.inspector_card = QFrame(right_widget)
        self.inspector_card.setFrameShape(QFrame.Shape.StyledPanel)
        self.inspector_card.setStyleSheet(
            "QFrame { background-color: rgba(0, 0, 0, 0.02); border: 1px solid rgba(0, 0, 0, 0.1); border-radius: 4px; padding: 6px; }"
        )
        card_layout = QVBoxLayout(self.inspector_card)
        card_layout.setSpacing(6)

        title_layout = QHBoxLayout()
        self.inspector_title = QLabel("Select a speaker", self.inspector_card)
        title_font = self.inspector_title.font()
        title_font.setBold(True)
        self.inspector_title.setFont(title_font)
        title_layout.addWidget(self.inspector_title)

        self.inspector_badge = QLabel("", self.inspector_card)
        title_layout.addWidget(self.inspector_badge)
        title_layout.addStretch()
        card_layout.addLayout(title_layout)

        # Candidate chips area
        self.candidates_widget = QWidget(self.inspector_card)
        cand_outer = QVBoxLayout(self.candidates_widget)
        cand_outer.setContentsMargins(0, 0, 0, 0)
        cand_outer.setSpacing(4)
        cand_outer.addWidget(QLabel("Choose Candidate Name:", self.candidates_widget))

        self.candidates_layout = QHBoxLayout()
        self.candidates_layout.setSpacing(6)
        cand_outer.addLayout(self.candidates_layout)
        card_layout.addWidget(self.candidates_widget)

        # Name edit row
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:", self.inspector_card))
        self.name_edit = QLineEdit(self.inspector_card)
        self.name_edit.setPlaceholderText("Enter or select speaker name...")
        self.name_edit.textChanged.connect(self._on_name_edit_changed)
        name_layout.addWidget(self.name_edit, 1)

        self.apply_single_button = QPushButton("Apply This Speaker", self.inspector_card)
        self.apply_single_button.setToolTip("Apply and save only this speaker mapping now")
        self.apply_single_button.clicked.connect(self._apply_current_speaker)
        name_layout.addWidget(self.apply_single_button)
        card_layout.addLayout(name_layout)

        self.feedback_label = QLabel("", self.inspector_card)
        self.feedback_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
        card_layout.addWidget(self.feedback_label)

        right_layout.addWidget(self.inspector_card)

        # Evidence details
        self.details = QPlainTextEdit(right_widget)
        self.details.setReadOnly(True)
        self.details.setUndoRedoEnabled(False)
        right_layout.addWidget(self.details, 1)

        splitter.setSizes([580, 480])
        layout.addWidget(splitter, 1)

        # --- Bottom bar ---
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel(self)
        self.status_label.setStyleSheet("color: #555555;")
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()

        self.apply_button = QPushButton("Apply checked names", self)
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self._apply_checked)
        bottom_layout.addWidget(self.apply_button)

        self.apply_all_button = QPushButton("Apply All Valid", self)
        self.apply_all_button.setToolTip("Apply all non-empty speaker names regardless of checkbox state")
        self.apply_all_button.clicked.connect(self._apply_all)
        bottom_layout.addWidget(self.apply_all_button)

        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.reject)
        bottom_layout.addWidget(self.close_button)

        layout.addLayout(bottom_layout)

        self._populate()
        self.tree.currentItemChanged.connect(self._on_selection)
        self._select_first()
        self._update_counts_and_buttons()

    # -- building -----------------------------------------------------------

    def _populate(self) -> None:
        resolved = getattr(self._result, "resolved", {}) or {}
        unproven = getattr(self._result, "unproven", {}) or {}
        all_placeholders = getattr(self._result, "all_placeholders", []) or []
        game_display_names = getattr(self._result, "game_display_names", []) or []
        is_markup = bool(getattr(self._result, "is_markup", False))

        strong_matches = []
        shared_matches = []
        for code, name in sorted(resolved.items()):
            votes_str = _votes_line(unproven.get(code) or self._votes_for(code))
            if NAME_SEPARATOR in name:
                source = f"{votes_str} • Shared voice" if votes_str else "Shared voice"
                shared_matches.append((code, name, source))
            else:
                source_tag = "Markup Studio match" if is_markup else "Script match"
                source = f"{votes_str} • {source_tag}" if votes_str else source_tag
                strong_matches.append((code, name, source))

        suggested = []
        for code, counter in sorted(unproven.items()):
            if code in resolved:
                continue
            votes = self._result.evidence.get(code) or []
            is_glossary = any("glossary description" in getattr(v, "text", "") for v in votes)
            top = _top_name(counter)
            if is_glossary:
                source = "Glossary suggestion"
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
        self._add_group(strong_label, strong_matches, QColor("#2e7d32"))
        self._add_group(f"Shared / conflicting matches ({len(shared_matches)})", shared_matches, QColor("#e65100"))
        self._add_group(f"Weak or AI suggestions ({len(suggested)})", suggested, QColor("#1565c0"))
        self._add_group(f"Unmatched manual rows ({len(unmatched)})", unmatched, QColor("#6a1b9a"))
        self._add_group(
            f"Game data display names ({len(display_items)})",
            display_items,
            QColor("#00695c"),
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
                if is_confirmed_speaker_alias(name):
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

    def chosen_names(self, only_checked: bool = True) -> dict:
        """``{code: name}`` as the tree now reads, blanks left out."""
        names = {}
        walker = QTreeWidgetItemIterator(self.tree)
        while walker.value():
            item = walker.value()
            code = item.data(0, _CODE_ROLE)
            is_display = bool(item.data(0, _DISPLAY_ROLE))
            name = item.text(1).strip()
            if code and is_confirmed_speaker_alias(name) and not is_display:
                if not only_checked or item.checkState(0) == Qt.CheckState.Checked:
                    names[code] = name
            walker += 1
        return names

    # -- Inspector & Candidate Updates --------------------------------------

    def _update_inspector(self, item: Optional[QTreeWidgetItem]) -> None:
        while self.candidates_layout.count():
            w_item = self.candidates_layout.takeAt(0)
            widget = w_item.widget()
            if widget:
                widget.deleteLater()
        self._candidate_buttons.clear()

        if item is None:
            self.inspector_title.setText("Select a speaker")
            self.inspector_badge.setText("")
            self.name_edit.setEnabled(False)
            self.name_edit.setText("")
            self.apply_single_button.setEnabled(False)
            self.candidates_widget.setVisible(False)
            self.feedback_label.setText("")
            return

        code = item.data(0, _CODE_ROLE)
        is_display = bool(item.data(0, _DISPLAY_ROLE))
        name = item.text(1).strip()

        if is_display or not code:
            self.inspector_title.setText(f"Display Name: {code or item.text(0)}")
            self.inspector_badge.setText("Game Data (Read-only)")
            self.inspector_badge.setStyleSheet("color: #00695c; font-weight: bold;")
            self.name_edit.setEnabled(False)
            self.name_edit.setText(name)
            self.apply_single_button.setEnabled(False)
            self.candidates_widget.setVisible(False)
            self.feedback_label.setText("")
            return

        parent = item.parent()
        group_title = parent.text(0) if parent else ""
        self.inspector_title.setText(f"Voice Code: {code}")

        if "Shared" in group_title:
            self.inspector_badge.setText("Shared Voice / Multiple Candidates")
            self.inspector_badge.setStyleSheet("color: #e65100; font-weight: bold;")
        elif "Weak" in group_title:
            self.inspector_badge.setText("Weak / AI Suggestion")
            self.inspector_badge.setStyleSheet("color: #1565c0; font-weight: bold;")
        elif "Strong" in group_title:
            self.inspector_badge.setText("Strong Match")
            self.inspector_badge.setStyleSheet("color: #2e7d32; font-weight: bold;")
        else:
            self.inspector_badge.setText("Unmatched Placeholder")
            self.inspector_badge.setStyleSheet("color: #6a1b9a; font-weight: bold;")

        self.name_edit.setEnabled(True)
        self.name_edit.blockSignals(True)
        self.name_edit.setText(name)
        self.name_edit.blockSignals(False)
        self.apply_single_button.setEnabled(
            self._on_apply is not None and is_confirmed_speaker_alias(name)
        )
        self.feedback_label.setText("")

        candidates = extract_candidates(self._result, code)
        if candidates:
            self.candidates_widget.setVisible(True)
            for cand_name, vote_count in candidates:
                label = f"{cand_name} ({vote_count})" if vote_count > 1 else cand_name
                btn = QPushButton(label, self.candidates_widget)
                btn.setProperty("candidate_name", cand_name)
                btn.setToolTip(f"Choose '{cand_name}'")
                btn.clicked.connect(lambda _, n=cand_name: self._set_current_name(n))
                self.candidates_layout.addWidget(btn)
                self._candidate_buttons.append(btn)

            btn_clear = QPushButton("Clear", self.candidates_widget)
            btn_clear.setProperty("candidate_name", "")
            btn_clear.setToolTip("Clear name for this voice")
            btn_clear.clicked.connect(lambda: self._set_current_name(""))
            self.candidates_layout.addWidget(btn_clear)
            self._candidate_buttons.append(btn_clear)

            self._update_candidate_buttons_style(name)
        else:
            self.candidates_widget.setVisible(False)

    def _update_candidate_buttons_style(self, current_name: str) -> None:
        current_name = (current_name or "").strip()
        for btn in self._candidate_buttons:
            cand = btn.property("candidate_name")
            if cand is not None and cand == current_name and cand != "":
                btn.setStyleSheet(
                    "font-weight: bold; background-color: #d1e7dd; border: 1px solid #0f5132; border-radius: 3px; padding: 3px 8px;"
                )
            else:
                btn.setStyleSheet("padding: 3px 8px;")

    def _set_current_name(self, name: str) -> None:
        current = self.tree.currentItem()
        if not current:
            return
        self.name_edit.blockSignals(True)
        self.name_edit.setText(name)
        self.name_edit.blockSignals(False)
        current.setText(1, name)
        if is_confirmed_speaker_alias(name):
            current.setCheckState(0, Qt.CheckState.Checked)
        self.apply_single_button.setEnabled(
            self._on_apply is not None and is_confirmed_speaker_alias(name)
        )
        self._update_counts_and_buttons()
        self._update_candidate_buttons_style(name)

    def _on_name_edit_changed(self, text: str) -> None:
        current = self.tree.currentItem()
        if not current:
            return
        current.setText(1, text)
        if is_confirmed_speaker_alias(text):
            current.setCheckState(0, Qt.CheckState.Checked)
        self.apply_single_button.setEnabled(
            self._on_apply is not None and is_confirmed_speaker_alias(text)
        )
        self._update_counts_and_buttons()
        self._update_candidate_buttons_style(text)

    # -- Application actions ------------------------------------------------

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
        if not code or is_display or not is_confirmed_speaker_alias(name):
            return
        if self._on_apply({code: name}) is False:
            self.feedback_label.setStyleSheet("color: #b71c1c; font-weight: bold;")
            self.feedback_label.setText(f"Could not save '{code}'.")
            return
        self.feedback_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
        self.feedback_label.setText(f"✓ Saved '{code}' → '{name}'")
        current_votes = current.text(2)
        if "[Applied]" not in current_votes:
            current.setText(2, f"{current_votes} • [Applied]" if current_votes else "[Applied]")
        self._update_counts_and_buttons()

    # -- Selection & Filtering ----------------------------------------------

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
                    self.apply_single_button.setEnabled(self._on_apply is not None and bool(text))
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
                self._on_apply is not None and is_confirmed_speaker_alias(name)
            )

            is_checked = item.checkState(0) == Qt.CheckState.Checked
            menu.addAction(
                "Uncheck" if is_checked else "Check",
                lambda: item.setCheckState(
                    0, Qt.CheckState.Unchecked if is_checked else Qt.CheckState.Checked
                ),
            )
            menu.addAction("Clear Name", lambda: self._set_current_name(""))
            menu.addSeparator()

        parent = item.parent() or item
        if parent.childCount() > 0:
            menu.addAction(
                "Check All in Group",
                lambda p=parent: self._toggle_group_checks(p, Qt.CheckState.Checked),
            )
            menu.addAction(
                "Uncheck All in Group",
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
