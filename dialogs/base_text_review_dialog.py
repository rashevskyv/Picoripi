# --- START OF FILE dialogs/base_text_review_dialog.py ---
# Base class for specialized text review dialogs (Spellcheck, Search, Glossary)
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QSplitter, QDialogButtonBox, QWidget, QApplication)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QTextBlockFormat
from typing import List, Optional
from utils.logging_utils import log_debug, log_error
from components.editor.line_numbered_text_edit import LineNumberedTextEdit

class BaseTextReviewDialog(QDialog):
    """Base interactive dialog for reviewing and editing text in a 3-panel layout."""

    def __init__(self, parent, title: str, text: str, line_numbers: List[int] = None):
        log_debug(f"BaseTextReviewDialog: __init__ started for '{title}'")
        super().__init__(parent)
        self.original_text = text
        self.current_text = text
        self.line_numbers = line_numbers # Real line numbers from block/document
        self.current_item_index = 0
        self.items_to_review = [] # To be populated by subclasses

        self.setWindowTitle(title)
        self.setMinimumSize(900, 600)

        self.setup_base_ui()
        
        # Process spacing and apply zebra striping BEFORE showing
        self._process_text_spacing_and_line_numbers()
        self._apply_zebra_striping()

        # Show dialog immediately to prevent "frozen" feeling
        self.show()
        QApplication.processEvents()

    def setup_base_ui(self):
        """Sets up the common 3-panel layout: [List | Text Editor | Actions]"""
        self.main_layout = QVBoxLayout(self)

        # 1. Top status bar and navigation
        self.top_nav_layout = QHBoxLayout()
        self.status_label = QLabel("Loading...")
        self.top_nav_layout.addWidget(self.status_label)
        self.top_nav_layout.addStretch()

        self.prev_button = QPushButton("← Previous")
        self.prev_button.clicked.connect(self.go_to_previous_item)
        self.top_nav_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("Next →")
        self.next_button.clicked.connect(self.go_to_next_item)
        self.top_nav_layout.addWidget(self.next_button)

        self.main_layout.addLayout(self.top_nav_layout)

        # 2. Main splitter
        self.splitter = QSplitter(Qt.Horizontal)

        # Left Panel (List)
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.setup_left_panel(self.left_layout)
        self.splitter.addWidget(self.left_panel)

        # Middle Panel (Editor)
        self.middle_panel = QWidget()
        self.middle_layout = QVBoxLayout(self.middle_panel)
        self.middle_layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_edit = LineNumberedTextEdit(None)
        self.text_edit.setPlainText(self.current_text)
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Courier New", 10))
        self.text_edit.mouseDoubleClickEvent = self._on_text_double_click
        
        self.middle_layout.addWidget(QLabel("Text:"))
        self.middle_layout.addWidget(self.text_edit)
        self.splitter.addWidget(self.middle_panel)

        # Right Panel (Actions)
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.setup_right_panel(self.right_layout)
        self.splitter.addWidget(self.right_panel)

        # Set default stretch factors (20%, 50%, 30%)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 5)
        self.splitter.setStretchFactor(2, 3)

        self.main_layout.addWidget(self.splitter)

        # 3. Bottom Close button
        self.button_box = QDialogButtonBox(QDialogButtonBox.Close)
        self.button_box.rejected.connect(self.accept)
        self.main_layout.addWidget(self.button_box)

    def setup_left_panel(self, layout: QVBoxLayout):
        """Override in subclass to add list widgets etc."""
        pass

    def setup_right_panel(self, layout: QVBoxLayout):
        """Override in subclass to add action buttons etc."""
        pass

    def _process_text_spacing_and_line_numbers(self):
        """Add spacing between different strings and update line numbers display."""
        line_count = self.current_text.count('\n') + 1

        if self.line_numbers and len(self.line_numbers) >= line_count:
            text_lines = self.current_text.split('\n')
            text_with_spacing = []
            new_line_numbers = []  # Updated line_numbers array with spacing
            display_line_numbers = []  # Line numbers to display (None for non-first sublines)
            subline_numbers = []  # Subline numbers per string (1, 2, 3...)

            prev_line_num = None
            current_sub_idx = 0
            for i in range(line_count):
                current_line_num = self.line_numbers[i]

                if current_line_num != prev_line_num:
                    # First subline of this string
                    if prev_line_num is not None:
                        # Add spacing between strings (empty line)
                        text_with_spacing.append('')
                        new_line_numbers.append(None)
                        display_line_numbers.append(None)
                        subline_numbers.append(None)

                    # Show number only on first subline of string
                    display_line_numbers.append(current_line_num)
                    prev_line_num = current_line_num
                    current_sub_idx = 1
                else:
                    # Subsequent sublines of same string - don't show number
                    display_line_numbers.append(None)
                    current_sub_idx += 1

                # Add text line
                text_with_spacing.append(text_lines[i] if i < len(text_lines) else '')
                new_line_numbers.append(current_line_num)
                subline_numbers.append(current_sub_idx)

            # Update current_text and line_numbers to include spacing
            self.current_text = '\n'.join(text_with_spacing)
            self.line_numbers = new_line_numbers
            self.text_edit.setPlainText(self.current_text)

            # Set custom line numbers and subline numbers for display
            self.text_edit.custom_line_numbers = display_line_numbers
            self.text_edit.custom_subline_numbers = subline_numbers
            
            # Recalculate margins to accommodate potential two columns
            self.text_edit.updateLineNumberAreaWidth(0)

    def _apply_zebra_striping(self):
        """Apply alternating background colors grouped by data string."""
        if not hasattr(self, 'text_edit') or not self.line_numbers:
            return

        # Define colors for alternating rows
        white_bg = QColor(Qt.white)
        # Use a slightly darker gray to be more visible (hex #F0F0F0)
        gray_bg = QColor(240, 240, 240)

        # Map each unique string number to alternating 0 or 1
        unique_strings = []
        seen = set()
        for ln in self.line_numbers:
            if ln is not None and ln not in seen:
                unique_strings.append(ln)
                seen.add(ln)
        
        string_color_map = {snum: i % 2 for i, snum in enumerate(unique_strings)}

        # Iterate through blocks and set background
        block = self.text_edit.document().firstBlock()
        subline_index = 0
        string_numbers = self.line_numbers

        while block.isValid() and subline_index < len(string_numbers):
            block_format = block.blockFormat()
            
            # Get string number for this subline
            string_num = string_numbers[subline_index]

            # For empty separator lines (None), use white background
            if string_num is None:
                block_format.setBackground(white_bg)
            else:
                color_idx = string_color_map.get(string_num, 0)
                bg_color = gray_bg if color_idx % 2 != 0 else white_bg
                block_format.setBackground(bg_color)

            cursor = QTextCursor(block)
            cursor.setBlockFormat(block_format)
            block = block.next()
            subline_index += 1

    def _find_main_window(self):
        """Helper to navigate up to find the QMainWindow."""
        from PyQt5.QtWidgets import QMainWindow
        parent = self.parent()
        while parent:
            if isinstance(parent, QMainWindow):
                return parent
            parent = parent.parent() if hasattr(parent, 'parent') else None
        
        from PyQt5.QtWidgets import QApplication
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMainWindow) and widget.objectName() != '':
                return widget
        return None

    def _navigate_to_string_in_main_window(self, string_number: int):
        """Navigate to a specific string in the main window."""
        if string_number is None:
            return

        main_window = self._find_main_window()
        if main_window and hasattr(main_window, 'ui_updater'):
            log_debug(f"BaseTextReviewDialog: Navigating to string {string_number}")
            main_window.current_string_idx = string_number
            if hasattr(main_window, 'strings_list_widget'):
                main_window.strings_list_widget.setCurrentRow(string_number)
            main_window.ui_updater.update_text_views()
            main_window.raise_()
            main_window.activateWindow()

    def _on_text_double_click(self, event):
        """Handle double-click on text to navigate to string in main window."""
        cursor = self.text_edit.cursorForPosition(event.pos())
        block_number = cursor.blockNumber()

        if hasattr(self.text_edit, 'custom_line_numbers') and self.text_edit.custom_line_numbers:
            if block_number < len(self.text_edit.custom_line_numbers):
                string_number = self.text_edit.custom_line_numbers[block_number]
                if string_number is None:
                    for i in range(block_number - 1, -1, -1):
                        if i < len(self.text_edit.custom_line_numbers):
                            if self.text_edit.custom_line_numbers[i] is not None:
                                string_number = self.text_edit.custom_line_numbers[i]
                                break
                if string_number is not None:
                    self._navigate_to_string_in_main_window(string_number)

        from PyQt5.QtWidgets import QPlainTextEdit
        QPlainTextEdit.mouseDoubleClickEvent(self.text_edit, event)

    def go_to_previous_item(self):
        """Navigate to previous item."""
        if self.current_item_index > 0:
            self.clear_current_item_highlight()
            self.current_item_index -= 1
            self.show_current_item()

    def go_to_next_item(self):
        """Navigate to next item."""
        if self.current_item_index < len(self.items_to_review) - 1:
            self.clear_current_item_highlight()
            self.current_item_index += 1
            self.show_current_item()

    def show_current_item(self):
        """Override in subclass."""
        pass

    def clear_current_item_highlight(self):
        """Override in subclass."""
        pass

    def get_corrected_text(self) -> str:
        """Get the corrected text."""
        return self.current_text
