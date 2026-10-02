"""Tag manager of the Minish Cap plugin."""
from typing import List, Tuple
from PyQt6.QtGui import QTextCharFormat, QColor
from plugins.common.tag_manager import GenericTagManager

class TagManager(GenericTagManager):
    """Manager class for tag."""

    legitimate_tags_from_aliases = True
    extra_legitimate_tags = ("{Player}",)

    def __init__(self, main_window_ref=None):
        """Initialize a new instance."""
        self.literal_newline_format = QTextCharFormat()
        self.color_red_format = QTextCharFormat()
        self.color_green_format = QTextCharFormat()
        self.color_blue_format = QTextCharFormat()
        self.color_default_format = QTextCharFormat()
        super().__init__(main_window_ref)
        self.reconfigure_styles()

    def reconfigure_styles(self):
        """Reconfigure styles."""
        super().reconfigure_styles()
        self.literal_newline_format = QTextCharFormat()
        self.literal_newline_format.setForeground(QColor("red"))
        self.literal_newline_format.setFontWeight(75) # Bold

        self.color_red_format.setForeground(QColor("red"))
        self.color_green_format.setForeground(QColor("darkGreen"))
        self.color_blue_format.setForeground(QColor("blue"))

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        """Get the syntax highlighting rules."""
        rules = super().get_syntax_highlighting_rules()
        
        # Add Zelda-specific rules
        rules.extend([
            (r"(\{\s*Color\s*:\s*Red\s*\})", self.curly_tag_format),
            (r"(\{\s*Color\s*:\s*Green\s*\})", self.curly_tag_format),
            (r"(\{\s*Color\s*:\s*Blue\s*\})", self.curly_tag_format),
            (r"(\{\s*Color\s*:\s*White\s*\})", self.curly_tag_format),
            (r"(\\n)", self.literal_newline_format),
        ])
        return rules
