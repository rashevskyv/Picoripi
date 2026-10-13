"""Tag manager of the Oracles plugin: the control codes of the markup (col, Link, stop and the rest)."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .text import TAG_PATTERN


class TagManager(GenericTagManager):
    """Control codes of the Oracles text (``text.TAG_PATTERN``)."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_PATTERN}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        import re

        return isinstance(tag_to_check, str) and re.fullmatch(TAG_PATTERN, tag_to_check) is not None
