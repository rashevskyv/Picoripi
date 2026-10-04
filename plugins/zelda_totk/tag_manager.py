"""Tag manager of the Tears of the Kingdom plugin: a tag is legitimate when it encodes to an MSBT tag."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .tags import TAG_RE, parse_tag


class TagManager(GenericTagManager):
    """``{name:args}`` and raw ``{tag:G:T:hex}`` tags from ``tags.py``."""

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
