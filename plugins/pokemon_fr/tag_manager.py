from typing import Set, List, Tuple
from PyQt5.QtGui import QTextCharFormat
from plugins.common.tag_manager import GenericTagManager

class TagManager(GenericTagManager):
    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        return super().get_syntax_highlighting_rules()

    def get_legitimate_tags(self) -> Set[str]:
        return set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return True
