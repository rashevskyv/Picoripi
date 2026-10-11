"""Tag manager of the Attack on Titan: Humanity in Chains plugin: the messages have no control tags (only line breaks)."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return False
