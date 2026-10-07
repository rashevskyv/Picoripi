"""Tag manager of the A Link Between Worlds plugin: a tag is legitimate when it encodes to an MSBT tag."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .tags import TAG_RE, parse_tag


class TagManager(GenericTagManager):
    """``{Name:args}`` tags of the game's message project and raw ``{tag:G:T:hex}`` tags."""

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
