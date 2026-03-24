# --- START OF FILE components/search_panel.py ---
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QComboBox, QPushButton,
    QCheckBox, QLabel, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
import collections

class SearchPanelWidget(QWidget):
    find_next_requested = pyqtSignal(str, bool, bool, bool, bool) # + is_fuzzy
    find_previous_requested = pyqtSignal(str, bool, bool, bool, bool) # + is_fuzzy
    close_requested = pyqtSignal()

    MAX_HISTORY_ITEMS = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchPanel")
        
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.search_history = collections.deque(maxlen=self.MAX_HISTORY_ITEMS)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        self.search_query_edit = QComboBox(self)
        self.search_query_edit.setEditable(True)
        self.search_query_edit.setInsertPolicy(QComboBox.NoInsert) 
        self.search_query_edit.lineEdit().setPlaceholderText("Find...")
        
        self.find_next_button = QPushButton("Next", self)
        self.find_previous_button = QPushButton("Prev", self)
        
        button_width = 75 
        self.find_next_button.setFixedWidth(button_width)
        self.find_previous_button.setFixedWidth(button_width)
        
        self.case_sensitive_checkbox = QCheckBox("Aa", self)
        self.case_sensitive_checkbox.setToolTip("Case sensitive")
        
        self.search_in_original_checkbox = QCheckBox("Original", self)
        self.search_in_original_checkbox.setToolTip("Search in original text")
        
        self.ignore_tags_newlines_checkbox = QCheckBox("No Tags", self)
        self.ignore_tags_newlines_checkbox.setChecked(True) 
        self.ignore_tags_newlines_checkbox.setToolTip("Ignore tags {...} [...], newlines, and extra spaces")
        
        self.fuzzy_search_checkbox = QCheckBox("Fuzzy", self)
        self.fuzzy_search_checkbox.setToolTip("Search for similar words (ignores endings)")

        self.status_label = QLabel("", self)
        self.status_label.setMinimumWidth(100) 
        self.status_label.setAlignment(Qt.AlignCenter)

        self.close_search_panel_button = QPushButton("X", self)
        self.close_search_panel_button.setToolTip("Close search panel")
        self.close_search_panel_button.setFixedSize(24, 24)

        left_layout = QHBoxLayout()
        left_layout.addWidget(self.search_query_edit)
        left_layout.addWidget(self.find_previous_button)
        left_layout.addWidget(self.find_next_button)
        
        options_layout = QHBoxLayout()
        options_layout.setSpacing(8)
        options_layout.addWidget(self.case_sensitive_checkbox)
        options_layout.addWidget(self.fuzzy_search_checkbox)
        options_layout.addWidget(self.search_in_original_checkbox)
        options_layout.addWidget(self.ignore_tags_newlines_checkbox)
        options_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        main_layout.addLayout(left_layout, 6) 
        main_layout.addLayout(options_layout, 5)
        main_layout.addWidget(self.status_label, 2) 
        main_layout.addWidget(self.close_search_panel_button) 

        self.find_next_button.clicked.connect(self._on_find_next)
        self.find_previous_button.clicked.connect(self._on_find_previous)
        self.search_query_edit.lineEdit().returnPressed.connect(self._on_find_next)
        self.search_query_edit.activated[str].connect(self._on_find_next_from_combobox_activation)
        self.close_search_panel_button.clicked.connect(self.close_requested)

    def _on_find_next_from_combobox_activation(self, text: str):
        self._on_find_next()

    def _add_to_history(self, query: str):
        if not query:
            return
        if query in self.search_history:
            self.search_history.remove(query)
        self.search_history.appendleft(query)
        self._update_combobox_items()

    def _update_combobox_items(self):
        current_text = self.search_query_edit.lineEdit().text() 
        self.search_query_edit.blockSignals(True)
        self.search_query_edit.clear()
        self.search_query_edit.addItems(list(self.search_history))
        self.search_query_edit.lineEdit().setText(current_text) 
        self.search_query_edit.blockSignals(False)

    def load_history(self, history_list: list):
        self.search_history.clear()
        for item in history_list: 
            if item not in self.search_history: 
                 if len(self.search_history) < self.MAX_HISTORY_ITEMS:
                    self.search_history.append(item) 
        self.search_history.reverse() 
        self._update_combobox_items()
        if self.search_history:
            self.search_query_edit.setCurrentText(self.search_history[0])

    def get_history(self) -> list:
        return list(self.search_history)

    def _on_find_next(self):
        query = self.search_query_edit.currentText()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        search_in_original = self.search_in_original_checkbox.isChecked()
        ignore_tags = self.ignore_tags_newlines_checkbox.isChecked()
        is_fuzzy = self.fuzzy_search_checkbox.isChecked()
        if query:
            self._add_to_history(query)
            # Emitting is_fuzzy via signal might require signal change, 
            # but we can change the signature or just call a public handler method 
            # if the signal is connected to it. 
            # However, the signal is defined as (str, bool, bool, bool). Adding another bool.
            # Since we are changing the signal class, it's better to update the definition.
            # BUT, to not break compatibility with ui_setup.py where connection is via connect,
            # we update the signal definition at the top of the file (see above).
            self.find_next_requested.emit(query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)

    def _on_find_previous(self):
        query = self.search_query_edit.currentText()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        search_in_original = self.search_in_original_checkbox.isChecked()
        ignore_tags = self.ignore_tags_newlines_checkbox.isChecked()
        is_fuzzy = self.fuzzy_search_checkbox.isChecked()
        if query:
            self._add_to_history(query)
            self.find_previous_requested.emit(query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)

    def get_search_parameters(self) -> tuple[str, bool, bool, bool, bool]:
        query = self.search_query_edit.currentText()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        search_in_original = self.search_in_original_checkbox.isChecked()
        ignore_tags = self.ignore_tags_newlines_checkbox.isChecked()
        is_fuzzy = self.fuzzy_search_checkbox.isChecked()
        return query, case_sensitive, search_in_original, ignore_tags, is_fuzzy

    def set_search_options(self, case_sensitive: bool, search_in_original: bool, ignore_tags: bool, is_fuzzy: bool = False):
        self.case_sensitive_checkbox.setChecked(case_sensitive)
        self.search_in_original_checkbox.setChecked(search_in_original)
        self.ignore_tags_newlines_checkbox.setChecked(ignore_tags)
        self.fuzzy_search_checkbox.setChecked(is_fuzzy)

    def set_status_message(self, message: str, is_error: bool = False):
        self.status_label.setText(message)
        if is_error:
            self.status_label.setStyleSheet("color: red;")
        else:
            self.status_label.setStyleSheet("")
            
    def focus_search_input(self):
        self.search_query_edit.lineEdit().selectAll()
        self.search_query_edit.setFocus()

    def clear_status(self):
        self.status_label.setText("")
        self.status_label.setStyleSheet("")

    def get_query(self) -> str:
        return self.search_query_edit.currentText()

    def set_query(self, query: str):
        self.search_query_edit.lineEdit().setText(query)