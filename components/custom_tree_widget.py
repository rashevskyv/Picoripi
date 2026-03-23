# --- START OF FILE components/custom_tree_widget.py ---
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu, QAction, QMessageBox, QTreeWidgetItemIterator, QApplication, QInputDialog, QToolTip
from PyQt5.QtCore import Qt, QPoint, QEvent, QTimer, QRect
from PyQt5.QtGui import QColor, QIcon, QPixmap, QPainter, QDrag, QFontMetrics
from pathlib import Path

from utils.logging_utils import log_debug, log_error

class CustomTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.viewport().setMouseTracking(True)
        self.setMouseTracking(True)
        self._is_programmatic_expansion = False
        
        # Enable tooltips
        self.setAttribute(Qt.WA_AlwaysShowToolTips)
        self.viewport().setAttribute(Qt.WA_AlwaysShowToolTips)
        
        from .custom_list_item_delegate import CustomListItemDelegate
        self.setItemDelegate(CustomListItemDelegate(self))
        self.setIndentation(15)
        
        self.setHeaderHidden(True)
        self.setSelectionMode(QTreeWidget.ExtendedSelection)
        
        # Drag and Drop support
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.InternalMove)
        
        from PyQt5.QtWidgets import QHeaderView
        self.header().setStretchLastSection(True)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Snapshot of dragged items captured at startDrag() before Qt can change selection.
        self._pending_drag_items = []
        self._custom_drop_target = None
        self.setDropIndicatorShown(False)

        # Ensure the selected item retains a prominent highlight
        self.setStyleSheet("""
            QTreeWidget::item:selected { background-color: #0078D7; color: white; }
            QTreeWidget::item:selected:!active { background-color: #0078D7; color: white; }
            QTreeView::drop-indicator { color: #0078D7; }
        """)
        
        self.color_marker_definitions = {
            "red": QColor(Qt.red),
            "green": QColor(Qt.green),
            "blue": QColor(Qt.blue),
        }
        
        self.itemExpanded.connect(self._handle_item_state_changed)
        self.itemCollapsed.connect(self._handle_item_state_changed)
        self.itemChanged.connect(self._handle_item_changed)
        
    def mousePressEvent(self, event):
        # If right-clicking on an item that is ALREADY selected,
        # we don't want the default QTreeWidget handler to clear the rest
        # of the selection before popping up the context menu.
        if event.button() == Qt.RightButton:
            item = self.itemAt(event.pos())
            if item and item in self.selectedItems():
                # We just accept the event so the default implementation doesn't run,
                # but we'll still get customContextMenuRequested signal via Qt's own logic
                # or we can let Qt handle the context menu signal and just bypass the selection change.
                # Actually, bypassing it entirely might stop the context menu signal in some Qt versions.
                # A safer way is to save the selection, call super, and restore if needed,
                # BUT QTreeWidget selection mechanism is internal.
                # By not calling super().mousePressEvent(event), we avoid selection reset.
                # However, CustomContextMenu is triggered by QWidget::mouseReleaseEvent or QWidget::contextMenuEvent depending on OS.
                # Let's emit the custom context menu signal directly or wait for contextMenuEvent.
                # Usually returning/accepting here is enough if contextMenuPolicy is Qt.CustomContextMenu.
                # Wait, Qt.CustomContextMenu is triggered by contextMenuEvent which happens after mousePress/Release.
                # If we just accept and return, the right click is consumed and selection isn't cleared.
                event.accept()
                return

        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        log_debug(f"CustomTreeWidget: keyPressEvent key={event.key()}, mods={int(event.modifiers())}")
        is_ctrl = bool(event.modifiers() & Qt.ControlModifier)
        is_alt = bool(event.modifiers() & Qt.AltModifier)
        is_shift = bool(event.modifiers() & Qt.ShiftModifier)

        # Ctrl+PageDown/Up OR Alt+Shift+Up/Down: navigate blocks
        if is_ctrl and not is_alt and not is_shift:
            if event.key() == Qt.Key_PageDown:
                self.navigate_blocks(direction=1)
                event.accept()
                return
            elif event.key() == Qt.Key_PageUp:
                self.navigate_blocks(direction=-1)
                event.accept()
                return

        if is_alt and is_shift and not is_ctrl:
            if event.key() == Qt.Key_Up:
                self.navigate_blocks(direction=-1)
                event.accept()
                return
            elif event.key() == Qt.Key_Down:
                self.navigate_blocks(direction=1)
                event.accept()
                return
            elif event.key() == Qt.Key_Left:
                self.navigate_folders(direction=-1)
                event.accept()
                return
            elif event.key() == Qt.Key_Right:
                self.navigate_folders(direction=1)
                event.accept()
                return

        super().keyPressEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            main_window = self.window()
            if hasattr(main_window, 'handle_zoom'):
                main_window.handle_zoom(event.angleDelta().y(), target='tree')
                event.accept()
                return
        super().wheelEvent(event)

    def navigate_blocks(self, direction):
        log_debug(f"CustomTreeWidget: navigate_blocks direction={direction}")
        current_item = self.currentItem()
        from PyQt5.QtWidgets import QTreeWidgetItemIterator
        iterator = QTreeWidgetItemIterator(self)
        items = []
        current_idx = -1
        
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) is not None:  # It's a block
                items.append(item)
                if current_item and item == current_item:
                    current_idx = len(items) - 1
            iterator += 1

        if not items: return

        if current_idx == -1:
            # Current item is a folder, find the nearest block
            target_idx = 0 if direction > 0 else len(items) - 1
        else:
            target_idx = (current_idx + direction) % len(items)

        target_item = items[target_idx]
        self.setCurrentItem(target_item)
        target_item.setSelected(True)
        self.scrollToItem(target_item)

    def navigate_folders(self, direction):
        log_debug(f"CustomTreeWidget: navigate_folders direction={direction}")
        current_item = self.currentItem()
        from PyQt5.QtWidgets import QTreeWidgetItemIterator
        iterator = QTreeWidgetItemIterator(self)
        items = []
        current_idx = -1
        
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) is None and item.data(0, Qt.UserRole + 1) is not None:  # It's a virtual folder
                items.append(item)
                if current_item and item == current_item:
                    current_idx = len(items) - 1
            iterator += 1

        if not items: return

        if current_idx == -1:
            # Current item is a block, find nearest folder
            target_idx = 0 if direction > 0 else len(items) - 1
        else:
            target_idx = (current_idx + direction) % len(items)

        target_item = items[target_idx]
        self.setCurrentItem(target_item)
        target_item.setSelected(True)
        self.scrollToItem(target_item)

    def _create_color_icon(self, color: QColor, size: int = 12) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen) 
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return QIcon(pixmap)

    def create_item(self, text, block_idx=None, role=Qt.UserRole):
        item = QTreeWidgetItem([text])
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        if block_idx is not None:
            item.setData(0, role, block_idx)
        return item

    def select_block_by_index(self, block_idx: int, category: str = None):
        from PyQt5.QtWidgets import QTreeWidgetItemIterator
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            item_block_idx = item.data(0, Qt.UserRole)
            item_category = item.data(0, Qt.UserRole + 10)
            
            match = False
            if item_block_idx == block_idx:
                if category:
                    if item_category == category:
                        match = True
                else:
                    if item_category is None:
                        match = True
            
            if match:
                self.clearSelection()
                self.setCurrentItem(item)
                item.setSelected(True)
                self.scrollToItem(item)
                return True
            iterator += 1
        return False
    
    def show_context_menu(self, pos: QPoint):
        item = self.itemAt(pos)
        selected_items = self.selectedItems()
        
        # Ensure the clicked item is part of the selection if possible
        if item and item not in selected_items:
            self.setCurrentItem(item)
            item.setSelected(True)
            selected_items = [item]
            
        main_window = self.window()
        from PyQt5.QtWidgets import QMenu, QAction, QStyle
        menu = QMenu(self)

        # 1. "Move to Folder" for batch selection (at least 2 items)
        if len(selected_items) > 1:
            add_to_folder_action = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogNewFolder), f"Move {len(selected_items)} item(s) to folder...")
            if hasattr(main_window, 'project_action_handler') and hasattr(main_window.project_action_handler, 'add_items_to_folder_action'):
                add_to_folder_action.triggered.connect(main_window.project_action_handler.add_items_to_folder_action)
            menu.addSeparator()

        # 2. Global "Import" actions
        if hasattr(main_window, 'project_manager') and main_window.project_manager:
            add_block_action = menu.addAction(self.style().standardIcon(QStyle.SP_FileIcon), "Import Block...")
            if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'import_block_action'):
                add_block_action.triggered.connect(main_window.app_action_handler.import_block_action)

            add_dir_action = menu.addAction(self.style().standardIcon(QStyle.SP_DirIcon), "Import Directory...")
            if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'import_directory_action'):
                add_dir_action.triggered.connect(main_window.app_action_handler.import_directory_action)
            elif hasattr(main_window, 'project_action_handler') and hasattr(main_window.project_action_handler, 'import_directory_action'):
                add_dir_action.triggered.connect(main_window.project_action_handler.import_directory_action)

            menu.addSeparator()

        # Global "Create Folder" if clicking on empty space
        if not item:
            create_folder_action = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogNewFolder), "Create Folder")
            create_folder_action.triggered.connect(self._create_folder_at_cursor)
            menu.exec_(self.mapToGlobal(pos))
            return

        # Set the current index without altering the selection state
        from PyQt5.QtCore import QItemSelectionModel
        self.selectionModel().setCurrentIndex(self.indexFromItem(item), QItemSelectionModel.Current)

        # 3. Handle Item Specific Data
        block_idx = item.data(0, Qt.UserRole)
        folder_id = item.data(0, Qt.UserRole + 1)
        merged_ids = item.data(0, Qt.UserRole + 2) or [] # For compacted items
        compaction_type = item.data(0, Qt.UserRole + 3) # 1: F/F, 2: F/B
        
        pm = getattr(main_window, 'project_manager', None)
        
        # 4. Folder Actions (for single or compacted folders)
        if folder_id or merged_ids:
            # If compacted, we show actions for EACH folder in the chain (FLATTENED)
            if merged_ids and len(merged_ids) > 1:
                for f_idx, f_id in enumerate(merged_ids):
                    folder = pm.find_virtual_folder(f_id) if pm else None
                    if folder:
                        if f_idx > 0: menu.addSeparator()
                        
                        # Show header ONLY if there are multiple folders
                        header = menu.addAction(self.style().standardIcon(QStyle.SP_DirIcon), f"FOLDER: {folder.name}")
                        header.setEnabled(False)
                        
                        rename_folder_action = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Rename Folder...")
                        rename_folder_action.triggered.connect(lambda checked=False, fid=f_id, name=folder.name: self._rename_folder_by_id(fid, name))
                        
                        delete_folder_action = menu.addAction(self.style().standardIcon(QStyle.SP_TrashIcon), "Delete Folder")
                        delete_folder_action.triggered.connect(lambda checked=False, itm=item, fid=f_id: self._delete_folder_by_id(itm, fid))
                        
                        create_folder_action = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogNewFolder), "Create Subfolder...")
                        create_folder_action.triggered.connect(lambda checked=False, fid=f_id: self._create_subfolder_by_id(fid))
                menu.addSeparator()
            else:
                # Single folder or Type 2 (Folder/Block) - treat folder part simply
                f_id_to_use = folder_id or (merged_ids[0] if merged_ids else None)
                folder = pm.find_virtual_folder(f_id_to_use) if (pm and f_id_to_use) else None
                if folder:
                    # For Folder/Block compaction (Type 2), add a header for the folder part
                    if compaction_type == 2:
                        header = menu.addAction(self.style().standardIcon(QStyle.SP_DirIcon), f"FOLDER: {folder.name}")
                        header.setEnabled(False)

                    rename_folder_action = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Rename Folder...")
                    rename_folder_action.triggered.connect(lambda checked=False, fid=folder.id, name=folder.name: self._rename_folder_by_id(fid, name))
                    
                    delete_folder_action = menu.addAction(self.style().standardIcon(QStyle.SP_TrashIcon), "Delete Folder")
                    delete_folder_action.triggered.connect(lambda checked=False, itm=item, fid=folder.id: self._delete_folder_by_id(itm, fid))
                    
                    create_folder_action = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogNewFolder), "Create Subfolder...")
                    create_folder_action.triggered.connect(lambda checked=False, fid=folder.id: self._create_subfolder_by_id(fid))
                    
                    menu.addSeparator()

        # 4b. Category Actions
        category_name = item.data(0, Qt.UserRole + 10)
        if category_name and block_idx is not None:
            cat_header = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogDetailedView), f"VIRTUAL BLOCK: {category_name}")
            cat_header.setEnabled(False)
            
            rename_cat_action = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Rename Virtual Block...")
            rename_cat_action.triggered.connect(lambda checked=False, bidx=block_idx, cname=category_name: main_window.list_selection_handler.rename_category(bidx, cname))
            
            delete_cat_action = menu.addAction(self.style().standardIcon(QStyle.SP_TrashIcon), "Delete Virtual Block")
            delete_cat_action.triggered.connect(lambda checked=False, bidx=block_idx, cname=category_name: main_window.list_selection_handler.delete_category(bidx, cname))
            
            menu.addSeparator()

        # 5. Block Actions (if it's a block or F/B compaction)
        if block_idx is not None:
            block_name = item.text(0)
            if hasattr(main_window, 'data_store') and hasattr(main_window.data_store, 'block_names'):
                 block_name = main_window.data_store.block_names.get(str(block_idx), f"Block {block_idx}")

            # For Folder/Block compaction, add a header for the block part
            if compaction_type == 2:
                header = menu.addAction(self.style().standardIcon(QStyle.SP_FileIcon), f"BLOCK: {block_name}")
                header.setEnabled(False)

            rename_action = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogDetailedView), f"Rename Block")
            if hasattr(main_window, 'list_selection_handler') and hasattr(main_window.list_selection_handler, 'rename_block'):
                rename_action.triggered.connect(lambda checked=False, item_to_rename=item: main_window.list_selection_handler.rename_block(item_to_rename))

            delete_action = menu.addAction(self.style().standardIcon(QStyle.SP_TrashIcon), f"Remove Block")
            if hasattr(main_window, 'project_action_handler') and hasattr(main_window.project_action_handler, 'delete_block_action'):
                delete_action.triggered.connect(lambda checked=False: main_window.project_action_handler.delete_block_action())

            # Specifically requested "Create Folder" for files too
            create_folder_action = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogNewFolder), "Create Folder")
            create_folder_action.triggered.connect(self._create_folder_at_cursor)

            menu.addSeparator()

            reveal_menu = menu.addMenu(self.style().standardIcon(QStyle.SP_DirOpenIcon), "Reveal in Explorer")
            orig_action = reveal_menu.addAction("Original")
            orig_action.triggered.connect(lambda checked=False, idx=block_idx: self._reveal_in_explorer(idx, is_translation=False))
            trans_action = reveal_menu.addAction("Translation")
            trans_action.triggered.connect(lambda checked=False, idx=block_idx: self._reveal_in_explorer(idx, is_translation=True))

            menu.addSeparator()

            marker_definitions = {}
            if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
                marker_definitions = main_window.current_game_rules.get_color_marker_definitions()

            current_markers = main_window.block_handler.get_block_color_markers(block_idx)
            for color_name, q_color in self.color_marker_definitions.items():
                label = marker_definitions.get(color_name, color_name.capitalize())
                action = QAction(self._create_color_icon(q_color), f"Mark '{label}'", menu)
                action.setCheckable(True)
                action.setChecked(color_name in current_markers)
                action.triggered.connect(lambda checked, b_idx=block_idx, c_name=color_name: main_window.block_handler.toggle_block_color_marker(b_idx, c_name))
                menu.addAction(action)

            menu.addSeparator()

            if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'rescan_issues_for_single_block'):
                rescan_action = menu.addAction(self.style().standardIcon(QStyle.SP_BrowserReload), f"Rescan Issues")
                rescan_action.triggered.connect(lambda checked=False, idx=block_idx: main_window.issue_scan_handler.rescan_issues_for_single_block(idx))

            if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'calculate_widths_for_block_action'):
                calc_widths_action = menu.addAction(self.style().standardIcon(QStyle.SP_ComputerIcon), f"Calculate Line Widths")
                calc_widths_action.triggered.connect(lambda checked=False, idx=block_idx, cname=category_name: main_window.app_action_handler.calculate_widths_for_block_action(idx, cname))

            # Spellcheck action
            spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
            if spellchecker_manager and spellchecker_manager.enabled:
                menu.addSeparator()
                spellcheck_action = menu.addAction(self.style().standardIcon(QStyle.SP_DialogHelpButton), f"Spellcheck")
                spellcheck_action.triggered.connect(lambda checked=False, idx=block_idx, cname=category_name: self._open_spellcheck_for_block(idx, cname))

            translator = getattr(main_window, 'translation_handler', None)
            if translator:
                menu.addSeparator()
                progress = translator.translation_progress.get(block_idx)
                if progress and progress['completed_chunks'] and len(progress['completed_chunks']) < progress['total_chunks']:
                    resume_action = menu.addAction(self.style().standardIcon(QStyle.SP_MediaPlay), f"AI: Resume Translation")
                    resume_action.triggered.connect(lambda checked=False, idx=block_idx: translator.resume_block_translation(idx))
                else:
                    action_label = f"AI: Translate Block '{block_name}' (UA)"
                    if category_name:
                        action_label = f"AI: Translate Virtual Block '{category_name}' (UA)"
                        
                    translate_block = menu.addAction(self.style().standardIcon(QStyle.SP_MessageBoxInformation), action_label)
                    translate_block.triggered.connect(lambda checked=False, idx=block_idx, cname=category_name: translator.translate_current_block(idx, cname))

                glossary_label = f"AI: Build Glossary for '{block_name}'"
                if category_name:
                    glossary_label = f"AI: Build Glossary for Virtual Block '{category_name}'"
                    
                generate_glossary = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogContentsView), glossary_label)
                generate_glossary.triggered.connect(lambda checked=False, idx=block_idx, cname=category_name: main_window.build_glossary_with_ai(idx, cname))

            # Revert to Original
            menu.addSeparator()
            selected_items = self.selectedItems()
            selected_block_indices = []
            for s_item in selected_items:
                b_idx = s_item.data(0, Qt.UserRole)
                if b_idx is not None and b_idx not in selected_block_indices:
                    selected_block_indices.append(b_idx)
            
            if len(selected_block_indices) > 1:
                revert_action = menu.addAction(self.style().standardIcon(QStyle.SP_ArrowBack), 
                                              f"Revert {len(selected_block_indices)} selected blocks to original")
                revert_action.triggered.connect(lambda: self._revert_blocks_to_original(selected_block_indices))
            else:
                revert_action = menu.addAction(self.style().standardIcon(QStyle.SP_ArrowBack), 
                                              f"Revert '{block_name}' to original")
                revert_action.triggered.connect(lambda: self._revert_blocks_to_original([block_idx]))

        menu.exec_(self.mapToGlobal(pos))

    def _revert_blocks_to_original(self, block_indices: list[int]):
        main_window = self.window()
        if not hasattr(main_window, 'data_processor'): return
        
        reply = QMessageBox.question(
            self, 'Revert to Original',
            f"Are you sure you want to revert {len(block_indices)} block(s) to their original state?\n\nAll unsaved changes in these blocks will be lost.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No: return
        
        main_window.data_processor.revert_blocks_to_original(block_indices)

    def _handle_item_changed(self, item, column):
        if getattr(self, '_is_programmatic_expansion', False):
            return
            
        new_name = item.text(column)
        folder_id = item.data(column, Qt.UserRole + 1)
        
        if folder_id:
            main_window = self.window()
            pm = getattr(main_window, 'project_manager', None)
            if pm:
                folder = pm.find_virtual_folder(folder_id)
                if folder and folder.name != new_name:
                    log_debug(f"In-place rename folder {folder.name} -> {new_name}")
                    undo_mgr = getattr(main_window, 'undo_manager', None)
                    before = undo_mgr.get_project_snapshot() if undo_mgr else None
                    
                    folder.name = new_name
                    pm.save()
                    
                    if undo_mgr and before is not None:
                        undo_mgr.record_structural_action(before, 'RENAME_FOLDER', f"Rename folder to '{new_name}'")
                    
                    # We might want to refresh to update compaction/counters if needed,
                    # but maybe it's cleaner to wait for next full refresh to avoid loop.
                    # Actually, we should call it because name change might trigger/break compaction.
                    QTimer.singleShot(0, main_window.ui_updater.populate_blocks)

    def _create_folder_at_cursor(self):
        main_window = self.window()
        pm = getattr(main_window, 'project_manager', None)
        if not pm or not pm.project:
            return

        current_item = self.currentItem()
        parent_id = None
        
        if current_item:
            # Check if it's a folder or block
            b_idx = current_item.data(0, Qt.UserRole)
            f_id = current_item.data(0, Qt.UserRole + 1)
            
            if f_id:
                # If a folder is selected, create INSIDE it
                parent_id = f_id
            elif b_idx is not None:
                # If a block is selected, create as SIBLING (same parent)
                parent_item = current_item.parent()
                if parent_item:
                    parent_id = parent_item.data(0, Qt.UserRole + 1)
        
        default_name = self._get_next_unnamed_name(pm)
        
        undo_mgr = getattr(main_window, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None
        
        new_folder = pm.create_virtual_folder(default_name, parent_id=parent_id)
        if new_folder:
            pm.save()
            if undo_mgr and before is not None:
                undo_mgr.record_structural_action(before, 'ADD_FOLDER', f"Add folder '{default_name}'")
            
            # Refresh UI
            main_window.ui_updater.populate_blocks()
            
            # Find the new item and trigger edit mode
            # We need to iterate over the tree to find the item with this folder_id
            from PyQt5.QtWidgets import QTreeWidgetItemIterator
            it = QTreeWidgetItemIterator(self)
            while it.value():
                item = it.value()
                if item.data(0, Qt.UserRole + 1) == new_folder.id:
                    self.setCurrentItem(item)
                    item.setSelected(True)
                    self.scrollToItem(item)
                    # Trigger Rename (using the editItem logic)
                    QTimer.singleShot(100, lambda: self.editItem(item, 0))
                    break
                it += 1

    def _rename_folder(self, item):
        # Trigger in-place edit instead of dialog
        self.editItem(item, 0)

    def _rename_folder_by_id(self, folder_id, current_name):
        # For compacted items, we still need a dialog because there's no single row to edit
        new_name, ok = QInputDialog.getText(self, "Rename Folder", "Enter new folder name:", text=current_name)
        if ok and new_name:
            main_window = self.window()
            undo_mgr = getattr(main_window, 'undo_manager', None)
            before = undo_mgr.get_project_snapshot() if undo_mgr else None
            
            folder = main_window.project_manager.find_virtual_folder(folder_id)
            if folder:
                folder.name = new_name
                main_window.project_manager.save()
                main_window.ui_updater.populate_blocks() # Refresh to update text/compaction
                if undo_mgr and before is not None:
                    undo_mgr.record_structural_action(before, 'RENAME_FOLDER', f"Rename folder to '{new_name}'")

    def _delete_folder_by_id(self, item, folder_id):
        # We need to temporarily set data so the handler knows WHICH folder to delete
        # because the handler currently looks at currentItem().data(UserRole+1)
        old_fid = item.data(0, Qt.UserRole + 1)
        item.setData(0, Qt.UserRole + 1, folder_id)
        self.setCurrentItem(item)
        
        main_window = self.window()
        if hasattr(main_window, 'project_action_handler'):
            main_window.project_action_handler.delete_block_action()
        
        # Restore if item still exists (handler might have deleted it)
        if item is not self.invisibleRootItem():
             item.setData(0, Qt.UserRole + 1, old_fid)

    def _create_subfolder_by_id(self, folder_id):
        main_window = self.window()
        pm = main_window.project_manager
        default_name = self._get_next_unnamed_name(pm)
        new_name, ok = QInputDialog.getText(self, "New Subfolder", "Enter subfolder name:", text=default_name)
        if ok and new_name:
            undo_mgr = getattr(main_window, 'undo_manager', None)
            before = undo_mgr.get_project_snapshot() if undo_mgr else None
            main_window.project_manager.create_virtual_folder(new_name, parent_id=folder_id)
            main_window.ui_updater.populate_blocks()
            if undo_mgr and before is not None:
                undo_mgr.record_structural_action(before, 'ADD_FOLDER', f"Create subfolder '{new_name}'")

    def _delete_folder(self, item):
        self.setCurrentItem(item)
        main_window = self.window()
        if hasattr(main_window, 'project_action_handler'):
            main_window.project_action_handler.delete_block_action()

    def _create_subfolder(self, item):
        folder_id = item.data(0, Qt.UserRole + 1)
        self._create_subfolder_by_id(folder_id)


    def startDrag(self, supportedActions):
        """Capture selected items BEFORE Qt can change hover/current state."""
        self._pending_drag_items = list(self.selectedItems())
        
        if not self._pending_drag_items:
            return
            
        self._custom_drop_target = None
        self.setDropIndicatorShown(False)
        
        # Create a compact, semi-transparent drag pixmap
        text = self._pending_drag_items[0].text(0).split(" (")[0][:30]
        if len(text) == 30: text += "..."
        if len(self._pending_drag_items) > 1:
            text += f" (+{len(self._pending_drag_items)-1})"
            
        font = self.font()
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(text)
        rect = QRect(0, 0, text_width + 20, fm.height() + 10)
        
        pixmap = QPixmap(rect.size())
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Semi-transparent background (blue #0078D7 with 200/255 alpha)
        bg_color = QColor(0, 120, 215, 200)
        painter.setBrush(bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(pixmap.rect(), 4, 4)
        
        # Draw text
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
        
        # Only do custom logic if dropping over a block or folder
        if item and (item.data(0, Qt.UserRole) is not None or item.data(0, Qt.UserRole + 1) is not None):
            rect = self.visualItemRect(item)
            pct = (event.pos().y() - rect.top()) / max(rect.height(), 1)
            
            if pct < 0.2:
                pos = "Above"
            elif pct > 0.8:
                pos = "Below"
            else:
                pos = "On"
                
            self._custom_drop_target = (item, pos)
            event.acceptProposedAction()
            
        self.viewport().update()

    def dragLeaveEvent(self, event):
        self._custom_drop_target = None
        super().dragLeaveEvent(event)
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        target_info = getattr(self, '_custom_drop_target', None)
        if target_info:
            target_item, drop_pos = target_info
            if drop_pos in ("Above", "Below"):
                rect = self.visualItemRect(target_item)
                painter = QPainter(self.viewport())
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#0078D7"))
                
                y = rect.top() if drop_pos == "Above" else rect.bottom()
                painter.drawRect(rect.left(), y - 2, rect.width(), 4) # 4px thick line
                painter.end()

    def dropEvent(self, event):
        target_info = getattr(self, '_custom_drop_target', None)
        self._custom_drop_target = None
        self.viewport().update()
        
        target_item = self.itemAt(event.pos())
        selected_items = self.selectedItems()
        main_window = self.window()
        undo_mgr = getattr(main_window, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None

        drag_source_items = self._pending_drag_items or selected_items
        
        if target_info and drag_source_items:
            target_item, drop_pos = target_info
            
            # Disallow dropping item on itself
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

            # Capture IDs for selecting them after refresh
            first_drag_item = valid_source_items[0]
            sel_b_idx = first_drag_item.data(0, Qt.UserRole)
            sel_f_id = first_drag_item.data(0, Qt.UserRole + 1)

            if drop_pos == "On":
                target_b_idx = target_item.data(0, Qt.UserRole)
                target_f_id = target_item.data(0, Qt.UserRole + 1)
                
                # If target is block, we create folder and group
                if target_b_idx is not None:
                    folder_name = self._get_next_unnamed_name(pm)
                    target_parent_id = target_item.parent().data(0, Qt.UserRole + 1) if target_item.parent() else None
                    new_folder = pm.create_virtual_folder(folder_name, parent_id=target_parent_id)
                    block_map = getattr(main_window, 'block_to_project_file_map', {})

                    proj_b_idx = block_map.get(target_b_idx, target_b_idx)
                    if proj_b_idx < len(pm.project.blocks):
                        pm.move_block_to_folder(pm.project.blocks[proj_b_idx].id, new_folder.id)

                    for drag_item in valid_source_items:
                        b_idx = drag_item.data(0, Qt.UserRole)
                        f_id = drag_item.data(0, Qt.UserRole + 1)
                        if b_idx is not None:
                            proj_idx = block_map.get(b_idx, b_idx)
                            if proj_idx < len(pm.project.blocks):
                                pm.move_block_to_folder(pm.project.blocks[proj_idx].id, new_folder.id)
                        elif f_id:
                            pm.move_folder_to_folder(f_id, new_folder.id)
                    
                    undo_mgr_label = f"Group into '{folder_name}'"
                
                # If target is folder, we move items INTO the folder
                elif target_f_id is not None:
                    block_map = getattr(main_window, 'block_to_project_file_map', {})
                    for drag_item in valid_source_items:
                        b_idx = drag_item.data(0, Qt.UserRole)
                        f_id = drag_item.data(0, Qt.UserRole + 1)
                        if b_idx is not None:
                            proj_idx = block_map.get(b_idx, b_idx)
                            if proj_idx < len(pm.project.blocks):
                                pm.move_block_to_folder(pm.project.blocks[proj_idx].id, target_f_id)
                        elif f_id:
                            pm.move_folder_to_folder(f_id, target_f_id)
                                
                    undo_mgr_label = f"Move into '{target_item.text(0)}'"

            else: # "Above" or "Below"
                # Custom reorder: explicit physical node replacement ensures predictability
                # 1. Take children from tree
                nodes = []
                for item in reversed(valid_source_items) if drop_pos == "Above" else valid_source_items:
                    p = item.parent() or self.invisibleRootItem()
                    nodes.append(p.takeChild(p.indexOfChild(item)))
                
                # 2. Re-evaluate target_index since takeChild might have shifted it
                parent_item = target_item.parent() or self.invisibleRootItem()
                target_index = parent_item.indexOfChild(target_item)
                insert_index = target_index if drop_pos == "Above" else target_index + 1
                
                # 3. Insert manually
                for node in nodes:
                    parent_item.insertChild(insert_index, node)
                
                # If we moved items to a DIFFERENT folder/parent, 
                # keep focus at the SOURCE parent so the user doesn't "jump" away.
                source_parent = drag_source_items[0].parent() if drag_source_items else None
                if source_parent and parent_item != source_parent:
                    self.setCurrentItem(source_parent)
                
                self.sync_tree_to_project_manager()
                QTimer.singleShot(0, lambda: main_window.ui_updater.populate_blocks(override_folder_id=sel_f_id, override_block_idx=sel_b_idx))
                event.accept()
                if undo_mgr and before is not None:
                    undo_mgr.record_structural_action(before, 'DRAG_DROP', 'Drag-drop reorder')
                self._pending_drag_items = []
                return
            
            pm.save()
            
            # For "On" drop: also keep focus at source if it was a folder
            source_parent = drag_source_items[0].parent() if drag_source_items else None
            # (Note: target_item here IS the folder we dropped ON)
            if source_parent and target_item != source_parent:
                self.setCurrentItem(source_parent)

            QTimer.singleShot(0, lambda: main_window.ui_updater.populate_blocks(override_folder_id=sel_f_id, override_block_idx=sel_b_idx))
            event.accept()
            if undo_mgr and before is not None:
                undo_mgr.record_structural_action(before, 'DRAG_DROP', undo_mgr_label)
            self._pending_drag_items = []
            return
        target_item = self.itemAt(event.pos())
        selected_items = self.selectedItems()
        main_window = self.window()
        undo_mgr = getattr(main_window, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None

        drag_source_items = self._pending_drag_items or selected_items
        
        # 2. Default behavior (empty space reorder - append to root)
        root = self.invisibleRootItem()
        nodes = []
        for item in drag_source_items:
            p = item.parent() or root
            nodes.append(p.takeChild(p.indexOfChild(item)))
            
        for node in nodes:
            root.addChild(node)
            
        self.sync_tree_to_project_manager()
        pm.save()
        QTimer.singleShot(0, main_window.ui_updater.populate_blocks)
        event.accept()
        if undo_mgr and before is not None:
            undo_mgr.record_structural_action(before, 'DRAG_DROP', 'Drag-drop reorder')
        self._pending_drag_items = []



    def sync_tree_to_project_manager(self):
        """Update virtual structure in project manager based on current tree layout."""
        main_window = self.window()
        if not hasattr(main_window, 'project_manager') or not main_window.project_manager or not main_window.project_manager.project:
            return
            
        project = main_window.project_manager.project
        
        def rebuild_from_item(tree_item, parent_id=None):
            folder_map = {} # Name -> Folder object for deduplication
            block_ids = []
            
            for i in range(tree_item.childCount()):
                child = tree_item.child(i)
                f_id = child.data(0, Qt.UserRole + 1)
                b_idx = child.data(0, Qt.UserRole)
                merged_ids = child.data(0, Qt.UserRole + 2)
                text = child.text(0)
                
                target_folder = None
                
                if merged_ids and isinstance(merged_ids, list) and len(merged_ids) > 0:
                    # Reconstruct compacted chain
                    parts = text.split(" / ")
                    is_block_item = b_idx is not None
                    folder_names = parts[:-1] if is_block_item else parts
                    
                    curr_p_id = parent_id
                    chain_top = None
                    chain_bottom = None
                    
                    raw_names = child.data(0, Qt.UserRole + 5)
                    
                    for f_idx, folder_id in enumerate(merged_ids):
                        folder_obj = main_window.project_manager.find_virtual_folder(folder_id)
                        new_f_name = None
                        
                        if raw_names and f_idx < len(raw_names):
                            new_f_name = raw_names[f_idx]
                        elif folder_names: # Fallback
                            name_idx = len(folder_names) - 1 - (len(merged_ids) - 1 - f_idx)
                            if name_idx >= 0:
                                import re
                                raw_name = folder_names[name_idx].strip()
                                # Strip the display count [f | b]
                                new_f_name = re.sub(r'\s*\[\d+\s*\|\s*\d+\]$', '', raw_name)
                        
                        if not folder_obj:
                            from core.project_models import VirtualFolder
                            folder_obj = VirtualFolder(id=folder_id, name=new_f_name or "Unnamed Folder", parent_id=curr_p_id)
                        else:
                            if new_f_name:
                                folder_obj.name = new_f_name
                            folder_obj.parent_id = curr_p_id
                        
                        # Sync expansion state from tree
                        folder_obj.is_expanded = child.isExpanded()
                        
                        folder_obj.children = []
                        folder_obj.block_ids = []

                        if not chain_top: chain_top = folder_obj
                        if chain_bottom: chain_bottom.children = [folder_obj]
                        chain_bottom = folder_obj
                        curr_p_id = folder_id

                    if is_block_item:
                        if b_idx < len(project.blocks):
                            chain_bottom.block_ids = [project.blocks[b_idx].id]
                    else:
                        sub_f, sub_b = rebuild_from_item(child, f_id)
                        chain_bottom.children = sub_f
                        chain_bottom.block_ids = sub_b
                    
                    target_folder = chain_top

                elif f_id:
                    # Standard folder
                    folder_obj = main_window.project_manager.find_virtual_folder(f_id)
                    if folder_obj:
                        raw_names = child.data(0, Qt.UserRole + 5)
                        if raw_names and len(raw_names) > 0:
                            folder_obj.name = raw_names[0]
                        else:
                            import re
                            # Strip the display count [f | b]
                            folder_obj.name = re.sub(r'\s*\[\d+\s*\|\s*\d+\]$', '', text)
                        
                        folder_obj.parent_id = parent_id
                        folder_obj.is_expanded = child.isExpanded()
                        folder_obj.children, folder_obj.block_ids = rebuild_from_item(child, f_id)
                        target_folder = folder_obj
                elif b_idx is not None:
                    # Standard block
                    if b_idx < len(project.blocks):
                        block_ids.append(project.blocks[b_idx].id)
                
                # Deduplicate/Merge by name at this level
                if target_folder:
                    if target_folder.name in folder_map:
                        existing = folder_map[target_folder.name]
                        # Merge content
                        existing.children.extend(target_folder.children)
                        existing.block_ids.extend(target_folder.block_ids)
                    else:
                        folder_map[target_folder.name] = target_folder
            
            return list(folder_map.values()), block_ids

        root_item = self.invisibleRootItem()
        project.virtual_folders, root_block_ids = rebuild_from_item(root_item)
        project.metadata['root_block_ids'] = root_block_ids
        
        main_window.project_manager.save()
        log_debug("Virtual folders structure updated.")

    def _handle_item_state_changed(self, item):
        """Toggle expansion state in project manager and refresh UI to update compaction."""
        if getattr(self, '_is_programmatic_expansion', False):
            return
            
        main_window = self.window()
        if not hasattr(main_window, 'project_manager') or not main_window.project_manager.project:
            return
            
        f_id = item.data(0, Qt.UserRole + 1)
        if not f_id: return
        
        folder = main_window.project_manager.find_virtual_folder(f_id)
        if folder:
            is_expanded = item.isExpanded()
            if folder.is_expanded == is_expanded: return # No change
            
            merged_ids = item.data(0, Qt.UserRole + 2) or [f_id]
            log_debug(f"Compacted chain {merged_ids} expansion state changed to {is_expanded}. Syncing...")
            
            for folder_id in merged_ids:
                f_obj = main_window.project_manager.find_virtual_folder(folder_id)
                if f_obj:
                    f_obj.is_expanded = is_expanded
            
            # Save the project state so expansion is persistent
            main_window.project_manager.save()
            
            # Use immediate refresh to avoid "expanding then renaming" flicker
            self.setUpdatesEnabled(False)
            try:
                main_window.ui_updater.populate_blocks()
            finally:
                self.setUpdatesEnabled(True)

    def _get_next_unnamed_name(self, pm) -> str:
        """Generate the next available 'Unnamed N' folder name."""
        if not pm or not pm.project:
            return "Unnamed 1"
        existing = set()
        def collect(folders):
            for f in folders:
                existing.add(f.name)
                collect(f.children)
        collect(pm.project.virtual_folders)
        n = 1
        while f"Unnamed {n}" in existing:
            n += 1
        return f"Unnamed {n}"

    def move_current_item_up(self):
        selected_items = self.selectedItems()
        if not selected_items: return
        
        # Sort items by their current index to move them in order
        items_with_indices = []
        for item in selected_items:
            parent = item.parent() or self.invisibleRootItem()
            items_with_indices.append((parent, parent.indexOfChild(item), item))
        
        # Group by parent and sort by index ascending
        items_with_indices.sort(key=lambda x: x[1])
        
        # Check if the first item can move up
        if items_with_indices[0][1] > 0:
            main_window = self.window()
            undo_mgr = getattr(main_window, 'undo_manager', None)
            before = undo_mgr.get_project_snapshot() if undo_mgr else None
            
            # Move each item up
            for parent, index, item in items_with_indices:
                parent.takeChild(index)
                parent.insertChild(index - 1, item)
            
            # Restore selection (Qt might clear it on takeChild)
            for _, _, item in items_with_indices:
                item.setSelected(True)
            
            if items_with_indices:
                self.setCurrentItem(items_with_indices[0][2])

            self.sync_tree_to_project_manager()
            if undo_mgr and before is not None:
                undo_mgr.record_structural_action(before, 'MOVE_BLOCK_BATCH', f"Move {len(selected_items)} item(s) up")

    def move_current_item_down(self):
        selected_items = self.selectedItems()
        if not selected_items: return
        
        # Sort items by their current index to move them in order
        items_with_indices = []
        for item in selected_items:
            parent = item.parent() or self.invisibleRootItem()
            items_with_indices.append((parent, parent.indexOfChild(item), item))
        
        # Group by parent and sort by index descending (to avoid index shift issues when moving down)
        items_with_indices.sort(key=lambda x: x[1], reverse=True)
        
        # Check if the last item can move down
        last_parent, last_idx, _ = items_with_indices[0]
        if last_idx < last_parent.childCount() - 1:
            main_window = self.window()
            undo_mgr = getattr(main_window, 'undo_manager', None)
            before = undo_mgr.get_project_snapshot() if undo_mgr else None
            
            # Move each item down
            for parent, index, item in items_with_indices:
                parent.takeChild(index)
                parent.insertChild(index + 1, item)
            
            # Restore selection
            for _, _, item in items_with_indices:
                item.setSelected(True)
                
            if items_with_indices:
                self.setCurrentItem(items_with_indices[0][2])

            self.sync_tree_to_project_manager()
            if undo_mgr and before is not None:
                undo_mgr.record_structural_action(before, 'MOVE_BLOCK_BATCH', f"Move {len(selected_items)} item(s) down")

    def event(self, event):
        if event.type() == QEvent.ToolTip:
            log_debug(f"CustomTreeWidget: event() ToolTip received")
        return super().event(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.ToolTip:
            # System ToolTip event
            log_debug(f"CustomTreeWidget: viewport ToolTip event at {event.pos()}")
        elif event.type() == QEvent.MouseMove:
            # Trigger our custom tooltip logic
            index = self.indexAt(event.pos())
            if index.isValid():
                delegate = self.itemDelegate(index)
                if delegate and hasattr(delegate, 'handle_tooltip'):
                    option = self.viewOptions()
                    option.rect = self.visualRect(index)
                    delegate.handle_tooltip(event, self, option, index)
            else:
                QToolTip.hideText()
        return super().viewportEvent(event)

    def _reveal_in_explorer(self, block_idx: int, is_translation: bool = False):
        main_window = self.window()
        if not hasattr(main_window, 'project_manager') or not main_window.project_manager:
            # Fallback for single file mode
            path_to_reveal = main_window.data_store.edited_json_path if is_translation else main_window.data_store.json_path
            if path_to_reveal and Path(path_to_reveal).exists():
                self._open_explorer_at_path(path_to_reveal)
            return
            
        project = main_window.project_manager.project
        if not project:
            return

        # Use mapping if available (for multi-block files), otherwise 1:1
        project_block_idx = block_idx
        if hasattr(main_window, 'block_to_project_file_map'):
            project_block_idx = main_window.block_to_project_file_map.get(block_idx, block_idx)

        if project_block_idx >= len(project.blocks):
            return
            
        block = project.blocks[project_block_idx]
        if is_translation:
            abs_path = main_window.project_manager.get_absolute_path(block.translation_file, is_translation=True)
        else:
            abs_path = main_window.project_manager.get_absolute_path(block.source_file)
        
        if abs_path and Path(abs_path).exists():
            self._open_explorer_at_path(abs_path)

    def _open_explorer_at_path(self, abs_path: str):
        import subprocess
        import platform
        abs_path_obj = Path(abs_path)
        if abs_path_obj.exists():
            if platform.system() == "Windows":
                subprocess.Popen(['explorer', '/select,', str(abs_path_obj)])
            elif platform.system() == "Darwin":
                subprocess.Popen(['open', '-R', str(abs_path_obj)])
            else:
                subprocess.Popen(['xdg-open', str(abs_path_obj.parent)])
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Reveal", f"File not found:\n{abs_path}")

    def _open_spellcheck_for_block(self, block_idx: int, category_name: str = None):
        log_debug(f"CustomTreeWidget: _open_spellcheck_for_block called for block_idx={block_idx}, category={category_name}")

        try:
            main_window = self.window()
            spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)

            if not spellchecker_manager:
                return

            if not hasattr(main_window, 'data_store') or not hasattr(main_window.data_store, 'data') or block_idx >= len(main_window.data_store.data):
                return

            block_data = main_window.data_store.data[block_idx]

            if not isinstance(block_data, list):
                return

            edited_data = getattr(main_window, 'edited_data', {})
            edited_file_data = getattr(main_window, 'edited_file_data', [])

            all_translated_lines = []

            valid_indices = None
            if category_name and hasattr(main_window, 'project_manager') and main_window.project_manager.project:
                project = main_window.project_manager.project
                proj_block_idx = block_idx
                if hasattr(main_window, 'block_to_project_file_map'):
                    proj_block_idx = main_window.block_to_project_file_map.get(block_idx, block_idx)
                if proj_block_idx < len(project.blocks):
                    block = project.blocks[proj_block_idx]
                    for cat in block.categories:
                        if cat.name == category_name:
                            valid_indices = set(cat.line_indices)
                            break

            for string_idx in range(len(block_data)):
                if valid_indices is not None and string_idx not in valid_indices:
                    continue

                key = (block_idx, string_idx)
                text = None

                if key in edited_data:
                    text = edited_data[key]
                elif edited_file_data and block_idx < len(edited_file_data):
                    edited_block = edited_file_data[block_idx]
                    if isinstance(edited_block, list) and string_idx < len(edited_block):
                        text = edited_block[string_idx]

                if text and text.strip():
                    all_translated_lines.append((string_idx, text))

            import re
            word_pattern = re.compile(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ\']+')

            text_parts = []
            line_numbers = []

            for string_idx, text in all_translated_lines:
                text_with_spaces = text.replace('·', ' ')
                has_misspellings = False
                for match in word_pattern.finditer(text_with_spaces):
                    word = match.group(0).strip("'")
                    if word and spellchecker_manager.is_misspelled(word):
                        has_misspellings = True
                        break

                if has_misspellings:
                    text_parts.append(text)
                    subline_count = text.count('\n') + 1
                    for _ in range(subline_count):
                        line_numbers.append(string_idx)

            text_to_check = '\n'.join(text_parts)
            if not text_to_check.strip():
                from PyQt5.QtWidgets import QMessageBox
                if len(all_translated_lines) == 0:
                    QMessageBox.information(self, "Spellcheck", "Немає перекладеного тексту для перевірки.\nСпочатку перекладіть текст у цьому блоці.")
                else:
                    QMessageBox.information(self, "Spellcheck", f"Орфографічні помилки не знайдено!\nПеревірено {len(all_translated_lines)} перекладених рядків.")
                return

            from dialogs.spellcheck_dialog import SpellcheckDialog
            dialog = SpellcheckDialog(self, text_to_check, spellchecker_manager,
                                     starting_line_number=0, line_numbers=line_numbers)

            if dialog.exec_():
                corrected_text = dialog.get_corrected_text()
                corrected_lines = corrected_text.split('\n')

                for i, corrected_line in enumerate(corrected_lines):
                    if i < len(line_numbers):
                        string_idx = line_numbers[i]
                        key = (block_idx, string_idx)
                        if corrected_line != text_parts[i]:
                            edited_data[key] = corrected_line
                            main_window.data_store.unsaved_changes = True
                            if hasattr(main_window, 'unsaved_block_indices'):
                                main_window.data_store.unsaved_block_indices.add(block_idx)

                current_block_idx = getattr(main_window, 'current_block_idx', -1)
                if current_block_idx == block_idx and hasattr(main_window, 'ui_updater'):
                    main_window.ui_updater.populate_strings_for_block(block_idx)
                    main_window.ui_updater.update_text_views()
                    main_window.ui_updater.update_block_item_text_with_problem_count(block_idx)

        except Exception as e:
            log_error(f"CustomTreeWidget: Error in _open_spellcheck_for_block: {e}", exc_info=True)
