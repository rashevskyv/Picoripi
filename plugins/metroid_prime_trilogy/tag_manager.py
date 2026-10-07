"""Tag manager of the Metroid Prime Trilogy plugin: every ``{name}`` / ``{name=value}`` tag is a game tag."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .tags import EDITOR_TAG


class TagManager(GenericTagManager):
    """Tags are the game's ``&name;`` codes shown in curly braces (``tags.py``)."""

    def get_legitimate_tags(self) -> Set[str]:
        return {EDITOR_TAG.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and EDITOR_TAG.fullmatch(tag_to_check) is not None
