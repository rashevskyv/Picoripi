"""Tag manager of the Castlevania: Symphony of the Night (Saturn) plugin: the ``[xNN]`` byte tags of ``codec``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .codec import TAG_RE


class TagManager(GenericTagManager):
    """``[x70]``: a byte the font has no letter for."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
