"""Tag manager of the Final Fantasy Tactics A2 plugin: the game's ``[...]`` tags from ``a2text.py``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .a2text import TAG_RE


class TagManager(GenericTagManager):
    """``[end]``, ``[page]``, ``[CA:01]``, ``[x96]``..."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
