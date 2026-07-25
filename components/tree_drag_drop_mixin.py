# components/tree_drag_drop_mixin.py
"""Drag-and-drop mixin for CustomTreeWidget."""
from PyQt6.QtCore import Qt, QPoint, QTimer, QSignalBlocker
from PyQt6.QtGui import QDrag, QFontMetrics, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QTreeWidgetItemIterator

from utils.logging_utils import log_debug


class TreeDragDropMixin:
    """Custom drag-and-drop logic: visual pixmap, above/on/below drop positions."""

    @staticmethod
    def _event_point(event):
        """Return an integer viewport point for Qt 6 and older compatible events."""
        position = event.position() if hasattr(event, "position") else event.pos()
        return position.toPoint() if hasattr(position, "toPoint") else position

    @staticmethod
    def _story_assignment_target(item):
        """Return the editable Story facet represented by a virtual tree leaf."""
        if item is None:
            return None
        if item.data(0, Qt.UserRole + 17) == "unbound":
            return "all", "None", ()
        kind = item.data(0, Qt.UserRole)
        if kind == -2:
            value = item.data(0, Qt.UserRole + 11)
            if value is not None:
                path = []
                cursor = item
                while cursor is not None:
                    if cursor.data(0, Qt.UserRole) == -2:
                        label = cursor.text(0).strip()
                        if label and label != "None":
                            path.append(label)
                    cursor = cursor.parent()
                return "story", value, tuple(reversed(path))
        if kind == -3:
            value = item.data(0, Qt.UserRole + 15)
            if value is not None:
                return "speaker", value, ()
        if kind == -4:
            value = item.data(0, Qt.UserRole + 16)
            if value is not None:
                return "item", value, ()
        return None

    def _selected_editor_assignment_rows(self):
        """Resolve the current multi-line editor selection to physical game rows."""
        main_window = self.window()
        store = getattr(main_window, "data_store", None)
        if store is None:
            return []
        selected = list(getattr(store, "selected_string_indices", []) or [])
        rows = []
        physical_block = getattr(store, "physical_block_idx", -1)
        if physical_block is None or physical_block < 0:
            physical_block = getattr(store, "current_block_idx", -1)
        for value in selected:
            if isinstance(value, (tuple, list)) and len(value) == 2:
                row = (int(value[0]), int(value[1]))
            elif physical_block is not None and physical_block >= 0:
                row = (int(physical_block), int(value))
            else:
                continue
            if row not in rows:
                rows.append(row)
        return rows

    def _dragged_assignment_rows(self, source_items=None, external=False):
        """Resolve editor lines or dragged tree nodes to physical game rows."""
        if external:
            return self._selected_editor_assignment_rows()
        rows = []
        seen = set()

        def collect_item(item):
            mappings = item.data(0, Qt.UserRole + 13)
            if isinstance(mappings, (list, tuple)):
                for value in mappings:
                    if isinstance(value, (list, tuple)) and len(value) == 2:
                        row = (int(value[0]), int(value[1]))
                        if row not in seen:
                            seen.add(row)
                            rows.append(row)
            for child_idx in range(item.childCount()):
                collect_item(item.child(child_idx))

        for item in source_items or []:
            collect_item(item)
        if rows:
            return rows
        selected_by_block = getattr(self, "_get_selected_strings_by_block", lambda: {})()
        for block_idx, string_indices in selected_by_block.items():
            for string_idx in string_indices:
                row = (int(block_idx), int(string_idx))
                if row not in seen:
                    seen.add(row)
                    rows.append(row)
        return rows

    @staticmethod
    def _virtual_item_locator(item):
        """Capture a stable path to an auto-generated virtual tree item."""
        path = []
        cursor = item
        while cursor is not None:
            path.append((
                cursor.text(0),
                cursor.data(0, Qt.UserRole),
                cursor.data(0, Qt.UserRole + 11),
                cursor.data(0, Qt.UserRole + 15),
                cursor.data(0, Qt.UserRole + 16),
                cursor.data(0, Qt.UserRole + 17),
                cursor.data(0, Qt.UserRole + 19),
            ))
            cursor = cursor.parent()
        return tuple(reversed(path))

    def _restore_virtual_item_locator(self, locator):
        """Restore selection and expansion after the virtual tree is rebuilt."""
        if not locator:
            return False
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if self._virtual_item_locator(item) == locator:
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
                self.setCurrentItem(item)
                item.setSelected(True)
                self.scrollToItem(item)
                return True
            iterator += 1
        return False

    def _assign_rows_to_story_target(self, rows, target_item):
        """Persist a forced Story/Speaker/Item assignment for several game rows."""
        target = self._story_assignment_target(target_item)
        if not target or not rows:
            return False
        facet, value, path = target
        return self._assign_rows_to_story_context(
            rows,
            facet,
            value,
            path,
            target_item.text(0),
            self._virtual_item_locator(target_item),
        )

    def _assign_rows_to_story_context(
        self,
        rows,
        facet,
        value,
        path=(),
        target_label=None,
        target_locator=None,
    ):
        """Persist one chosen Memory Palace facet for several game rows."""
        if facet not in {"story", "speaker", "item", "all"} or not rows:
            return False
        main_window = self.window()
        manager = getattr(main_window, "project_manager", None)
        if manager is None or getattr(manager, "project", None) is None:
            return False

        target_label = target_label or str(value)
        source_locator = self._virtual_item_locator(self.currentItem())
        source_rows = []
        continuation_row = None
        if self.currentItem() is not None:
            source_rows = [
                tuple(row) for row in (self.currentItem().data(0, Qt.UserRole + 13) or ())
                if isinstance(row, (tuple, list)) and len(row) == 2
            ]
            removed = set(rows)
            positions = [index for index, row in enumerate(source_rows) if row in removed]
            if positions:
                data_processor = getattr(main_window, "data_processor", None)

                def is_row_non_empty(row):
                    if not data_processor:
                        return True
                    try:
                        text, _ = data_processor.get_current_string_text(row[0], row[1])
                        if not text:
                            return False
                        from utils.utils import remove_all_tags
                        return bool(remove_all_tags(text).strip())
                    except Exception:
                        return True

                # 1. Search downwards for a non-empty surviving row
                continuation_row = next(
                    (row for row in source_rows[max(positions) + 1:] if row not in removed and is_row_non_empty(row)),
                    None,
                )
                # 2. Search upwards for a non-empty surviving row
                if continuation_row is None:
                    continuation_row = next(
                        (row for row in reversed(source_rows[:min(positions)]) if row not in removed and is_row_non_empty(row)),
                        None,
                    )
                # 3. Fallback: Search downwards for any surviving row
                if continuation_row is None:
                    continuation_row = next(
                        (row for row in source_rows[max(positions) + 1:] if row not in removed),
                        None,
                    )
                # 4. Fallback: Search upwards for any surviving row
                if continuation_row is None:
                    continuation_row = next(
                        (row for row in reversed(source_rows[:min(positions)]) if row not in removed),
                        None,
                    )
        preserve_source = continuation_row is not None
        restore_locator = source_locator if preserve_source else target_locator
        undo_mgr = getattr(main_window, "undo_manager", None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None
        from core.story_context_overrides import update_story_context_override

        changed = 0
        for block_idx, string_idx in rows:
            if facet == "story":
                changes = {
                    "structure_id": value,
                    "structure_path": list(path) if value != "story:none" else [],
                }
            elif facet == "speaker":
                changes = {"speaker": str(value or "None")}
            elif facet == "item":
                changes = {"item": str(value or "None")}
            else:
                changes = {
                    "structure_id": "story:none",
                    "structure_path": [],
                    "speaker": "None",
                    "item": "None",
                    "translator_note": None,
                    "notated": None,
                }
            if update_story_context_override(
                main_window, block_idx, string_idx, **changes
            ):
                changed += 1
        if not changed:
            return False

        manager.save()
        if undo_mgr and before is not None:
            undo_mgr.record_structural_action(
                before,
                "ASSIGN_STORY_CONTEXT",
                f"Change {facet} context for {changed} string(s): {target_label}",
            )
        updater = getattr(getattr(main_window, "ui_updater", None), "block_list_updater", None)
        if updater is not None:
            def restore_source_and_row():
                try:
                    from PyQt6 import sip
                    if sip.isdeleted(self):
                        return False
                except (ImportError, TypeError, RuntimeError):
                    pass
                if not restore_locator:
                    return False

                selection_handler = getattr(main_window, "list_selection_handler", None)

                # Re-select the source leaf without re-emitting currentItemChanged;
                # we drive the block load explicitly below so the flow is
                # deterministic regardless of Qt's signal timing.
                blocker = QSignalBlocker(self)
                restored = bool(self._restore_virtual_item_locator(restore_locator))
                del blocker
                if not restored:
                    return False

                if not (preserve_source and continuation_row is not None):
                    # Fall back to the destination view (nothing survived in the
                    # source leaf); mirror the plain locator restore behaviour.
                    if selection_handler is not None:
                        item = self.currentItem()
                        if item is not None:
                            selection_handler.block_selected(item, None)
                    return True

                item = self.currentItem()
                if item is None or selection_handler is None:
                    return True

                # Rebuild the source leaf's view synchronously so its filtered
                # preview (displayed_string_indices) is up to date.
                selection_handler.block_selected(item, None)

                # Then land the cursor on the continuation row using its position
                # in the *displayed* preview, not the raw mapping index — the two
                # diverge when filters such as "Hide empty strings" are active.
                target_row = (int(continuation_row[0]), int(continuation_row[1]))

                def reveal_continuation():
                    try:
                        from PyQt6 import sip
                        if sip.isdeleted(self):
                            return
                    except (ImportError, TypeError, RuntimeError):
                        pass
                    self._reveal_preview_row(target_row)

                QTimer.singleShot(0, reveal_continuation)
                return True

            def refresh_and_restore_target():
                try:
                    from PyQt6 import sip
                except ImportError:
                    import sip
                try:
                    if sip.isdeleted(self):
                        return
                except (TypeError, RuntimeError):
                    return
                updater.populate_blocks()
                try:
                    restored = restore_source_and_row()
                    if (
                        not restored
                        and getattr(updater, "_is_loading_chapters", False)
                    ):
                        when_ready = getattr(updater, "when_virtual_blocks_ready", None)
                        if callable(when_ready):
                            when_ready(restore_source_and_row)
                except (TypeError, RuntimeError):
                    return

            QTimer.singleShot(0, refresh_and_restore_target)
        status_bar = getattr(main_window, "statusBar", None)
        if callable(status_bar):
            status_bar().showMessage(
                f"Changed {facet} context for {changed} string(s): {target_label}", 5000
            )
        return True

    def _reveal_preview_row(self, row):
        """Select and scroll the preview to a physical (block, string) row.

        Resolves the row against the *displayed* (filtered) preview lines so the
        cursor lands correctly even when preview filters hide some strings. If the
        exact row is filtered out, the nearest still-visible row is used instead.
        """
        main_window = self.window()
        selection_handler = getattr(main_window, "list_selection_handler", None)
        if selection_handler is None:
            return

        rel = -1
        get_relative = getattr(selection_handler, "_get_relative_index", None)
        if callable(get_relative):
            try:
                rel = int(get_relative(row))
            except (TypeError, ValueError):
                rel = -1

        if rel == -1:
            displayed = list(
                getattr(main_window.data_store, "displayed_string_indices", []) or []
            )
            visible = [
                (index, value)
                for index, value in enumerate(displayed)
                if isinstance(value, (tuple, list)) and len(value) == 2
            ]
            after = [index for index, value in visible if tuple(value) >= row]
            before = [index for index, value in visible if tuple(value) < row]
            if after:
                rel = after[0]
            elif before:
                rel = before[-1]

        if rel != -1:
            selection_handler.string_selected_from_preview(rel)

    def _set_notes_for_rows(self, rows, note, restore_locator=None):
        """Persist or clear a translator note for several game rows."""
        if not rows:
            return False
        main_window = self.window()
        manager = getattr(main_window, "project_manager", None)
        if manager is None or getattr(manager, "project", None) is None:
            return False
        note = str(note or "").strip()
        undo_mgr = getattr(main_window, "undo_manager", None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None
        from core.story_context_overrides import update_story_context_override

        changed = sum(
            bool(update_story_context_override(
                main_window,
                block_idx,
                string_idx,
                translator_note=note or None,
                notated=True if note else None,
            ))
            for block_idx, string_idx in rows
        )
        if not changed:
            return False
        manager.save()
        if undo_mgr and before is not None:
            undo_mgr.record_structural_action(
                before,
                "ASSIGN_STORY_CONTEXT",
                f"{'Add' if note else 'Remove'} notes for {changed} string(s)",
            )
        updater = getattr(getattr(main_window, "ui_updater", None), "block_list_updater", None)
        if updater is not None:
            updater.populate_blocks()
            if restore_locator:
                self._restore_virtual_item_locator(restore_locator)
        data_processor = getattr(main_window, "data_processor", None)
        if data_processor is not None:
            data_processor.schedule_autosave()
        status_bar = getattr(main_window, "statusBar", None)
        if callable(status_bar):
            status_bar().showMessage(
                f"{'Added' if note else 'Removed'} notes for {changed} string(s)", 5000
            )
        return True

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
        from PyQt6.QtCore import QRect
        rect = QRect(0, 0, fm.horizontalAdvance(text) + 20, fm.height() + 10)

        pixmap = QPixmap(rect.size())
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(0, 120, 215, 200))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(pixmap.rect(), 4, 4)
            painter.setPen(Qt.GlobalColor.white)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        finally:
            painter.end()

        drag = QDrag(self)
        drag.setMimeData(self.mimeData(self._pending_drag_items))
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        drag.exec(supportedActions)

    def dragEnterEvent(self, event):
        """Accept selected game-string lines dragged from the Strings editor."""
        if event.mimeData().hasFormat("application/x-selected-lines"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """Dragmoveevent."""
        is_editor_drag = event.mimeData().hasFormat("application/x-selected-lines")
        if not is_editor_drag:
            super().dragMoveEvent(event)
        self._custom_drop_target = None
        event_point = self._event_point(event)
        item = self.itemAt(event_point)

        if self._story_assignment_target(item):
            self._custom_drop_target = (item, "On")
            event.acceptProposedAction()
        elif not is_editor_drag and item and (item.data(0, Qt.UserRole) is not None or item.data(0, Qt.UserRole + 1) is not None):
            rect = self.visualItemRect(item)
            pct = (event_point.y() - rect.top()) / max(rect.height(), 1)
            pos = "Above" if pct < 0.2 else ("Below" if pct > 0.8 else "On")
            self._custom_drop_target = (item, pos)
            event.acceptProposedAction()

        self.viewport().update()

    def dragLeaveEvent(self, event):
        """Dragleaveevent."""
        self._custom_drop_target = None
        super().dragLeaveEvent(event)
        self.viewport().update()

    def dropEvent(self, event):
        """Dropevent."""
        target_info = getattr(self, '_custom_drop_target', None)
        drop_item = self.itemAt(self._event_point(event))
        # Qt may clear/change the hover state between dragMoveEvent and dropEvent.
        # Re-resolve semantic assignment targets at the actual release point.
        if self._story_assignment_target(drop_item):
            target_info = (drop_item, "On")
        self._custom_drop_target = None
        self.viewport().update()

        main_window = self.window()
        undo_mgr = getattr(main_window, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None

        selected_items = self.selectedItems()
        drag_source_items = self._pending_drag_items or selected_items

        is_editor_drag = event.mimeData().hasFormat("application/x-selected-lines")
        if target_info and self._story_assignment_target(target_info[0]):
            target_item, drop_pos = target_info
            rows = self._dragged_assignment_rows(
                drag_source_items, external=is_editor_drag
            )
            if drop_pos == "On" and self._assign_rows_to_story_target(rows, target_item):
                event.acceptProposedAction()
            else:
                event.ignore()
            self._pending_drag_items = []
            return

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
        target_item = self.itemAt(self._event_point(event))
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
