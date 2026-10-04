"""Tag manager of the Hyrule Warriors DE plugin: a tag is legitimate when it encodes to game bytes."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .tags import TAG_RE, parse_tag


class TagManager(GenericTagManager):
    """``{c:0}``, ``{form:1}``, ``{btn:P}`` ... from ``tags.py``."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        if not isinstance(tag_to_check, str):
            return False
        try:
            parse_tag(tag_to_check)
        except ValueError:
            return False
        return True
