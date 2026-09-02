"""Manual and hierarchy marking actions for Script Markup Studio."""
from __future__ import annotations

import re

from PyQt6.QtWidgets import (
    QColorDialog,
)
from PyQt6.QtGui import (
    QColor,
)
from PyQt6.QtCore import Qt, QPoint
from core.script_markup import (
    LineKind,
    HierarchyType, HierarchyTypeDefinition,
)
from core.i18n import tr

from ui.script_markup.constants import (
    _MENU_MARKS,
    _CUSTOM_TYPE_COLORS,
)


class MarkingMixin:
    """Manual marks and hierarchy type-picker actions for Script Markup Studio."""

    # -------------------------------------------------------- manual marking
    def _add_mark_context_actions(self, menu, pos: QPoint | None = None):
        menu.addSeparator()
        if self.mode == "hierarchy":
            line_no = None
            if pos is not None:
                block = self.raw_edit.cursorForPosition(pos).block()
                line_no = block.blockNumber() if block.isValid() else None
                source_col = (
                    self.raw_edit.cursorForPosition(pos).positionInBlock()
                    if block.isValid() else None
                )
            else:
                source_col = None
            source_mark = self._hierarchy_mark_at_line(line_no, source_col) if line_no is not None else None
            if source_mark is not None:
                jump_tree_action = menu.addAction(tr('Jump to this text in tree'))
                jump_tree_action.triggered.connect(
                    lambda _checked=False, line=line_no, col=source_col: self._jump_raw_line_to_outline(line, col)
                )
                menu.addSeparator()
            fold_key = self._raw_fold_key_at_pos(pos, require_gutter=False) if pos is not None else None
            if fold_key:
                collapsed = fold_key in self._collapsed_hierarchy_keys
                fold_action = menu.addAction(
                    "Expand hierarchy node" if collapsed else "Collapse hierarchy node"
                )
                fold_action.triggered.connect(lambda _checked=False, key=fold_key: self._toggle_raw_hierarchy_fold(key))
            if self._collapsed_hierarchy_keys:
                expand_all_action = menu.addAction(tr('Expand all raw folds'))
                expand_all_action.triggered.connect(self._expand_all_raw_hierarchy_folds)
            if fold_key or self._collapsed_hierarchy_keys:
                menu.addSeparator()
            mark_action = menu.addAction(tr('Mark selection as hierarchy node'))
            mark_action.triggered.connect(self._mark_selection_as_hierarchy)
            if self._selected_hierarchy_marks():
                clear_hierarchy_action = menu.addAction(tr('Clear hierarchy mark'))
                clear_hierarchy_action.triggered.connect(self._clear_selected_hierarchy_marks)
            return

        mark_menu = menu.addMenu(tr('Mark selection as'))
        for label, kind in _MENU_MARKS:
            action = mark_menu.addAction(label)
            action.triggered.connect(lambda _checked=False, k=kind: self._mark_selection_as(k))

        if any(idx in self.manual_marks for idx in self._selected_line_indices()):
            clear_action = menu.addAction(tr('Clear manual mark'))
            clear_action.triggered.connect(self._clear_selected_manual_marks)

    def _selected_line_indices(self) -> list[int]:
        cursor = self.raw_edit.textCursor()
        if not cursor.hasSelection():
            return [cursor.blockNumber()]

        start = min(cursor.selectionStart(), cursor.selectionEnd())
        end = max(cursor.selectionStart(), cursor.selectionEnd())
        if end > start:
            end -= 1

        doc = self.raw_edit.document()
        first = doc.findBlock(start).blockNumber()
        last = doc.findBlock(end).blockNumber()
        if first < 0 or last < first:
            return []
        return list(range(first, last + 1))

    def _selected_text_in_line(self, line_idx: int) -> str:
        cursor = self.raw_edit.textCursor()
        if not cursor.hasSelection():
            return ""

        block = self.raw_edit.document().findBlockByNumber(line_idx)
        if not block.isValid():
            return ""

        start = max(min(cursor.selectionStart(), cursor.selectionEnd()), block.position())
        end = min(max(cursor.selectionStart(), cursor.selectionEnd()), block.position() + len(block.text()))
        if end <= start:
            return ""
        return block.text()[start - block.position():end - block.position()].strip()

    def _clean_mark_text(self, text: str) -> str:
        s = (text or "").replace(chr(0x2029), "\n").strip()
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"^\[\s*(?:Chapter|Location)\s*:\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^\{\s*(?:Action|Context)\s*:\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^[\[\{]\s*", "", s)
        s = re.sub(r"\s*[\]\}]\s*$", "", s)
        return s.strip()

    def _manual_speaker_name(self, text: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9 #\-]", " ", text or "")
        return re.sub(r"\s+", " ", cleaned).strip().upper()

    def _build_manual_mark(self, line_idx: int, kind: str) -> dict[str, object]:
        block = self.raw_edit.document().findBlockByNumber(line_idx)
        raw = block.text() if block.isValid() else ""
        selected = self._selected_text_in_line(line_idx)

        if kind == LineKind.SPEAKER:
            line = raw.strip()
            if ":" in line:
                speaker, body = line.split(":", 1)
                return {
                    "kind": LineKind.SPEAKER,
                    "speaker": self._manual_speaker_name(selected or speaker),
                    "text": body.strip(),
                }
            if selected and selected != line:
                pos = line.find(selected)
                body = line[pos + len(selected):].lstrip(" :-\t") if pos >= 0 else ""
                return {
                    "kind": LineKind.SPEAKER,
                    "speaker": self._manual_speaker_name(selected),
                    "text": body.strip(),
                }
            return {
                "kind": LineKind.GUTTER_SPEAKER,
                "speaker": self._manual_speaker_name(selected or line),
                "text": "",
            }

        return {"kind": kind, "text": self._clean_mark_text(selected or raw)}

    def _mark_selection_as(self, kind: str):
        changed = False
        for idx in self._selected_line_indices():
            self.manual_marks[idx] = self._build_manual_mark(idx, kind)
            changed = True
        if changed:
            self._refresh()
            self._record_history()

    def _clear_selected_manual_marks(self):
        changed = False
        for idx in self._selected_line_indices():
            if idx in self.manual_marks:
                del self.manual_marks[idx]
                changed = True
        if changed:
            self._refresh()
            self._record_history()

    def _selected_line_span(self) -> tuple[int, int] | None:
        indices = self._selected_line_indices()
        if not indices:
            return None
        return min(indices), max(indices)

    def _source_text_for_lines(self, start: int, end: int, lines: list[str] | None = None) -> str:
        lines = lines if lines is not None else self.raw_edit.toPlainText().splitlines()
        if not lines:
            return ""
        start = max(0, min(start, len(lines) - 1))
        end = max(start, min(end, len(lines) - 1))
        return self._clean_mark_text(" ".join(lines[start:end + 1]))

    def _clean_hierarchy_type_label(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _custom_hierarchy_type_id(self, label: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "custom"
        base = f"custom:{slug}"
        type_id = base
        suffix = 2
        while (
            type_id in self.hierarchy_type_definitions
            and self.hierarchy_type_definitions[type_id].label.casefold() != label.casefold()
        ):
            type_id = f"{base}_{suffix}"
            suffix += 1
        return type_id

    def _default_custom_type_color(self, label: str) -> str:
        idx = sum(ord(ch) for ch in label) % len(_CUSTOM_TYPE_COLORS)
        return _CUSTOM_TYPE_COLORS[idx]

    def _hierarchy_type_def_for_text(self, text: str) -> HierarchyTypeDefinition | None:
        label = self._clean_hierarchy_type_label(text)
        if not label:
            return None
        folded = label.casefold()
        for type_def in self.hierarchy_type_definitions.values():
            if type_def.type_id == HierarchyType.UNMARKED:
                continue
            if type_def.label.casefold() == folded or type_def.type_id.casefold() == folded:
                return type_def
        return None

    def _hierarchy_type_index(self, type_id: str) -> int:
        for idx in range(self.hierarchy_type_combo.count()):
            if self.hierarchy_type_combo.itemData(idx) == type_id:
                return idx
        return -1

    def _add_hierarchy_type_item(self, type_def: HierarchyTypeDefinition) -> int:
        if type_def.type_id in (
            HierarchyType.UNMARKED,
            HierarchyType.ITEM,
            HierarchyType.ITEM_DESCRIPTION,
        ):
            return -1
        idx = self._hierarchy_type_index(type_def.type_id)
        if idx < 0:
            self.hierarchy_type_combo.addItem(type_def.label, type_def.type_id)
            idx = self.hierarchy_type_combo.count() - 1
        else:
            self.hierarchy_type_combo.setItemText(idx, type_def.label)
            self.hierarchy_type_combo.setItemData(idx, type_def.type_id)
        self.hierarchy_type_combo.setItemData(
            idx,
            QColor(type_def.color),
            Qt.ItemDataRole.BackgroundRole,
        )
        self.hierarchy_type_combo.setItemData(
            idx,
            QColor("#111111"),
            Qt.ItemDataRole.ForegroundRole,
        )
        return idx

    def _ensure_hierarchy_type(
        self,
        text: str | None = None,
        *,
        select: bool = False,
    ) -> HierarchyTypeDefinition:
        label = self._clean_hierarchy_type_label(
            self.hierarchy_type_combo.currentText() if text is None else text
        )
        existing = self._hierarchy_type_def_for_text(label)
        if existing:
            if existing.type_id in (HierarchyType.ITEM, HierarchyType.ITEM_DESCRIPTION):
                role_idx = self.hierarchy_role_combo.findData("item")
                old_role_blocked = self.hierarchy_role_combo.blockSignals(True)
                try:
                    if role_idx >= 0:
                        self.hierarchy_role_combo.setCurrentIndex(role_idx)
                finally:
                    self.hierarchy_role_combo.blockSignals(old_role_blocked)
                existing = self.hierarchy_type_definitions[
                    self._visible_hierarchy_type_id(existing.type_id)
                ]
            if select:
                idx = self._add_hierarchy_type_item(existing)
                if idx >= 0 and self.hierarchy_type_combo.currentIndex() != idx:
                    self.hierarchy_type_combo.setCurrentIndex(idx)
            return existing

        if not label:
            return self.hierarchy_type_definitions[HierarchyType.TEXT]

        type_id = self._custom_hierarchy_type_id(label)
        type_def = HierarchyTypeDefinition(
            type_id,
            label,
            f"Custom hierarchy type: {label}.",
            self._default_custom_type_color(label),
        )
        self.hierarchy_type_definitions[type_id] = type_def
        idx = self._add_hierarchy_type_item(type_def)
        if select and idx >= 0:
            self.hierarchy_type_combo.setCurrentIndex(idx)
        return type_def

    def _finalize_hierarchy_type_text(self):
        self._ensure_hierarchy_type(select=True)
        self._on_hierarchy_type_changed()
        self._record_history()

    def _reset_hierarchy_type_edit_view(self):
        type_edit = self.hierarchy_type_combo.lineEdit()
        if type_edit is not None and not type_edit.hasFocus():
            type_edit.deselect()
            type_edit.setCursorPosition(0)

    def _current_hierarchy_type_id(self) -> str:
        return self._current_hierarchy_type_def().type_id

    def _current_hierarchy_type_def(self) -> HierarchyTypeDefinition:
        base_type = self._ensure_hierarchy_type(select=True)
        resolved_type_id = self._resolved_hierarchy_type_id(base_type.type_id)
        return self.hierarchy_type_definitions[resolved_type_id]

    @staticmethod
    def _visible_hierarchy_type_id(type_id: str) -> str:
        return {
            HierarchyType.ITEM: HierarchyType.SPEAKER,
            HierarchyType.ITEM_DESCRIPTION: HierarchyType.TEXT,
        }.get(str(type_id), str(type_id))

    @staticmethod
    def _role_for_hierarchy_type(type_id) -> str:
        return (
            "item"
            if str(type_id) in (HierarchyType.ITEM, HierarchyType.ITEM_DESCRIPTION)
            else "speaker"
        )

    def _resolved_hierarchy_type_id(self, base_type_id: str) -> str:
        if self.hierarchy_role_combo.currentData() != "item":
            return base_type_id
        return {
            HierarchyType.SPEAKER: HierarchyType.ITEM,
            HierarchyType.TEXT: HierarchyType.ITEM_DESCRIPTION,
        }.get(base_type_id, base_type_id)

    def _on_hierarchy_role_changed(self):
        self._on_hierarchy_type_changed()
        if self._history_ready and not self._history_suspended:
            self._record_history()

    def _on_hierarchy_type_changed(self):
        if not hasattr(self, "hierarchy_color_btn"):
            return
        type_def = self._current_hierarchy_type_def()
        base_type_id = self._visible_hierarchy_type_id(type_def.type_id)
        role_visible = base_type_id in (HierarchyType.SPEAKER, HierarchyType.TEXT)
        self.hierarchy_role_label.setVisible(role_visible)
        self.hierarchy_role_combo.setVisible(role_visible)
        if role_visible:
            self.hierarchy_role_combo.setToolTip(
                "Item" if self.hierarchy_role_combo.currentData() == "item" else "Speaker"
            )
        self.hierarchy_type_combo.setStyleSheet(
            "QComboBox, QComboBox QLineEdit {"
            f"  background-color: {type_def.color};"
            "}"
        )
        self.hierarchy_color_btn.setStyleSheet(
            "QPushButton { "
            f"background:{type_def.color}; "
            "border:1px solid #999; border-radius:4px; "
            "padding:3px 10px; min-height:24px; "
            "}"
        )
        self.hierarchy_color_btn.setToolTip(
            f"Choose the default highlight color for {type_def.label} marks.\n"
            f"{type_def.description}"
        )
        self._reset_hierarchy_type_edit_view()
        if hasattr(self, "hierarchy_split_text_cb"):
            self.hierarchy_split_text_cb.setEnabled(
                not self._is_hierarchy_editing()
                and type_def.type_id == HierarchyType.TEXT
            )

    def _choose_hierarchy_type_color(self):
        type_def = self._current_hierarchy_type_def()
        type_id = type_def.type_id
        chosen = QColorDialog.getColor(QColor(type_def.color), self, "Choose type colour")
        if not chosen.isValid():
            return
        updated = HierarchyTypeDefinition(
            type_def.type_id,
            type_def.label,
            type_def.description,
            chosen.name(),
        )
        self.hierarchy_type_definitions[type_id] = updated
        idx = self._add_hierarchy_type_item(updated)
        if idx >= 0:
            self.hierarchy_type_combo.setCurrentIndex(idx)
        self._on_hierarchy_type_changed()
        self._refresh()
        self._record_history()

