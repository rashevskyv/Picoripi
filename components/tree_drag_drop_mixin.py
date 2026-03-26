# components/tree_drag_drop_mixin.py
"""Drag-and-drop mixin for CustomTreeWidget."""
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QDrag, QFontMetrics, QPixmap, QPainter, QColor
from PyQt5.QtWidgets import QTreeWidgetItemIterator

from utils.logging_utils import log_debug


class TreeDragDropMixin:
    """Custom drag-and-drop logic: visual pixmap, above/on/below drop positions."""

    def startDrag(self, supportedActions):
        """Capture selected items BEFORE Qt can change hover/current state."""
        self._pending_drag_items = list(self.selectedItems())

        if not self._pending_drag_items:
            return

        self._custom_drop_target = None
        self.setDropIndicatorShown(False)

        # Build a compact semi-transparent drag pixmap
        text = self._pending_drag_items[0].text(0).split(" (")[0][:30]
        if len(text) == 30:
            text += "..."
        if len(self._pending_drag_items) > 1:
            text += f" (+{len(self._pending_drag_items) - 1})"

        font = self.font()
        fm = QFontMetrics(font)
        from PyQt5.QtCore import QRect
        rect = QRect(0, 0, fm.horizontalAdvance(text) + 20, fm.height() + 10)

        pixmap = QPixmap(rect.size())
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(0, 120, 215, 200))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(pixmap.rect(), 4, 4)
        painter.setPen(Qt.white)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, text)
        painter.end()

        drag = QDrag(self)
        drag.setMimeData(self.mimeData(self._pending_drag_items))
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        drag.exec_(supportedActions)

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        self._custom_drop_target = None
        item = self.itemAt(event.pos())

        if item and (item.data(0, Qt.UserRole) is not None or item.data(0, Qt.UserRole + 1) is not None):
            rect = self.visualItemRect(item)
            pct = (event.pos().y() - rect.top()) / max(rect.height(), 1)
            pos = "Above" if pct < 0.2 else ("Below" if pct > 0.8 else "On")
            self._custom_drop_target = (item, pos)
            event.acceptProposedAction()

        self.viewport().update()

    def dragLeaveEvent(self, event):
        self._custom_drop_target = None
        super().dragLeaveEvent(event)
        self.viewport().update()

    def dropEvent(self, event):
        target_info = getattr(self, '_custom_drop_target', None)
        self._custom_drop_target = None
        self.viewport().update()

        main_window = self.window()
        undo_mgr = getattr(main_window, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None

        selected_items = self.selectedItems()
        drag_source_items = self._pending_drag_items or selected_items

        if target_info and drag_source_items:
            target_item, drop_pos = target_info
            valid_source_items = [i for i in drag_source_items if i != target_item]

            if not valid_source_items:
                super().dropEvent(event)
                QTimer.singleShot(0, self.sync_tree_to_project_manager)
                self._pending_drag_items = []
                return

            pm = main_window.project_manager
            if not pm or not pm.project:
                super().dropEvent(event)
                self._pending_drag_items = []
                return

            first_drag_item = valid_source_items[0]
            sel_b_idx = first_drag_item.data(0, Qt.UserRole)
            sel_f_id = first_drag_item.data(0, Qt.UserRole + 1)

            undo_mgr_label = 'Drag-drop reorder'

            if drop_pos == "On":
                target_b_idx = target_item.data(0, Qt.UserRole)
                target_f_id = target_item.data(0, Qt.UserRole + 1)
                block_map = getattr(main_window, 'block_to_project_file_map', {})

                if target_b_idx is not None:
                    # Drop on block → create new folder and group
                    folder_name = self._get_next_unnamed_name(pm)
                    target_parent_id = (
                        target_item.parent().data(0, Qt.UserRole + 1)
                        if target_item.parent() else None
                    )
                    new_folder = pm.create_virtual_folder(folder_name, parent_id=target_parent_id)
                    proj_b_idx = block_map.get(target_b_idx, target_b_idx)
                    if proj_b_idx < len(pm.project.blocks):
                        pm.move_block_to_folder(pm.project.blocks[proj_b_idx].id, new_folder.id)
                    for drag_item in valid_source_items:
                        b = drag_item.data(0, Qt.UserRole)
                        f = drag_item.data(0, Qt.UserRole + 1)
                        if b is not None:
                            pi = block_map.get(b, b)
                            if pi < len(pm.project.blocks):
                                pm.move_block_to_folder(pm.project.blocks[pi].id, new_folder.id)
                        elif f:
                            pm.move_folder_to_folder(f, new_folder.id)
                    undo_mgr_label = f"Group into '{folder_name}'"

                elif target_f_id is not None:
                    # Drop on folder → move into it
                    for drag_item in valid_source_items:
                        b = drag_item.data(0, Qt.UserRole)
                        f = drag_item.data(0, Qt.UserRole + 1)
                        if b is not None:
                            pi = block_map.get(b, b)
                            if pi < len(pm.project.blocks):
                                pm.move_block_to_folder(pm.project.blocks[pi].id, target_f_id)
                        elif f:
                            pm.move_folder_to_folder(f, target_f_id)
                    undo_mgr_label = f"Move into '{target_item.text(0)}'"

                source_parent = drag_source_items[0].parent() if drag_source_items else None
                if source_parent and target_item != source_parent:
                    self.setCurrentItem(source_parent)

            else:  # "Above" or "Below"
                nodes = []
                ordered = reversed(valid_source_items) if drop_pos == "Above" else valid_source_items
                for item in ordered:
                    p = item.parent() or self.invisibleRootItem()
                    nodes.append(p.takeChild(p.indexOfChild(item)))

                parent_item = target_item.parent() or self.invisibleRootItem()
                target_index = parent_item.indexOfChild(target_item)
                insert_index = target_index if drop_pos == "Above" else target_index + 1
                for node in nodes:
                    parent_item.insertChild(insert_index, node)

                source_parent = drag_source_items[0].parent() if drag_source_items else None
                if source_parent and parent_item != source_parent:
                    self.setCurrentItem(source_parent)

                self.sync_tree_to_project_manager()
                QTimer.singleShot(
                    0,
                    lambda: main_window.ui_updater.populate_blocks(
                        override_folder_id=sel_f_id, override_block_idx=sel_b_idx
                    ),
                )
                event.accept()
                if undo_mgr and before is not None:
                    undo_mgr.record_structural_action(before, 'DRAG_DROP', undo_mgr_label)
                self._pending_drag_items = []
                return

            pm.save()
            QTimer.singleShot(
                0,
                lambda: main_window.ui_updater.populate_blocks(
                    override_folder_id=sel_f_id, override_block_idx=sel_b_idx
                ),
            )
            event.accept()
            if undo_mgr and before is not None:
                undo_mgr.record_structural_action(before, 'DRAG_DROP', undo_mgr_label)
            self._pending_drag_items = []
            return

        # ── Fallback: drop on empty space → append to root ──────────────────
        target_item = self.itemAt(event.pos())
        selected_items = self.selectedItems()
        main_window = self.window()
        undo_mgr = getattr(main_window, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None
        drag_source_items = self._pending_drag_items or selected_items

        root = self.invisibleRootItem()
        nodes = []
        for item in drag_source_items:
            p = item.parent() or root
            nodes.append(p.takeChild(p.indexOfChild(item)))
        for node in nodes:
            root.addChild(node)

        self.sync_tree_to_project_manager()
        pm = getattr(main_window, 'project_manager', None)
        if pm:
            pm.save()
        QTimer.singleShot(0, main_window.ui_updater.populate_blocks)
        event.accept()
        if undo_mgr and before is not None:
            undo_mgr.record_structural_action(before, 'DRAG_DROP', 'Drag-drop reorder')
        self._pending_drag_items = []
