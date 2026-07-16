"""Compact chapter selector backed by a searchable hierarchy dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)


class ChapterSelectionDialog(QDialog):
    """Choose one Story node without flattening the hierarchy into a menu."""

    ID_ROLE = Qt.ItemDataRole.UserRole
    PATH_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, projection=None, selected_id=None, parent=None, choices=None):
        super().__init__(parent)
        self.setWindowTitle("Choose chapter or scene")
        self.setMinimumSize(640, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose where this string belongs:"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search acts, chapters, and scenes…")
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(("Story structure", "Type"))
        self.tree.setColumnWidth(0, 470)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        layout.addWidget(self.tree)

        self.none_item = QTreeWidgetItem(("No chapter", ""))
        self.none_item.setData(0, self.ID_ROLE, None)
        self.none_item.setData(0, self.PATH_ROLE, ())
        self.tree.addTopLevelItem(self.none_item)

        selected_item = self.none_item if selected_id is None else None

        def add_folder(folder, parent_item=None, path=()):
            nonlocal selected_item
            current_path = path + (folder.title,)
            item = QTreeWidgetItem((folder.title, str(folder.node_type).title()))
            item.setData(0, self.ID_ROLE, folder.id)
            item.setData(0, self.PATH_ROLE, current_path)
            item.setToolTip(0, " › ".join(current_path))
            if parent_item is None:
                self.tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            if folder.id == selected_id:
                selected_item = item
            for child in folder.children:
                add_folder(child, item, current_path)

        if projection is not None:
            for root in projection.roots:
                add_folder(root)

        if choices:
            items_by_path = {}
            for folder_id, raw_path in choices:
                path = tuple(raw_path or ())
                parent_item = None
                for depth, title in enumerate(path, start=1):
                    partial_path = path[:depth]
                    item = items_by_path.get(partial_path)
                    if item is None:
                        item = QTreeWidgetItem((str(title), ""))
                        item.setData(0, self.ID_ROLE, None)
                        item.setData(0, self.PATH_ROLE, partial_path)
                        item.setToolTip(0, " › ".join(partial_path))
                        if parent_item is None:
                            self.tree.addTopLevelItem(item)
                        else:
                            parent_item.addChild(item)
                        items_by_path[partial_path] = item
                    parent_item = item
                if parent_item is not None:
                    parent_item.setData(0, self.ID_ROLE, folder_id)
                    if folder_id == selected_id:
                        selected_item = parent_item

        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)
            parent_item = selected_item.parent()
            while parent_item is not None:
                parent_item.setExpanded(True)
                parent_item = parent_item.parent()
            self.tree.scrollToItem(selected_item)
        else:
            self.tree.setCurrentItem(self.none_item)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Select")
        layout.addWidget(self.buttons)

        self.search_edit.textChanged.connect(self._filter_tree)
        self.tree.itemDoubleClicked.connect(lambda _item, _column: self.accept())
        self.tree.currentItemChanged.connect(self._update_accept_state)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self._update_accept_state(self.tree.currentItem())

    def _update_accept_state(self, item, _previous=None):
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(item is not None)

    def _filter_tree(self, text):
        query = text.strip().casefold()

        def visit(item):
            child_matches = any(visit(item.child(i)) for i in range(item.childCount()))
            path = " › ".join(item.data(0, self.PATH_ROLE) or ())
            own_match = not query or query in path.casefold()
            visible = own_match or child_matches
            item.setHidden(not visible)
            if query and child_matches:
                item.setExpanded(True)
            return visible

        for index in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(index))

        current = self.tree.currentItem()
        if query and (current is None or current.isHidden()):
            def first_visible(item):
                if not item.isHidden() and query in (
                    " › ".join(item.data(0, self.PATH_ROLE) or ())
                ).casefold():
                    return item
                for child_index in range(item.childCount()):
                    match = first_visible(item.child(child_index))
                    if match is not None:
                        return match
                return None

            for index in range(self.tree.topLevelItemCount()):
                match = first_visible(self.tree.topLevelItem(index))
                if match is not None:
                    self.tree.setCurrentItem(match)
                    break

    def selection(self):
        item = self.tree.currentItem()
        if item is None:
            return None, ()
        return item.data(0, self.ID_ROLE), tuple(item.data(0, self.PATH_ROLE) or ())


class HierarchicalChapterComboBox(QComboBox):
    """Combo-sized control that opens a proper tree picker instead of a flat popup."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._projection = None
        self._selection_path = ()
        self.addItem("No chapter", None)

    def set_story_projection(self, projection):
        self._projection = projection

    def set_story_selection(self, structure_id, path=()):
        self.blockSignals(True)
        self.clear()
        self._selection_path = tuple(path or ())
        text = " › ".join(self._selection_path) if structure_id is not None else "No chapter"
        self.addItem(text, structure_id)
        self.setCurrentIndex(0)
        self.story_structure_id = structure_id
        self.setToolTip(text if structure_id is not None else "No chapter assigned")
        self.blockSignals(False)

    def current_story_path(self):
        return self._selection_path

    def showPopup(self):
        if not self.isEnabled() or self._projection is None:
            return
        dialog = ChapterSelectionDialog(
            self._projection,
            selected_id=self.currentData(),
            parent=self.window(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        structure_id, path = dialog.selection()
        if structure_id == self.currentData() and tuple(path) == self._selection_path:
            return
        self.set_story_selection(structure_id, path)
        self.activated.emit(self.currentIndex())
