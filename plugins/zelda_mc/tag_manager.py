import re
from typing import Optional, Set, List, Tuple
from PyQt5.QtGui import QTextCharFormat, QColor
from PyQt5.QtCore import Qt
from plugins.common.tag_manager import GenericTagManager
from utils.logging_utils import log_debug

class TagManager(GenericTagManager):
    def __init__(self, main_window_ref=None):
        self.literal_newline_format = QTextCharFormat()
        self.color_red_format = QTextCharFormat()
        self.color_green_format = QTextCharFormat()
        self.color_blue_format = QTextCharFormat()
        self.color_default_format = QTextCharFormat()
        super().__init__(main_window_ref)
        self._legitimate_exact_tags_cache: Optional[Set[str]] = None
        self.reconfigure_styles()

    def reconfigure_styles(self):
        super().reconfigure_styles()
        self.literal_newline_format = QTextCharFormat()
        self.literal_newline_format.setForeground(QColor("red"))
        self.literal_newline_format.setFontWeight(75) # Bold

        self.color_red_format.setForeground(Qt.red)
        self.color_green_format.setForeground(Qt.darkGreen)
        self.color_blue_format.setForeground(Qt.blue)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
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

    def _ensure_exact_tags_loaded(self):
        if self._legitimate_exact_tags_cache is None:
            self._legitimate_exact_tags_cache = set()
            if self.mw and hasattr(self.mw, 'default_tag_mappings'):
                for key, value in self.mw.default_tag_mappings.items():
                    self._legitimate_exact_tags_cache.add(key)
                    self._legitimate_exact_tags_cache.add(value)
            self._legitimate_exact_tags_cache.add("{Player}")
            log_debug(f"Loaded {len(self._legitimate_exact_tags_cache)} exact legitimate tags.")

    def get_legitimate_tags(self) -> Set[str]:
        self._ensure_exact_tags_loaded()
        return self._legitimate_exact_tags_cache if self._legitimate_exact_tags_cache is not None else set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return True
