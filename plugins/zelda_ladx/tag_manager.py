"""Tag manager of the Link's Awakening DX plugin: the symbol names and unnamed codes of the dialog text."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .text import TAG_PATTERN


class TagManager(GenericTagManager):
    """Symbols (``<flower>``, ``<ask>``) and unnamed bytes (``{XX}``) of the dialog text (``text.TAG_PATTERN``)."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_PATTERN}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and re.fullmatch(TAG_PATTERN, tag_to_check) is not None
