"""Tag manager of the Four Swords Anniversary Edition plugin: the game's ``[...]`` tags from ``tags.py``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .tags import TAG_RE


class TagManager(GenericTagManager):
    """``[speaker:1]``, ``[color:1]``, ``[icon:12]``, ``[wait:120]``, ``[close]``..."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
