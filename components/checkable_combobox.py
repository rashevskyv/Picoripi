# components/checkable_combobox.py
from PyQt6.QtWidgets import QComboBox, QStyledItemDelegate
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QStandardItemModel, QStandardItem

class CheckableComboBox(QComboBox):
    """
    A QComboBox that allows selecting multiple items via checkboxes.
    """
    checkedItemsChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModel(QStandardItemModel(self))
        self.setItemDelegate(QStyledItemDelegate(self))
        self.model().dataChanged.connect(self._on_data_changed)
        
        # Make editable but read-only so we can set custom text programmatically
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        
        # Install event filter to prevent closing on checkbox click
        self.view().viewport().installEventFilter(self)
        self._is_updating = False

    def eventFilter(self, widget, event):
        if widget == self.view().viewport():
            if event.type() == QEvent.Type.MouseButtonPress:
                index = self.view().indexAt(event.pos())
                item = self.model().itemFromIndex(index)
                if item:
                    # Toggle check state
                    new_state = (
                        Qt.CheckState.Unchecked 
                        if item.checkState() == Qt.CheckState.Checked 
                        else Qt.CheckState.Checked
                    )
                    item.setCheckState(new_state)
                return True  # Consume the event to prevent closing the popup
        return super().eventFilter(widget, event)

    def add_item(self, text, data=None, is_checked=False):
        self._is_updating = True
        item = QStandardItem(text)
        item.setData(data, Qt.ItemDataRole.UserRole)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        state = Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
        item.setCheckState(state)
        self.model().appendRow(item)
        self._is_updating = False
        self._update_text()

    def clear(self):
        self._is_updating = True
        self.model().clear()
        self._is_updating = False
        self._update_text()

    def _on_data_changed(self, top_left, bottom_right, roles):
        if self._is_updating:
            return
        if Qt.ItemDataRole.CheckStateRole in roles:
            self._update_text()
            self.checkedItemsChanged.emit(self.checked_data())

    def checked_data(self):
        checked = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked.append(item.data(Qt.ItemDataRole.UserRole))
        return checked

    def set_checked_data(self, data_list):
        self._is_updating = True
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item:
                val = item.data(Qt.ItemDataRole.UserRole)
                if val in data_list:
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
        self._is_updating = False
        self._update_text()

    def _update_text(self):
        checked_texts = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked_texts.append(item.text())
        
        if not checked_texts:
            self.setEditText("None selected")
        elif len(checked_texts) == self.model().rowCount():
            self.setEditText("All selected")
        else:
            self.setEditText(", ".join(checked_texts))
