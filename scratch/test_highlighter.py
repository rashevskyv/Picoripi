import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QTextDocument, QTextCharFormat, QColor, QFont
from PyQt5.QtCore import Qt
import re

# Initialize QApp
app = QApplication(sys.argv)

from utils.syntax_highlighter import JsonTagHighlighter
from core.glossary_manager import GlossaryManager, GlossaryEntry

# Setup glossary manager with twilight term
gm = GlossaryManager()
gm.add_entry("hour of twilight", "годину сутінків", "notes")

# Create source document with English original text
source_doc = QTextDocument()
source_doc.setPlainText("pervades the hour of twilight...")

# Create target document with Ukrainian translated text
target_doc = QTextDocument()
target_doc.setPlainText("пронизує {color:red}годину сутінків{color:white}...")

# Mock main window
class MockMainWindow:
    def __init__(self):
        self.theme = 'light'
        self.glossary_enabled = True
        self.newline_display_symbol = "↵"
        self.show_multiple_spaces_as_dots = False
        self.space_dot_color_hex = "#BBBBBB"
        self.tag_color_rgba = "#FF8C00"
        self.icon_sequences = []

# Mock editor
class MockEditor:
    def __init__(self):
        pass
    def objectName(self):
        return "edited_text_edit"

mw = MockMainWindow()
editor = MockEditor()

# Create highlighter for translated text
hl = JsonTagHighlighter(target_doc, main_window_ref=mw, editor_widget_ref=editor)
hl.set_glossary_manager(gm)
hl.set_translation_mode(True, source_editor_ref=source_doc) # Translation mode with English source!

# Force rehighlight
hl.rehighlight()

# Inspect additional formats for target block
block = target_doc.firstBlock()
layout = block.layout()
formats = layout.formats()
print(f"Formats count: {len(formats)}")
for fmt_range in formats:
    start = fmt_range.start
    length = fmt_range.length
    fmt = fmt_range.format
    is_underlined = fmt.fontUnderline()
    color = fmt.foreground().color().name()
    italic = fmt.fontItalic()
    substring = block.text()[start:start+length]
    print(f"Range {start} to {start+length} ({repr(substring)}) | Underline: {is_underlined} | Color: {color} | Italic: {italic}")
