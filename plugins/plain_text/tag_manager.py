import re
from typing import Optional, Set, List, Tuple
from plugins.common.tag_manager import GenericTagManager

class TagManager(GenericTagManager):
    """Manager class for tag."""
    def __init__(self, main_window_ref=None):
        """Initialize a new instance."""
        super().__init__(main_window_ref)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, any]]:
        """Get the syntax highlighting rules."""
        return super().get_syntax_highlighting_rules()

    def get_legitimate_tags(self) -> Set[str]:
        """Get the legitimate tags."""
        return set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        """Check if is tag legitimate."""
        return bool(re.fullmatch(r"\[[^\]]+\]", tag_to_check))
