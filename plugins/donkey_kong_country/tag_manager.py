"""Tag manager of the Donkey Kong Country plugin: the ROM text has no tags, so square brackets are plain text."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager


class TagManager(GenericTagManager):
    """No legitimate tags in the ROM text."""

    def get_legitimate_tags(self) -> Set[str]:
        return set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return False
