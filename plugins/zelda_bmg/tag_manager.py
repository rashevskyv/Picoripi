import re
from typing import Optional, Set, List, Tuple
from PyQt6.QtGui import QTextCharFormat, QColor, QFont
from PyQt6.QtCore import Qt
from utils.logging_utils import log_debug

class TagManager:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref
        
        # Initialize formats immediately
        self.tag_format = QTextCharFormat()
        self.newline_symbol_format = QTextCharFormat()
        self.red_text_format = QTextCharFormat()
        self.blue_text_format = QTextCharFormat()
        self.color_default_format = QTextCharFormat()
        
        # Configure them
        self.reconfigure_styles()

    def reconfigure_styles(self):
        # Use Tag Style from settings
        tag_color = getattr(self.mw, 'tag_color_rgba', "#FF8C00") if self.mw else "#FF8C00"
        self.tag_format.setForeground(QColor(tag_color))
        self.tag_format.setFontWeight(QFont.Weight.Bold if getattr(self.mw, 'tag_bold', True) else QFont.Weight.Normal)
        self.tag_format.setFontItalic(getattr(self.mw, 'tag_italic', False))
        self.tag_format.setFontUnderline(getattr(self.mw, 'tag_underline', False))

        nl_color = getattr(self.mw, 'newline_color_rgba', "#A020F0") if self.mw else "#A020F0"
        self.newline_symbol_format.setForeground(QColor(nl_color))
        self.newline_symbol_format.setFontWeight(QFont.Weight.Bold if getattr(self.mw, 'newline_bold', True) else QFont.Weight.Normal)
        self.newline_symbol_format.setFontItalic(getattr(self.mw, 'newline_italic', False))
        self.newline_symbol_format.setFontUnderline(getattr(self.mw, 'newline_underline', False))

        self.red_text_format.setForeground(QColor("#FF4C4C"))
        self.blue_text_format.setForeground(QColor("#0958e0"))
        
        default_text_color = QColor("black")
        if self.mw and hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
            editor_widget = self.mw.edited_text_edit
            default_text_color = editor_widget.palette().color(editor_widget.foregroundRole())
        
        self.color_default_format.setForeground(default_text_color)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        self.reconfigure_styles() 
        
        # Zelda BMG tags use curly braces like {COLOR_RED} or {escape:1:02}
        rules = [
            (r"(\{\s*[^}]*?\s*\})", self.tag_format),
        ]
        
        if self.mw and hasattr(self.mw, 'newline_display_symbol') and self.mw.newline_display_symbol:
            rules.append((r"(" + re.escape(self.mw.newline_display_symbol) + r")", self.newline_symbol_format))
            
        return rules
        
    def get_legitimate_tags(self) -> Set[str]:
        # Return CONTROL_CODES from the plugin config
        from .config import CONTROL_CODES
        return set(CONTROL_CODES)

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return True
