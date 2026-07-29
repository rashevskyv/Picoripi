from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QComboBox, QPushButton, QCheckBox, QLabel, QSpacerItem, QSizePolicy, QLineEdit)
from PyQt6.QtGui import (QAction)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor
import collections

class SearchLineEdit(QLineEdit):
    """Search line edit implementation."""
    def __init__(self, parent=None, main_window=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.mw = main_window
        self.setStyleSheet("padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px;")
        fm = self.fontMetrics()
        self.setMinimumHeight(fm.height() + 10)

    def paintEvent(self, event):
        # Draw standard QLineEdit first
        """Paintevent."""
        super().paintEvent(event)
        
        # If spellchecker is enabled and active, draw wavy lines under misspelled words
        sm = getattr(self.mw, 'spellchecker_manager', None)
        if not sm or not sm.enabled or not sm.hunspell:
            return
            
        text = self.text()
        if not text:
            return
            
        painter = QPainter()
        if not painter.begin(self):
            return
            
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            
            # Find all words
            import re
            words_iter = re.finditer(r"[a-zA-Zа-яА-ЯіїІїЄєґҐ']+", text)
            
            # Create red pen for wavy line
            pen = QPen(QColor(255, 0, 0))
            pen.setWidth(1)
            painter.setPen(pen)
            
            # Font metrics for baseline calculation
            fm = self.fontMetrics()
            # Draw wavy line near the bottom of QLineEdit client area (y_base relative to height)
            y = self.height() - 4
            
            for match in words_iter:
                word = match.group(0)
                cleaned_word = word.strip("'")
                if len(cleaned_word) < 3 or cleaned_word.isdigit():
                    continue
                    
                if sm.is_misspelled(cleaned_word):
                    start = match.start()
                    end = match.end()
                    
                    # Get X coordinates on screen
                    x_start = self._get_x_for_index(start)
                    x_end = self._get_x_for_index(end)
                    
                    if x_start != -1 and x_end != -1 and x_end > x_start:
                        # Draw wavy line from x_start to x_end
                        points = []
                        for x in range(x_start, x_end):
                            dx = x - x_start
                            dy = 1 if (dx // 2) % 2 == 0 else -1
                            points.append(QPoint(x, y + dy))
                            
                        for i in range(len(points) - 1):
                            painter.drawLine(points[i], points[i+1])
        finally:
            painter.end()

    def _get_x_for_index(self, idx: int) -> int:
        # To get the X coordinate of a character index, we can do binary search
        # using cursorPositionAt which is a public API.
        """Internal helper to get the x for index."""
        width = self.width()
        margin = 4
        
        low = margin
        high = width - margin
        best_x = -1
        
        while low <= high:
            mid = (low + high) // 2
            pos = self.cursorPositionAt(QPoint(mid, self.height() // 2))
            if pos < idx:
                low = mid + 1
            else:
                best_x = mid
                high = mid - 1
                
        return best_x

    def contextMenuEvent(self, event):
        """Contextmenuevent."""
        menu = self.createStandardContextMenu()
        
        # Get spellchecker manager
        sm = getattr(self.mw, 'spellchecker_manager', None)
        if sm and sm.enabled and sm.hunspell:
            # Determine the word under cursor
            text = self.text()
            cursor_pos = self.cursorPosition()
            
            # Find which word is at cursor_pos
            import re
            words_iter = re.finditer(r"[a-zA-Zа-яА-ЯіїІїЄєґҐ']+", text)
            word_under_cursor = None
            for match in words_iter:
                if match.start() <= cursor_pos <= match.end():
                    word_under_cursor = match.group(0)
                    break
            
            if word_under_cursor:
                cleaned_word = word_under_cursor.strip("'")
                if len(cleaned_word) >= 3 and not cleaned_word.isdigit() and sm.is_misspelled(cleaned_word):
                    # Word is misspelled! Fetch suggestions.
                    suggestions = sm._suggestions_cache.get(cleaned_word.lower(), [])
                    if not suggestions and sm.hunspell:
                        try:
                            res = sm.hunspell.suggest(cleaned_word)
                            if hasattr(res, '__next__') or (hasattr(res, '__iter__') and not isinstance(res, list)):
                                gen = iter(res)
                                for _ in range(7):
                                    try:
                                        suggestions.append(next(gen))
                                    except StopIteration:
                                        break
                            else:
                                suggestions = list(res)[:7]
                            sm._suggestions_cache[cleaned_word.lower()] = suggestions
                        except Exception:
                            pass
                    
                    if suggestions:
                        first_action = menu.actions()[0] if menu.actions() else None
                        
                        suggestion_actions = []
                        for sugg in suggestions:
                            act = QAction(sugg, menu)
                            act.triggered.connect(lambda checked, s=sugg, match_start=match.start(), match_end=match.end(): self._replace_word(match_start, match_end, s))
                            suggestion_actions.append(act)
                        
                        add_dict_action = QAction(f"Add '{cleaned_word}' to Dictionary", menu)
                        add_dict_action.triggered.connect(lambda checked, w=cleaned_word: sm.add_to_custom_dictionary(w))
                        
                        if first_action:
                            menu.insertActions(first_action, suggestion_actions)
                            menu.insertSeparator(first_action)
                            menu.insertAction(first_action, add_dict_action)
                            menu.insertSeparator(first_action)
                        else:
                            menu.addActions(suggestion_actions)
                            menu.addSeparator()
                            menu.addAction(add_dict_action)
                            
        menu.exec(event.globalPos())

    def _replace_word(self, start, end, new_word):
        """Internal helper to replace word."""
        text = self.text()
        new_text = text[:start] + new_word + text[end:]
        self.setText(new_text)
        self.setCursorPosition(start + len(new_word))

class SearchPanelWidget(QWidget):
    """Widget component for search panel."""
    find_next_requested = pyqtSignal(str, bool, bool, bool, bool) # + is_fuzzy
    find_previous_requested = pyqtSignal(str, bool, bool, bool, bool) # + is_fuzzy
    advanced_search_requested = pyqtSignal(str, bool, bool, bool, bool)
    close_requested = pyqtSignal()

    MAX_HISTORY_ITEMS = 20

    def __init__(self, parent=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.setObjectName("SearchPanel")
        self.mw = parent
        
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self.search_history = collections.deque(maxlen=self.MAX_HISTORY_ITEMS)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        self.search_query_edit = QComboBox(self)
        self.search_query_edit.setLineEdit(SearchLineEdit(self, self.mw))
        self.search_query_edit.setEditable(True)
        self.search_query_edit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert) 
        self.search_query_edit.lineEdit().setPlaceholderText("Find...")
        
        self.find_next_button = QPushButton("Next", self)
        self.find_previous_button = QPushButton("Prev", self)
        self.advanced_button = QPushButton("Advance", self)
        
        button_width = 75 
        self.find_next_button.setFixedWidth(button_width)
        self.find_previous_button.setFixedWidth(button_width)
        self.advanced_button.setFixedWidth(button_width)
        
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
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.close_search_panel_button = QPushButton("X", self)
        self.close_search_panel_button.setToolTip("Close search panel")
        self.close_search_panel_button.setFixedSize(24, 24)

        left_layout = QHBoxLayout()
        left_layout.addWidget(self.search_query_edit)
        left_layout.addWidget(self.find_previous_button)
        left_layout.addWidget(self.find_next_button)
        left_layout.addWidget(self.advanced_button)
        
        options_layout = QHBoxLayout()
        options_layout.setSpacing(8)
        options_layout.addWidget(self.case_sensitive_checkbox)
        options_layout.addWidget(self.fuzzy_search_checkbox)
        options_layout.addWidget(self.search_in_original_checkbox)
        options_layout.addWidget(self.ignore_tags_newlines_checkbox)
        options_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        main_layout.addLayout(left_layout, 6) 
        main_layout.addLayout(options_layout, 5)
        main_layout.addWidget(self.status_label, 2) 
        main_layout.addWidget(self.close_search_panel_button) 

        self.find_next_button.clicked.connect(self._on_find_next)
        self.find_previous_button.clicked.connect(self._on_find_previous)
        self.advanced_button.clicked.connect(self._on_advanced_clicked)
        self.search_query_edit.lineEdit().returnPressed.connect(self._on_find_next)
        self.search_query_edit.textActivated.connect(self._on_find_next_from_combobox_activation)
        self.search_query_edit.lineEdit().textChanged.connect(self.trigger_spellcheck)
        self.close_search_panel_button.clicked.connect(self.close_requested)

    def _on_find_next_from_combobox_activation(self, text: str):
        """Internal helper to handle the find next from combobox activation event."""
        self._on_find_next()

    def _add_to_history(self, query: str):
        """Internal helper to add to history."""
        if not query:
            return
        if query in self.search_history:
            self.search_history.remove(query)
        self.search_history.appendleft(query)
        self._update_combobox_items()

    def _update_combobox_items(self):
        """Internal helper to update the combobox items."""
        current_text = self.search_query_edit.lineEdit().text() 
        self.search_query_edit.blockSignals(True)
        self.search_query_edit.clear()
        self.search_query_edit.addItems(list(self.search_history))
        self.search_query_edit.lineEdit().setText(current_text) 
        self.search_query_edit.blockSignals(False)

    def load_history(self, history_list: list):
        """Load history."""
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
        """Get the history."""
        return list(self.search_history)

    def _on_find_next(self):
        """Internal helper to handle the find next event."""
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
        """Internal helper to handle the find previous event."""
        query = self.search_query_edit.currentText()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        search_in_original = self.search_in_original_checkbox.isChecked()
        ignore_tags = self.ignore_tags_newlines_checkbox.isChecked()
        is_fuzzy = self.fuzzy_search_checkbox.isChecked()
        if query:
            self._add_to_history(query)
            self.find_previous_requested.emit(query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)

    def _on_advanced_clicked(self):
        """Internal helper to handle the advanced clicked event."""
        query = self.search_query_edit.currentText()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        search_in_original = self.search_in_original_checkbox.isChecked()
        ignore_tags = self.ignore_tags_newlines_checkbox.isChecked()
        is_fuzzy = self.fuzzy_search_checkbox.isChecked()
        if query:
            self._add_to_history(query)
        self.advanced_search_requested.emit(query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)

    def get_search_parameters(self) -> tuple[str, bool, bool, bool, bool]:
        """Get the search parameters."""
        query = self.search_query_edit.currentText()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        search_in_original = self.search_in_original_checkbox.isChecked()
        ignore_tags = self.ignore_tags_newlines_checkbox.isChecked()
        is_fuzzy = self.fuzzy_search_checkbox.isChecked()
        return query, case_sensitive, search_in_original, ignore_tags, is_fuzzy

    def set_search_options(self, case_sensitive: bool, search_in_original: bool, ignore_tags: bool, is_fuzzy: bool = False):
        """Set the search options."""
        self.case_sensitive_checkbox.setChecked(case_sensitive)
        self.search_in_original_checkbox.setChecked(search_in_original)
        self.ignore_tags_newlines_checkbox.setChecked(ignore_tags)
        self.fuzzy_search_checkbox.setChecked(is_fuzzy)

    def set_status_message(self, message: str, is_error: bool = False):
        """Set the status message."""
        self.status_label.setText(message)
        if is_error:
            self.status_label.setStyleSheet("color: red;")
        else:
            self.status_label.setStyleSheet("")
            
    def focus_search_input(self):
        """Focus search input."""
        self.search_query_edit.lineEdit().selectAll()
        self.search_query_edit.setFocus()

    def clear_status(self):
        """Remove status."""
        self.status_label.setText("")
        self.status_label.setStyleSheet("")

    def get_query(self) -> str:
        """Get the query."""
        return self.search_query_edit.currentText()

    def set_query(self, query: str):
        """Set the query."""
        self.search_query_edit.lineEdit().setText(query)

    def trigger_spellcheck(self):
        """Trigger spellcheck."""
        line_edit = self.search_query_edit.lineEdit()
        if line_edit:
            line_edit.update()