"""Tag manager of the Pokémon Red / Blue / Yellow plugin: {text commands} and <game codes>."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager
from core.tag_utils import ANY_NON_EMPTY_TAG_CAPTURE_PATTERN as TAG_RE


class TagManager(GenericTagManager):
    """Text commands in curly braces ({text_ram wStringBuffer}, {cont}) are legitimate tags."""

    def get_legitimate_tags(self) -> Set[str]:
        return {r"\{[^}]+\}"}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        if not isinstance(tag_to_check, str):
            return False
        return bool(TAG_RE.fullmatch(tag_to_check))
