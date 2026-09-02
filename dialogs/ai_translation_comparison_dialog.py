# dialogs/ai_translation_comparison_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHBoxLayout, QPushButton, QHeaderView, QMenu, QStyledItemDelegate, QTextEdit
)
from PyQt6.QtCore import Qt, QEvent, QPoint
from PyQt6.QtGui import QColor, QKeyEvent
from core.i18n import tr

class MultilineItemDelegate(QStyledItemDelegate):
    """Custom delegate for multiline text editing in table cells using QTextEdit."""
    def createEditor(self, parent, option, index):
        if index.column() == 2:
            editor = QTextEdit(parent)
            editor.setAcceptRichText(False)
            editor.setObjectName("comparison_editor_text_edit")
            editor.installEventFilter(self)
            
            dialog = self.parent()
            mw = getattr(dialog, 'mw', None)
            if mw:
                from utils.syntax_highlighter import JsonTagHighlighter
                highlighter = JsonTagHighlighter(editor.document(), main_window_ref=mw, editor_widget_ref=editor)
                
                # Load glossary manager to enable glossary highlighting
                gm = None
                if hasattr(mw, 'translation_handler') and mw.translation_handler:
                    gm = getattr(mw.translation_handler, '_glossary_manager', None)
                if gm:
                    highlighter.set_glossary_manager(gm)
                
                # Load spellchecker if enabled globally
                if getattr(mw, 'spellchecker_enabled', True):
                    highlighter.set_spellchecker_enabled(True)
                    
            return editor
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        if isinstance(editor, QTextEdit):
            text = index.model().data(index, Qt.ItemDataRole.EditRole) or ""
            editor.setPlainText(text)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QTextEdit):
            model.setData(index, editor.toPlainText(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)

    def eventFilter(self, editor, event):
        if isinstance(editor, QTextEdit):
            if event.type() == QEvent.Type.KeyPress:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                    self.commitData.emit(editor)
                    self.closeEditor.emit(editor)
                    return True
                elif event.key() == Qt.Key.Key_Escape:
                    self.closeEditor.emit(editor)
                    return True
            elif event.type() == QEvent.Type.FocusOut:
                self.commitData.emit(editor)
                self.closeEditor.emit(editor)
                return True
        return super().eventFilter(editor, event)


class AITranslationComparisonDialog(QDialog):
    """Custom dialog for displaying detailed AI translation comparison in a table format."""
    def __init__(self, parent, translation_details: dict, previous_translations: dict):
        """
        Initialize the dialog.
        translation_details: Dict mapping block_idx (int) -> List of (string_idx (int), translated_text (str))
        previous_translations: Dict mapping block_idx (int) -> List of (string_idx (int), old_text (str))
        """
        from PyQt6.QtWidgets import QWidget
        parent_widget = parent if isinstance(parent, QWidget) else None
        super().__init__(parent_widget)
        
        # Access main window directly
        self.mw = parent
        while self.mw and not hasattr(self.mw, 'data_store') and hasattr(self.mw, 'parentWidget'):
            self.mw = self.mw.parentWidget()
        ds = getattr(self.mw, 'data_store', None)
        
        self.setWindowTitle(tr('AI Translation Comparison'))
        self.setMinimumSize(800, 500)
        self.resize(850, 550)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)
        
        comparison_rows = []
        
        # Build maps for easy lookup
        new_text_map = {}
        for b_idx, items in translation_details.items():
            for s_idx, text in items:
                new_text_map[(b_idx, s_idx)] = text
                
        for b_idx, items in sorted(previous_translations.items()):
            block_name = None
            if ds and hasattr(ds, 'block_names') and ds.block_names:
                block_name = ds.block_names.get(str(b_idx))
            if not block_name:
                if b_idx == -2:
                    block_name = "Chapter Mode"
                elif b_idx == 999999:
                    block_name = "All Blocks Chronological"
                else:
                    block_name = f"Block {b_idx + 1}"
            
            for s_idx, old_text in sorted(items, key=lambda x: x[0]):
                new_text = new_text_map.get((b_idx, s_idx), "")
                location = f"{block_name}\nLine {s_idx + 1}"
                comparison_rows.append((location, old_text, new_text, b_idx, s_idx))
                
        total_rows = len(comparison_rows)
        
        # 1. Summary Label
        summary_text = (
            f"AI translation finished successfully.<br>"
            f"Compared <b>{total_rows}</b> re-translated line(s)."
        )
        self.info_label = QLabel(summary_text, self)
        self.info_label.setTextFormat(Qt.TextFormat.RichText)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        # 2. Table Widget
        self.table_widget = QTableWidget(self)
        self.table_widget.setColumnCount(3)
        self.table_widget.setHorizontalHeaderLabels(["Location", "Old Translation", "New Translation"])
        self.table_widget.setRowCount(total_rows)
        
        # Table configuration
        self.table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_widget.setColumnWidth(0, 180)
        self.table_widget.setWordWrap(True)
        self.table_widget.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        # Set multiline delegate for Column 2
        self.delegate = MultilineItemDelegate(self)
        self.table_widget.setItemDelegateForColumn(2, self.delegate)
        
        self.row_metadata = []
        self.undo_stack = []
        self.redo_stack = []
        self._is_updating_table = False
        
        self.initial_database_states = {}
        if self.mw:
            for loc, old_t, new_t, b_idx, s_idx in comparison_rows:
                val, _ = self.mw.data_processor.get_current_string_text(b_idx, s_idx)
                self.initial_database_states[(b_idx, s_idx)] = val

        for row_idx, (loc, old_t, new_t, b_idx, s_idx) in enumerate(comparison_rows):
            item_loc = QTableWidgetItem(loc)
            item_loc.setFlags(item_loc.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            item_old = QTableWidgetItem(old_t)
            item_old.setFlags(item_old.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            item_new = QTableWidgetItem(new_t)
            item_new.setFlags(item_new.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            
            self.table_widget.setItem(row_idx, 0, item_loc)
            self.table_widget.setItem(row_idx, 1, item_old)
            self.table_widget.setItem(row_idx, 2, item_new)
            
            self.row_metadata.append({
                "block_idx": b_idx,
                "string_idx": s_idx,
                "old_text": old_t,
                "new_text": new_t,
                "current_choice": "new"
            })
            
            self._update_row_highlights(row_idx)
            
        layout.addWidget(self.table_widget)
        
        # Connect signals
        self.table_widget.cellClicked.connect(self._on_cell_clicked)
        self.table_widget.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table_widget.itemChanged.connect(self._on_item_changed)
        self.table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_widget.customContextMenuRequested.connect(self._show_context_menu)
        
        # 3. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.close_btn = QPushButton(tr('OK'), self)
        self.close_btn.setToolTip(
            tr('<b>OK</b><br>Click — accept the table as shown and close (Enter).<br>Double-click a cell to edit it, Ctrl+Enter to commit that edit.<br>Ctrl+Z / Ctrl+Y undo and redo edits while this window is open.')
        )
        self.close_btn.setDefault(True)
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)

    def _update_row_highlights(self, row_idx: int):
        self._is_updating_table = True
        try:
            meta = self.row_metadata[row_idx]
            choice = meta["current_choice"]
            
            active_color = QColor(40, 167, 69, 40)  # light green highlight
            inactive_color = QColor(0, 0, 0, 0)
            
            item_old = self.table_widget.item(row_idx, 1)
            item_new = self.table_widget.item(row_idx, 2)
            
            if item_old and item_new:
                if choice == "old":
                    item_old.setBackground(active_color)
                    item_new.setBackground(inactive_color)
                else:
                    item_old.setBackground(inactive_color)
                    item_new.setBackground(active_color)
        finally:
            self._is_updating_table = False

    def _on_cell_clicked(self, row: int, col: int):
        if col == 0:
            meta = self.row_metadata[row]
            b_idx = meta["block_idx"]
            s_idx = meta["string_idx"]
            if self.mw and hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                entry = {
                    "block_idx": b_idx,
                    "string_idx": s_idx,
                }
                self.mw.translation_handler.ui_handler._activate_entry(entry)
        elif col in (1, 2):
            meta = self.row_metadata[row]
            new_choice = "old" if col == 1 else "new"
            if meta["current_choice"] != new_choice:
                self._save_state()
                meta["current_choice"] = new_choice
                self._update_row_highlights(row)

    def _on_cell_double_clicked(self, row: int, col: int):
        if col in (0, 1):
            meta = self.row_metadata[row]
            b_idx = meta["block_idx"]
            s_idx = meta["string_idx"]
            if self.mw and hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                entry = {
                    "block_idx": b_idx,
                    "string_idx": s_idx,
                }
                self.mw.translation_handler.ui_handler._activate_entry(entry)

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._is_updating_table or item.column() != 2:
            return
            
        row = item.row()
        new_text = item.text()
        meta = self.row_metadata[row]
        if meta["new_text"] != new_text or meta["current_choice"] != "new":
            self._save_state()
            meta["new_text"] = new_text
            meta["current_choice"] = "new"
            self._update_row_highlights(row)

    def _show_context_menu(self, pos: QPoint):
        item = self.table_widget.itemAt(pos)
        if not item or item.column() != 2 or not self.mw:
            return
            
        row = item.row()
        meta = self.row_metadata[row]
        
        menu = QMenu(self)
        edit_action = menu.addAction(tr('Edit Text'))
        var_action = menu.addAction(tr('AI Variations'))
        
        action = menu.exec(self.table_widget.viewport().mapToGlobal(pos))
        if action == edit_action:
            self.table_widget.editItem(item)
        elif action == var_action:
            b_idx = meta["block_idx"]
            s_idx = meta["string_idx"]
            
            self.mw.translation_handler.variations_handler.generate_variation_for_string(
                b_idx, s_idx, force=False,
                on_success_callback=lambda chosen: self._on_variation_chosen(row, chosen),
                parent=self
            )

    def _on_variation_chosen(self, row_idx: int, chosen: str):
        meta = self.row_metadata[row_idx]
        b_idx = meta["block_idx"]
        s_idx = meta["string_idx"]
        
        final_text = self.mw.translation_handler._format_and_wrap_translation(chosen, b_idx, s_idx)
        
        self._save_state()
        self._is_updating_table = True
        try:
            self.table_widget.item(row_idx, 2).setText(final_text)
        finally:
            self._is_updating_table = False
            
        meta["new_text"] = final_text
        meta["current_choice"] = "new"
        self._update_row_highlights(row_idx)

    def _save_state(self):
        import copy
        state = copy.deepcopy(self.row_metadata)
        self.undo_stack.append(state)
        self.redo_stack.clear()

    def _restore_state(self, state):
        self.row_metadata = state
        self._is_updating_table = True
        try:
            for row_idx, meta in enumerate(self.row_metadata):
                item_new = self.table_widget.item(row_idx, 2)
                if item_new:
                    if item_new.text() != meta["new_text"]:
                        item_new.setText(meta["new_text"])
                self._update_row_highlights(row_idx)
        finally:
            self._is_updating_table = False

    def undo(self):
        if not self.undo_stack:
            return
        import copy
        current_state = copy.deepcopy(self.row_metadata)
        self.redo_stack.append(current_state)
        
        previous_state = self.undo_stack.pop()
        self._restore_state(previous_state)

    def redo(self):
        if not self.redo_stack:
            return
        import copy
        current_state = copy.deepcopy(self.row_metadata)
        self.undo_stack.append(current_state)
        
        next_state = self.redo_stack.pop()
        self._restore_state(next_state)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Z and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.undo()
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Y and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.redo()
            event.accept()
            return
        super().keyPressEvent(event)

    def accept(self):
        if self.mw:
            self.mw.undo_manager.begin_group()
            try:
                saved_mgr = getattr(self.mw, 'saved_translations_manager', None)
                bulk_translations = {}
                for meta in self.row_metadata:
                    b_idx = meta["block_idx"]
                    s_idx = meta["string_idx"]
                    choice = meta["current_choice"]
                    text = meta["new_text"] if choice == "new" else meta["old_text"]
                    
                    self.mw.data_processor.update_edited_data(b_idx, s_idx, text, action_type="TRANSLATE", skip_ui_refresh=True)
                    if hasattr(self.mw, 'editor_operation_handler') and self.mw.editor_operation_handler:
                        self.mw.editor_operation_handler._rescan_issues_for_current_string(b_idx, s_idx, text)
                    
                    if choice == "new" and text != meta["old_text"]:
                        bulk_translations.setdefault(b_idx, []).append((s_idx, text))
                        
                if saved_mgr and bulk_translations:
                    for b_idx, items in bulk_translations.items():
                        if b_idx != 999999 and b_idx >= 0:
                            saved_mgr.save_translations_bulk(b_idx, items)
            finally:
                self.mw.undo_manager.end_group("TRANSLATE")
                
            from PyQt6.QtWidgets import QApplication
            changed_blocks = {meta["block_idx"] for meta in self.row_metadata}
            for b_idx in changed_blocks:
                self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)
                if hasattr(self.mw, 'issue_scan_handler'):
                    self.mw.issue_scan_handler.rescan_issues_for_single_block(b_idx, show_message_on_completion=False)
                    
            current_view_block = self.mw.data_store.current_block_idx
            if self.mw.data_store.current_chapter_id is not None:
                current_view_block = -2
            self.mw.ui_updater.populate_strings_for_block(current_view_block, getattr(self.mw.data_store, 'current_category_name', None), force=True)
            self.mw.ui_updater.update_text_views()
            self.mw.ui_updater.update_title()
            
            try:
                from dialogs.search_review_dialog import SearchReviewDialog
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, SearchReviewDialog):
                        widget.refresh_from_project()
            except Exception as e:
                import logging
                logging.getLogger().warning(f"Failed to refresh SearchReviewDialog in accept: {e}")
                
        super().accept()

    def reject(self):
        if self.mw and hasattr(self, 'initial_database_states') and self.initial_database_states:
            self.mw.undo_manager.begin_group()
            try:
                for (b_idx, s_idx), val in self.initial_database_states.items():
                    curr_val, _ = self.mw.data_processor.get_current_string_text(b_idx, s_idx)
                    if curr_val != val:
                        self.mw.data_processor.update_edited_data(b_idx, s_idx, val, action_type="TRANSLATE", skip_ui_refresh=True)
            finally:
                self.mw.undo_manager.end_group("TRANSLATE")
                
            changed_blocks = {b_idx for b_idx, _ in self.initial_database_states.keys()}
            for b_idx in changed_blocks:
                self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)
            
            current_view_block = self.mw.data_store.current_block_idx
            if self.mw.data_store.current_chapter_id is not None:
                current_view_block = -2
            self.mw.ui_updater.populate_strings_for_block(current_view_block, getattr(self.mw.data_store, 'current_category_name', None), force=True)
            self.mw.ui_updater.update_text_views()
            self.mw.ui_updater.update_title()
        super().reject()
