"""Tag manager of the Age of Calamity plugin: the game's square-bracket tags are legitimate."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .tags import KNOWN_TAG_RE


class TagManager(GenericTagManager):
    """``[cdb]``, ``[v]``, ``[/]``, ``[s0]``, ``[eg2]``, ``[es:1_5_1]``, ``[$0003]`` ... from ``tags.py``."""

    def get_legitimate_tags(self) -> Set[str]:
        return {KNOWN_TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and KNOWN_TAG_RE.fullmatch(tag_to_check) is not None
