"""Tag manager of the Silent Hill 3 (PC) plugin: the game's control bytes, shown as ``{XX}``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .codec import TAG_RE


class TagManager(GenericTagManager):
    """Control bytes the game reads and does not print: message start and end, line and wait codes."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
