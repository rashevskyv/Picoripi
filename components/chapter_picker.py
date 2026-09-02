"""Compact chapter selector backed by a searchable hierarchy dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)
from core.i18n import tr


class StoryStructureTree(QTreeWidget):
    """Editable hierarchy tree that reports completed internal moves."""

    structureDropped = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.none_item = None
        self._dragged_item = None
        self._dragged_path = ()
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None or item is self.none_item:
            return
        self._dragged_item = item
        self._dragged_path = tuple(
            item.data(0, Qt.ItemDataRole.UserRole + 1) or ()
        )
        super().startDrag(supported_actions)

    def dropEvent(self, event):
        dragged_item = self._dragged_item
        old_path = self._dragged_path
        target = self.itemAt(event.position().toPoint())
        if (
            target is self.none_item
            and self.dropIndicatorPosition()
            == QAbstractItemView.DropIndicatorPosition.OnItem
        ):
            event.ignore()
            return
        super().dropEvent(event)
        if self.none_item is not None:
            index = self.indexOfTopLevelItem(self.none_item)
            if index > 0:
                self.insertTopLevelItem(0, self.takeTopLevelItem(index))
        if dragged_item is not None and dragged_item.treeWidget() is self:
            self.structureDropped.emit(dragged_item, old_path)
        self._dragged_item = None
        self._dragged_path = ()


class ChapterSelectionDialog(QDialog):
    """Choose one Story node without flattening the hierarchy into a menu."""

    ID_ROLE = Qt.ItemDataRole.UserRole
    PATH_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, projection=None, selected_id=None, parent=None, choices=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Choose chapter or scene'))
        self.setMinimumSize(640, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr('Choose where this string belongs:')))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr('Search acts, chapters, and scenes…'))
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)

        self.tree = StoryStructureTree()
        self.tree.setHeaderLabels(("Story structure", "Type"))
        self.tree.setColumnWidth(0, 470)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        layout.addWidget(self.tree)

        edit_hint = QLabel(
            tr('Drag nodes to reorder or nest them. Add under the selected node, or select No chapter to add at the top level:')
        )
        layout.addWidget(edit_hint)
        edit_row = QHBoxLayout()
        self.add_act_button = QPushButton(tr('+ Act'))
        self.add_chapter_button = QPushButton(tr('+ Chapter'))
        self.add_scene_button = QPushButton(tr('+ Scene'))
        self.rename_button = QPushButton(tr('Rename'))
        self.remove_button = QPushButton(tr('Remove'))
        for button in (
            self.add_act_button,
            self.add_chapter_button,
            self.add_scene_button,
            self.rename_button,
            self.remove_button,
        ):
            edit_row.addWidget(button)
        edit_row.addStretch(1)
        layout.addLayout(edit_row)

        self._project_manager = self._find_project_manager()
        self._structure_changed = False
        can_edit = bool(
            self._project_manager is not None
            and getattr(self._project_manager, "project", None) is not None
        )
        edit_hint.setEnabled(can_edit)
        for button in (
            self.add_act_button,
            self.add_chapter_button,
            self.add_scene_button,
            self.rename_button,
            self.remove_button,
        ):
            button.setEnabled(can_edit)

        self.none_item = QTreeWidgetItem(("No chapter", ""))
        self.none_item.setData(0, self.ID_ROLE, None)
        self.none_item.setData(0, self.PATH_ROLE, ())
        self.none_item.setFlags(
            self.none_item.flags()
            & ~Qt.ItemFlag.ItemIsDragEnabled
            & ~Qt.ItemFlag.ItemIsDropEnabled
        )
        self.tree.none_item = self.none_item
        self.tree.addTopLevelItem(self.none_item)

        selected_item = self.none_item if selected_id is None else None

        def add_folder(folder, parent_item=None, path=()):
            nonlocal selected_item
            current_path = path + (folder.title,)
            item = QTreeWidgetItem((folder.title, str(folder.node_type).title()))
            item.setData(0, self.ID_ROLE, folder.id)
            item.setData(0, self.PATH_ROLE, current_path)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsDropEnabled
            )
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
                        item.setFlags(
                            item.flags()
                            | Qt.ItemFlag.ItemIsDragEnabled
                            | Qt.ItemFlag.ItemIsDropEnabled
                        )
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
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr('Select'))
        layout.addWidget(self.buttons)

        self.search_edit.textChanged.connect(self._filter_tree)
        self.tree.itemDoubleClicked.connect(lambda _item, _column: self.accept())
        self.tree.currentItemChanged.connect(self._update_accept_state)
        self.tree.currentItemChanged.connect(self._update_edit_state)
        self.add_act_button.clicked.connect(lambda: self._add_structure("act"))
        self.add_chapter_button.clicked.connect(lambda: self._add_structure("chapter"))
        self.add_scene_button.clicked.connect(lambda: self._add_structure("scene"))
        self.rename_button.clicked.connect(self._rename_structure)
        self.remove_button.clicked.connect(self._remove_structure)
        self.tree.structureDropped.connect(self._persist_tree_move)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self._update_accept_state(self.tree.currentItem())
        self._update_edit_state(self.tree.currentItem())

    def _find_project_manager(self):
        widget = self.parentWidget()
        while widget is not None:
            manager = getattr(widget, "project_manager", None)
            if manager is not None:
                return manager
            widget = widget.parentWidget()
        return None

    def _main_window(self):
        widget = self.parentWidget()
        while widget is not None:
            if hasattr(widget, "ui_updater") and hasattr(widget, "project_manager"):
                return widget
            widget = widget.parentWidget()
        return None

    def _update_edit_state(self, item, _previous=None):
        can_edit = bool(
            self._project_manager is not None
            and getattr(self._project_manager, "project", None) is not None
        )
        self.rename_button.setEnabled(can_edit and item is not None and item is not self.none_item)
        self.remove_button.setEnabled(can_edit and item is not None and item is not self.none_item)

    def _add_structure(self, node_type: str):
        project = getattr(self._project_manager, "project", None)
        if project is None:
            return
        title, accepted = QInputDialog.getText(
            self,
            f"Add {node_type.title()}",
            f"{node_type.title()} name:",
        )
        title = title.strip()
        if not accepted or not title:
            return

        parent_item = self.tree.currentItem()
        if parent_item is self.none_item:
            parent_item = None
        parent_id = parent_item.data(0, self.ID_ROLE) if parent_item is not None else None
        parent_path = tuple(parent_item.data(0, self.PATH_ROLE) or ()) if parent_item is not None else ()

        from core.manual_story_structures import add_manual_story_node
        node_id = add_manual_story_node(project, title, node_type, parent_id)
        self._project_manager.save()

        item = QTreeWidgetItem((title, node_type.title()))
        item.setData(0, self.ID_ROLE, node_id)
        item.setData(0, self.PATH_ROLE, parent_path + (title,))
        item.setFlags(
            item.flags()
            | Qt.ItemFlag.ItemIsDragEnabled
            | Qt.ItemFlag.ItemIsDropEnabled
        )
        item.setToolTip(0, " › ".join(parent_path + (title,)))
        if parent_item is None:
            self.tree.addTopLevelItem(item)
        else:
            parent_item.addChild(item)
            parent_item.setExpanded(True)
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        self._structure_changed = True

    def _rename_structure(self):
        item = self.tree.currentItem()
        project = getattr(self._project_manager, "project", None)
        if project is None or item is None or item is self.none_item:
            return
        old_title = item.text(0)
        title, accepted = QInputDialog.getText(
            self,
            "Rename story structure",
            "New name:",
            text=old_title,
        )
        title = title.strip()
        if not accepted or not title or title == old_title:
            return

        old_path = tuple(item.data(0, self.PATH_ROLE) or ())
        new_path = old_path[:-1] + (title,)
        from core.manual_story_structures import rename_story_node, update_assigned_story_paths
        rename_story_node(project, item.data(0, self.ID_ROLE), title)
        update_assigned_story_paths(project, old_path, new_path)
        self._project_manager.save()

        def replace_path(node):
            path = tuple(node.data(0, self.PATH_ROLE) or ())
            if path[:len(old_path)] == old_path:
                path = new_path + path[len(old_path):]
                node.setData(0, self.PATH_ROLE, path)
                node.setToolTip(0, " › ".join(path))
            for index in range(node.childCount()):
                replace_path(node.child(index))

        item.setText(0, title)
        replace_path(item)
        self._structure_changed = True

    def _real_top_level_items(self):
        return [
            self.tree.topLevelItem(index)
            for index in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(index) is not self.none_item
        ]

    def _refresh_paths_and_positions(self):
        positions = []

        def visit(item, parent_id, parent_path, order):
            title = item.text(0)
            path = parent_path + (title,)
            item.setData(0, self.PATH_ROLE, path)
            item.setToolTip(0, " › ".join(path))
            node_id = item.data(0, self.ID_ROLE)
            if node_id is not None:
                positions.append((node_id, parent_id, order))
            child_parent_id = node_id if node_id is not None else parent_id
            for child_order in range(item.childCount()):
                visit(item.child(child_order), child_parent_id, path, child_order)

        for root_order, item in enumerate(self._real_top_level_items()):
            visit(item, None, (), root_order)
        return positions

    def _persist_tree_move(self, item, old_path):
        project = getattr(self._project_manager, "project", None)
        if project is None or item is None or item is self.none_item:
            return
        from core.manual_story_structures import (
            set_story_node_positions,
            update_assigned_story_paths,
        )

        positions = self._refresh_paths_and_positions()
        new_path = tuple(item.data(0, self.PATH_ROLE) or ())
        set_story_node_positions(project, positions)
        if tuple(old_path or ()) != new_path:
            update_assigned_story_paths(project, old_path, new_path)
        self._project_manager.save()
        self._structure_changed = True

    def _remove_structure(self):
        item = self.tree.currentItem()
        project = getattr(self._project_manager, "project", None)
        if project is None or item is None or item is self.none_item:
            return
        answer = QMessageBox.question(
            self,
            tr('Remove story structure'),
            f"Remove '{item.text(0)}' and all structures below it?\n\n"
            "Strings assigned to this branch will be moved to No chapter.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        node_ids = []
        paths = []

        def collect(node):
            node_id = node.data(0, self.ID_ROLE)
            if node_id is not None:
                node_ids.append(node_id)
            paths.append(tuple(node.data(0, self.PATH_ROLE) or ()))
            for index in range(node.childCount()):
                collect(node.child(index))

        collect(item)
        from core.manual_story_structures import remove_story_nodes
        remove_story_nodes(project, node_ids, paths)
        parent = item.parent()
        if parent is None:
            index = self.tree.indexOfTopLevelItem(item)
            self.tree.takeTopLevelItem(index)
            next_item = self.none_item
        else:
            parent.takeChild(parent.indexOfChild(item))
            next_item = parent
        self.tree.setCurrentItem(next_item)
        self._refresh_paths_and_positions()
        self._project_manager.save()
        self._structure_changed = True

    def done(self, result):
        if self._structure_changed:
            main_window = self._main_window()
            block_updater = getattr(
                getattr(main_window, "ui_updater", None), "block_list_updater", None
            )
            invalidate = getattr(block_updater, "invalidate_mempalace_story_cache", None)
            if callable(invalidate):
                invalidate()
            populate = getattr(block_updater, "populate_blocks", None)
            if callable(populate):
                QTimer.singleShot(0, populate)
        super().done(result)

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
        self.addItem(tr('No chapter'), None)

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
