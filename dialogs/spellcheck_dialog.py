# --- START OF FILE dialogs/spellcheck_dialog.py ---
# Dialog for interactive spellchecking of selected text
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTextEdit, QListWidget, QSplitter,
                             QDialogButtonBox, QWidget, QApplication)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QTextBlockFormat
from typing import List, Tuple
import re
from utils.logging_utils import log_debug, log_error
from components.editor.line_numbered_text_edit import LineNumberedTextEdit


class SpellcheckDialog(QDialog):
    """Interactive dialog for spellchecking text with suggestions."""

    def __init__(self, parent, text: str, spellchecker_manager, starting_line_number: int = 0, line_numbers: List[int] = None):
        log_debug("SpellcheckDialog: __init__ started")
        super().__init__(parent)
        self.spellchecker_manager = spellchecker_manager
        self.original_text = text
        self.current_text = text
        self.misspelled_words = []
        self.current_word_index = 0
        self.starting_line_number = starting_line_number  # Deprecated, kept for compatibility
        self.line_numbers = line_numbers  # Real line numbers from block/document

        self.setWindowTitle("Spellcheck")
        self.setMinimumSize(900, 600)

        log_debug("SpellcheckDialog: Setting up UI with placeholder")
        self.setup_ui()

        log_debug("SpellcheckDialog: Showing dialog")
        # Show dialog immediately
        self.show()
        QApplication.processEvents()  # Force UI update

        log_debug("SpellcheckDialog: Starting content loading")
        # Load content after a small delay to let dialog appear
        QTimer.singleShot(50, self._load_content)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Top label with navigation
        top_layout = QHBoxLayout()
        self.status_label = QLabel("Loading spellchecker...")
        top_layout.addWidget(self.status_label)

        top_layout.addStretch()

        # Navigation buttons
        self.prev_button = QPushButton("← Previous")
        self.prev_button.clicked.connect(self.go_to_previous_word)
        top_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("Next →")
        self.next_button.clicked.connect(self.go_to_next_word)
        top_layout.addWidget(self.next_button)

        layout.addLayout(top_layout)

        # Main splitter (3 panels)
        splitter = QSplitter(Qt.Horizontal)

        # Left panel: Misspelled words list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Misspelled Words:"))

        self.misspelled_list = QListWidget()
        self.misspelled_list.itemClicked.connect(self.jump_to_word_from_list)
        self.misspelled_list.itemDoubleClicked.connect(self._on_list_double_click)
        left_layout.addWidget(self.misspelled_list)

        splitter.addWidget(left_widget)

        # Middle panel: Text editor with line numbers
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 0, 0, 0)

        middle_layout.addWidget(QLabel("Text:"))

        # Use LineNumberedTextEdit with built-in line numbers
        # Pass None as parent to avoid issues with main window attributes
        self.text_edit = LineNumberedTextEdit(None)
        self.text_edit.setPlainText(self.current_text)
        self.text_edit.setReadOnly(True)
        font = QFont("Courier New", 10)
        self.text_edit.setFont(font)

        # Set custom line numbers for the dialog
        # This will be used by the paint logic to display proper string numbers
        self.text_edit.custom_line_numbers = None  # Will be set after spacing processing

        # Connect double-click handler for navigation to main window
        self.text_edit.mouseDoubleClickEvent = self._on_text_double_click

        # Process spacing between strings if we have line numbers data
        self._process_text_spacing_and_line_numbers()

        # Apply zebra striping to text
        self._apply_zebra_striping()

        middle_layout.addWidget(self.text_edit)

        splitter.addWidget(middle_widget)

        # Right panel: Suggestions and actions
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.word_label = QLabel("Word:")
        right_layout.addWidget(self.word_label)

        right_layout.addWidget(QLabel("Suggestions:"))

        self.suggestions_list = QListWidget()
        self.suggestions_list.itemDoubleClicked.connect(self.replace_with_suggestion)
        right_layout.addWidget(self.suggestions_list)

        # Action buttons
        button_layout = QVBoxLayout()

        self.ignore_button = QPushButton("Ignore")
        self.ignore_button.clicked.connect(self.ignore_word)
        button_layout.addWidget(self.ignore_button)

        self.ignore_all_button = QPushButton("Ignore All")
        self.ignore_all_button.clicked.connect(self.ignore_all_word)
        button_layout.addWidget(self.ignore_all_button)

        self.replace_button = QPushButton("Replace")
        self.replace_button.clicked.connect(self.replace_word)
        button_layout.addWidget(self.replace_button)

        self.add_to_dict_button = QPushButton("Add to Dictionary")
        self.add_to_dict_button.clicked.connect(self.add_to_dictionary)
        button_layout.addWidget(self.add_to_dict_button)

        button_layout.addStretch()
        right_layout.addLayout(button_layout)

        splitter.addWidget(right_widget)

        # Set splitter sizes (20%, 50%, 30%)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 3)

        layout.addWidget(splitter)

        # Bottom buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)

    def _process_text_spacing_and_line_numbers(self):
        """Add spacing between different strings and update line numbers display."""
        line_count = self.current_text.count('\n') + 1

        if self.line_numbers and len(self.line_numbers) >= line_count:
            # Build text with spacing between different strings
            text_lines = self.current_text.split('\n')
            text_with_spacing = []
            new_line_numbers = []  # Updated line_numbers array with spacing
            display_line_numbers = []  # Line numbers to display (None for non-first sublines)

            prev_line_num = None
            for i in range(line_count):
                current_line_num = self.line_numbers[i]

                if current_line_num != prev_line_num:
                    # First subline of this string
                    if prev_line_num is not None:
                        # Add spacing between strings (empty line)
                        text_with_spacing.append('')
                        new_line_numbers.append(None)  # Placeholder for empty line
                        display_line_numbers.append(None)  # No number for spacer

                    # Show number only on first subline of string
                    display_line_numbers.append(current_line_num)
                    prev_line_num = current_line_num
                else:
                    # Subsequent sublines of same string - don't show number
                    display_line_numbers.append(None)

                # Add text line
                text_with_spacing.append(text_lines[i] if i < len(text_lines) else '')
                new_line_numbers.append(current_line_num)

            # Update current_text and line_numbers to include spacing
            self.current_text = '\n'.join(text_with_spacing)
            self.line_numbers = new_line_numbers  # Update for zebra striping
            self.text_edit.setPlainText(self.current_text)

            # Set custom line numbers for display (shows string number only once)
            self.text_edit.custom_line_numbers = display_line_numbers

    def _apply_zebra_striping(self):
        """Apply alternating background colors grouped by data string (not by subline)."""
        cursor = QTextCursor(self.text_edit.document())
        cursor.movePosition(QTextCursor.Start)

        # Define colors for alternating rows
        white_bg = QColor(Qt.white)
        gray_bg = QColor(245, 245, 245)  # Light gray

        block = self.text_edit.document().firstBlock()
        subline_index = 0

        # Build mapping: subline_index -> string_number
        # Then determine color based on string_number, not subline_index
        line_count = self.current_text.count('\n') + 1

        # Track which string number each subline belongs to
        string_numbers = []
        if self.line_numbers and len(self.line_numbers) >= line_count:
            string_numbers = self.line_numbers[:line_count]
        else:
            # Fallback: each line is its own string
            string_numbers = list(range(line_count))

        # Create set of unique string numbers in order they appear (skip None)
        unique_strings = []
        seen = set()
        for snum in string_numbers:
            if snum is not None and snum not in seen:
                unique_strings.append(snum)
                seen.add(snum)

        # Map string_number -> color_index (alternating)
        string_color_map = {}
        for i, snum in enumerate(unique_strings):
            string_color_map[snum] = i % 2

        while block.isValid() and subline_index < len(string_numbers):
            cursor.setPosition(block.position())
            block_format = QTextBlockFormat()

            # Get string number for this subline
            string_num = string_numbers[subline_index]

            # For empty separator lines (None), use transparent/white background
            if string_num is None:
                block_format.setBackground(white_bg)
            else:
                color_idx = string_color_map.get(string_num, 0)
                # Apply color based on string number, not subline index
                if color_idx == 0:
                    block_format.setBackground(white_bg)
                else:
                    block_format.setBackground(gray_bg)

            cursor.setBlockFormat(block_format)
            block = block.next()
            subline_index += 1


    def _load_content(self):
        """Load spellcheck content after dialog is shown."""
        try:
            log_debug("SpellcheckDialog: _load_content started")
            self.status_label.setText("Analyzing text...")
            QApplication.processEvents()

            log_debug("SpellcheckDialog: Finding misspelled words")
            self.find_misspelled_words()

            log_debug(f"SpellcheckDialog: Found {len(self.misspelled_words)} misspelled words")
            self.status_label.setText("Highlighting errors...")
            QApplication.processEvents()

            log_debug("SpellcheckDialog: Pre-highlighting all misspelled words")
            self.pre_highlight_all_misspelled_words()

            log_debug("SpellcheckDialog: Showing current word")
            self.show_current_word()

            log_debug("SpellcheckDialog: Content loading complete")
        except Exception as e:
            log_error(f"SpellcheckDialog: Error in _load_content: {e}", exc_info=True)
            self.status_label.setText(f"Error loading spellchecker: {e}")

    def find_misspelled_words(self):
        """Find all misspelled words in the text, ignoring tags and control codes."""
        self.misspelled_words = []
        word_pattern = re.compile(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ\']+')

        # Get ignore pattern from plugin if available
        ignore_pattern = None
        main_window = self._find_main_window()
        if main_window and hasattr(main_window, 'current_game_rules'):
            ignore_pattern = main_window.current_game_rules.get_spellcheck_ignore_pattern()
        
        ignore_re = re.compile(ignore_pattern) if ignore_pattern else None

        lines = self.current_text.split('\n')
        char_offset = 0
        for line_idx, line in enumerate(lines):
            # 1. First, create a version of the line where ignored patterns are replaced by spaces 
            # of the same length to keep offsets correct for highlighting.
            line_cleaned = line
            if ignore_re:
                # We replace matches with spaces to maintain character offsets
                def replace_with_spaces(match):
                    return ' ' * len(match.group(0))
                line_cleaned = ignore_re.sub(replace_with_spaces, line)
            
            # 2. Replace middle dots with spaces for word detection
            line_for_detection = line_cleaned.replace('·', ' ')

            # 3. Find words in the cleaned line
            for match in word_pattern.finditer(line_for_detection):
                word = match.group(0)
                if self.spellchecker_manager.is_misspelled(word):
                    start_pos = char_offset + match.start()
                    end_pos = char_offset + match.end()
                    self.misspelled_words.append((start_pos, end_pos, word, line_idx))
                    
            char_offset += len(line) + 1  # +1 for newline character

    def _find_main_window(self):
        """Helper to navigate up to find the QMainWindow."""
        from PyQt5.QtWidgets import QMainWindow
        parent = self.parent()
        while parent:
            if isinstance(parent, QMainWindow):
                return parent
            parent = parent.parent() if hasattr(parent, 'parent') else None
        
        # Fallback to top level widgets
        from PyQt5.QtWidgets import QApplication
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMainWindow) and widget.objectName() != '':
                return widget
        return None

    def pre_highlight_all_misspelled_words(self):
        """Highlight all misspelled words with red wavy underline."""
        cursor = self.text_edit.textCursor()
        
        # Clear existing underlines first
        cursor.select(QTextCursor.Document)
        clear_format = QTextCharFormat()
        clear_format.setUnderlineStyle(QTextCharFormat.NoUnderline)
        cursor.mergeCharFormat(clear_format)

        cursor.setPosition(0)

        # Create format for misspelled words (red wavy underline)
        misspell_format = QTextCharFormat()
        misspell_format.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        misspell_format.setUnderlineColor(QColor("red"))

        for start, end, word, line_idx in self.misspelled_words:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(misspell_format)

        # Populate misspelled words list
        self.misspelled_list.clear()
        for start, end, word, line_idx in self.misspelled_words:
            # Use real line number if available, otherwise use sequential
            if self.line_numbers and line_idx < len(self.line_numbers):
                display_line_num = self.line_numbers[line_idx]
            else:
                display_line_num = self.starting_line_number + line_idx + 1
            self.misspelled_list.addItem(f"Line {display_line_num}: {word}")

    def show_current_word(self):
        """Display current misspelled word and its suggestions."""
        if self.current_word_index >= len(self.misspelled_words):
            # No more words
            self.status_label.setText("Spellcheck complete!")
            self.word_label.setText("No more misspelled words.")
            self.suggestions_list.clear()
            self.ignore_button.setEnabled(False)
            self.ignore_all_button.setEnabled(False)
            self.replace_button.setEnabled(False)
            self.add_to_dict_button.setEnabled(False)
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return

        start, end, word, line_idx = self.misspelled_words[self.current_word_index]

        # Update status
        total = len(self.misspelled_words)
        current = self.current_word_index + 1
        self.status_label.setText(f"Word {current} of {total}")

        # Update word label with line number
        # Use real line number if available, otherwise use sequential
        if self.line_numbers and line_idx < len(self.line_numbers):
            display_line_num = self.line_numbers[line_idx]
        else:
            display_line_num = self.starting_line_number + line_idx + 1
        self.word_label.setText(f"Line {display_line_num}: \"{word}\"")

        # Highlight word in text with yellow background + red underline
        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)

        # Set yellow background AND red wavy underline for the selection
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#FFFF00"))  # Yellow highlight
        fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        fmt.setUnderlineColor(QColor("red"))
        cursor.mergeCharFormat(fmt)

        # Move cursor to show the word
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

        # Highlight current word in the list
        self.misspelled_list.setCurrentRow(self.current_word_index)

        # Get suggestions
        self.suggestions_list.clear()
        suggestions = self.spellchecker_manager.get_suggestions(word)
        for suggestion in suggestions[:10]:  # Show up to 10 suggestions
            self.suggestions_list.addItem(suggestion)

        if suggestions:
            self.suggestions_list.setCurrentRow(0)

        # Enable/disable navigation buttons
        self.prev_button.setEnabled(self.current_word_index > 0)
        self.next_button.setEnabled(self.current_word_index < len(self.misspelled_words) - 1)

    def go_to_previous_word(self):
        """Navigate to previous misspelled word."""
        if self.current_word_index > 0:
            # Clear current highlight before moving
            self.clear_current_word_highlight()
            self.current_word_index -= 1
            self.show_current_word()

    def go_to_next_word(self):
        """Navigate to next misspelled word."""
        if self.current_word_index < len(self.misspelled_words) - 1:
            # Clear current highlight before moving
            self.clear_current_word_highlight()
            self.current_word_index += 1
            self.show_current_word()

    def clear_current_word_highlight(self):
        """Remove yellow highlight from current word, keep red underline."""
        if self.current_word_index < len(self.misspelled_words):
            start, end, word, line_idx = self.misspelled_words[self.current_word_index]
            cursor = self.text_edit.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)

            # Reset background but keep red underline
            fmt = QTextCharFormat()
            fmt.setBackground(Qt.transparent)
            fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
            fmt.setUnderlineColor(QColor("red"))
            cursor.mergeCharFormat(fmt)

    def jump_to_word_from_list(self, item):
        """Jump to word when clicked in the misspelled words list and navigate in main window."""
        clicked_index = self.misspelled_list.row(item)
        if clicked_index != self.current_word_index:
            self.clear_current_word_highlight()
            self.current_word_index = clicked_index
            self.show_current_word()
            
            # Navigate in main window (Request 5)
            if clicked_index < len(self.misspelled_words):
                _, _, _, line_idx = self.misspelled_words[clicked_index]
                if self.line_numbers and line_idx < len(self.line_numbers):
                    string_number = self.line_numbers[line_idx]
                    self._navigate_to_string_in_main_window(string_number)

    def ignore_word(self):
        """Ignore current word and move to next."""
        self.clear_current_word_highlight()
        self.current_word_index += 1
        self.show_current_word()

    def ignore_all_word(self):
        """Ignore all occurrences of current word."""
        if self.current_word_index >= len(self.misspelled_words):
            return

        _, _, word, _ = self.misspelled_words[self.current_word_index]
        # Remove all occurrences of this word from the list
        self.misspelled_words = [
            (s, e, w, l) for s, e, w, l in self.misspelled_words
            if w.lower() != word.lower()
        ]
        self.pre_highlight_all_misspelled_words()
        self.show_current_word()

    def replace_word(self):
        """Replace current word with selected suggestion."""
        if self.current_word_index >= len(self.misspelled_words):
            return

        current_item = self.suggestions_list.currentItem()
        if not current_item:
            return

        replacement = current_item.text()
        self.replace_with_suggestion(current_item)

    def replace_with_suggestion(self, item):
        """Replace word with the given suggestion."""
        if self.current_word_index >= len(self.misspelled_words):
            return

        start, end, word, line_idx = self.misspelled_words[self.current_word_index]
        replacement = item.text()

        # Replace in text
        self.current_text = self.current_text[:start] + replacement + self.current_text[end:]
        self.text_edit.setPlainText(self.current_text)

        # Reapply zebra striping after text change
        self._apply_zebra_striping()

        # Adjust positions for remaining words
        length_diff = len(replacement) - len(word)
        self.misspelled_words = [
            (s + length_diff if s > start else s,
             e + length_diff if e > start else e,
             w,
             l)
            for i, (s, e, w, l) in enumerate(self.misspelled_words)
            if i != self.current_word_index
        ]

        # Re-apply highlights
        self.pre_highlight_all_misspelled_words()

        # Stay at current index (next word)
        self.show_current_word()

    def add_to_dictionary(self):
        """Add current word to custom dictionary."""
        if self.current_word_index >= len(self.misspelled_words):
            return

        _, _, word, _ = self.misspelled_words[self.current_word_index]
        self.spellchecker_manager.add_to_custom_dictionary(word)

        # Remove this word and all its occurrences from list
        word_lower = word.lower()
        self.misspelled_words = [
            (s, e, w, l) for s, e, w, l in self.misspelled_words
            if w.lower() != word_lower
        ]
        self.pre_highlight_all_misspelled_words()
        self.show_current_word()

    def get_corrected_text(self) -> str:
        """Get the corrected text."""
        return self.current_text

    def _navigate_to_string_in_main_window(self, string_number: int):
        """Helper to navigate to a specific string in the main window."""
        if string_number is None:
            return

        main_window = self._find_main_window()
        if main_window and hasattr(main_window, 'ui_updater'):
            log_debug(f"SpellcheckDialog: Navigating to string {string_number}")

            # 1. Update the current string index
            main_window.current_string_idx = string_number

            # 2. Select the string in the list
            if hasattr(main_window, 'strings_list_widget'):
                main_window.strings_list_widget.setCurrentRow(string_number)

            # 3. Update text views
            main_window.ui_updater.update_text_views()

            # 4. Bring main window to front and give it focus
            main_window.raise_()
            main_window.activateWindow()
            log_debug(f"SpellcheckDialog: Navigation to {string_number} complete")

    def _on_list_double_click(self, item):
        """Handle double-click on misspelled list item to navigate in main window."""
        index = self.misspelled_list.row(item)
        if index < len(self.misspelled_words):
            _, _, _, line_idx = self.misspelled_words[index]
            
            # Get real string number from our line_numbers mapping
            if self.line_numbers and line_idx < len(self.line_numbers):
                string_number = self.line_numbers[line_idx]
                self._navigate_to_string_in_main_window(string_number)

    def _on_text_double_click(self, event):
        """Handle double-click on text to navigate to string in main window."""
        # Get the block number that was clicked
        cursor = self.text_edit.cursorForPosition(event.pos())
        block_number = cursor.blockNumber()

        # Get the string number from custom_line_numbers
        if hasattr(self.text_edit, 'custom_line_numbers') and self.text_edit.custom_line_numbers:
            if block_number < len(self.text_edit.custom_line_numbers):
                string_number = self.text_edit.custom_line_numbers[block_number]

                # If this is a spacer line or subline without number, find the parent string
                if string_number is None:
                    # Search backwards for the first non-None string number
                    for i in range(block_number - 1, -1, -1):
                        if i < len(self.text_edit.custom_line_numbers):
                            if self.text_edit.custom_line_numbers[i] is not None:
                                string_number = self.text_edit.custom_line_numbers[i]
                                break

                if string_number is not None:
                    self._navigate_to_string_in_main_window(string_number)

        # Call the original double click handler
        from PyQt5.QtWidgets import QPlainTextEdit
        QPlainTextEdit.mouseDoubleClickEvent(self.text_edit, event)
