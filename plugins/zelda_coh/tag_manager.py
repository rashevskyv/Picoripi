"""Tag manager of the Cadence of Hyrule plugin: the game's ``[...]`` tags from ``tags.py``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .tags import TAG_RE


class TagManager(GenericTagManager):
    """``[c:b]``, ``[/c]``, ``[i:button_a]``, ``[p]``, ``[s:9]``, ``[z]``, ``[f]``."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
