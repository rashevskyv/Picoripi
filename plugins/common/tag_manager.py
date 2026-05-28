import re
from typing import List, Set, Tuple, Optional
from PyQt5.QtGui import QTextCharFormat, QColor, QFont
from PyQt5.QtCore import Qt

class GenericTagManager:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref
        self.curly_tag_format = QTextCharFormat()
        self.bracket_tag_format = QTextCharFormat()
        self.newline_symbol_format = QTextCharFormat()
        self.reconfigure_styles()

    def reconfigure_styles(self):
        if not self.mw:
            return
            
        tag_color_str = getattr(self.mw, 'tag_color_rgba', "#FF8C00")
        newline_color_str = getattr(self.mw, 'newline_color_rgba', "#A020F0")

        def get_safe_color(color_str, default_hex):
            if not color_str:
                return QColor(default_hex)
            color = QColor(color_str)
            if color.isValid():
                return color
            # Try to handle #AARRGGBB if QColor failed (though it shouldn't)
            if isinstance(color_str, str) and color_str.startswith('#') and len(color_str) == 9:
                # Convert #AARRGGBB to #RRGGBB for fallback
                fallback = '#' + color_str[3:]
                color = QColor(fallback)
                if color.isValid():
                    return color
            return QColor(default_hex)

        tag_color = get_safe_color(tag_color_str, "#FF8C00")
        newline_color = get_safe_color(newline_color_str, "#A020F0")

        self.curly_tag_format = QTextCharFormat()
        self.bracket_tag_format = QTextCharFormat()
        self.curly_tag_format.setForeground(tag_color)
        self.bracket_tag_format.setForeground(tag_color)
            
        is_bold = getattr(self.mw, 'tag_bold', True)
        is_italic = getattr(self.mw, 'tag_italic', False)
        is_underline = getattr(self.mw, 'tag_underline', False)
        
        for fmt in [self.curly_tag_format, self.bracket_tag_format]:
            fmt.setFontWeight(QFont.Bold if is_bold else QFont.Normal)
            fmt.setFontItalic(is_italic)
            fmt.setFontUnderline(is_underline)

        self.newline_symbol_format = QTextCharFormat()
        self.newline_symbol_format.setForeground(newline_color)
        self.newline_symbol_format.setFontWeight(QFont.Bold if getattr(self.mw, 'newline_bold', True) else QFont.Normal)
        self.newline_symbol_format.setFontItalic(getattr(self.mw, 'newline_italic', False))
        self.newline_symbol_format.setFontUnderline(getattr(self.mw, 'newline_underline', False))

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        self.reconfigure_styles()
        rules = [
            (r"(\{[^}]*\})", self.curly_tag_format),
            (r"(\[[^\]]*\])", self.bracket_tag_format),
        ]
        if self.mw and hasattr(self.mw, 'newline_display_symbol') and self.mw.newline_display_symbol:
            rules.append((r"(" + re.escape(self.mw.newline_display_symbol) + r")", self.newline_symbol_format))
        return rules

    def is_tag_legitimate(self, tag: str) -> bool:
        return True

    def get_legitimate_tags(self) -> Set[str]:
        return set()
