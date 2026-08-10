"""Show what the speaker join decided, next to the lines it decided it from.

The join's own output is a wall of text: sixty codes, their votes and their
counts. Nobody reads that, and nobody can check it -- the counts say a decision
was made but not what it rests on. So the decisions go on the left, one row
each, and picking one puts its evidence on the right: every script line that
voted, and the game row it matched.

Reading those rows is what shows a shared voice for what it is. "CHILD #1 x7,
CHILD 2 x2" looks like a contradiction until the lines show one child on rows
1323-1335 and the other on 1219-1220.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from core.speaker_alias_merge import NAME_SEPARATOR
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QStyledItemDelegate,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

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


def describe_code(result, code: str) -> str:
    """The evidence behind one code, as plain text for the right-hand pane."""
    if hasattr(result, "game_display_names") and code in (getattr(result, "game_display_names", ()) or ()):
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
        # Same guard as the other report dialogs: a MagicMock parent in tests is
        # not a QWidget and would abort the C++ constructor.
        if parent is not None and (
            not isinstance(parent, QWidget) or bool(getattr(parent, "_is_test_mode", False))
        ):
            parent = None
        super().__init__(parent)
        self.setWindowTitle("Merge Speakers")
        self.resize(1020, 620)
        self._result = result
        self._on_apply = on_apply

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(result.summary, self))
        hint = QLabel(
            "Double-click a Name cell to set or edit it. Blanks can be filled "
            "manually or cleared to reject a suggestion. Click 'Apply names' to save.",
            self,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666666;")
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.tree = QTreeWidget(splitter)
        self.tree.setHeaderLabels(["Voice", "Name", "Votes / Source"])
        self.tree.setColumnWidth(0, 130)
        self.tree.setColumnWidth(1, 210)
        self.tree.setRootIsDecorated(True)
        self.tree.setItemDelegate(NameOnlyDelegate(self.tree))
        self.details = QPlainTextEdit(splitter)
        self.details.setReadOnly(True)
        self.details.setUndoRedoEnabled(False)
        splitter.setSizes([560, 460])
        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.apply_button = buttons.addButton(
            "Apply names", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.apply_button.clicked.connect(self._apply)
        self.apply_button.setEnabled(on_apply is not None)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate()
        self.tree.currentItemChanged.connect(self._on_selection)
        self._select_first()

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

        brush = QBrush(color)
        for code, name, votes in rows:
            child = QTreeWidgetItem(group, [code, name, votes])
            child.setData(0, _CODE_ROLE, code)
            if is_display_name:
                child.setData(0, _DISPLAY_ROLE, True)
            if is_editable:
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsEditable)
            else:
                child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsEditable)
            for col in range(3):
                child.setForeground(col, brush)
        group.setExpanded(True)

    def chosen_names(self) -> dict:
        """``{code: name}`` as the tree now reads, blanks left out."""
        names = {}
        walker = QTreeWidgetItemIterator(self.tree)
        while walker.value():
            item = walker.value()
            code = item.data(0, _CODE_ROLE)
            is_display = bool(item.data(0, _DISPLAY_ROLE))
            name = item.text(1).strip()
            if code and name and not is_display:
                names[code] = name
            walker += 1
        return names

    def _apply(self) -> None:
        if self._on_apply is None:
            return
        self._on_apply(self.chosen_names())
        self.accept()

    def _select_first(self) -> None:
        top = self.tree.topLevelItem(0)
        if top is not None and top.childCount():
            self.tree.setCurrentItem(top.child(0))
        elif not self._result.evidence and not getattr(self._result, "all_placeholders", None) and not getattr(self._result, "game_display_names", None):
            self.details.setPlainText("Nothing was matched, so there is nothing to show.")

    # -- signals ------------------------------------------------------------

    def _on_selection(self, current, _previous=None) -> None:
        code = current.data(0, _CODE_ROLE) if current is not None else None
        self.details.setPlainText(describe_code(self._result, code) if code else "")
