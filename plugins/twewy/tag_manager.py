"""Tag manager of The World Ends with You plugin: the game's ``[...]`` tags from ``mestxt.py``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .mestxt import TAG_RE


class TagManager(GenericTagManager):
    """``[color:4]``, ``[/color]``, ``[num]``, ``[name]``, ``[g:226]``..."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
