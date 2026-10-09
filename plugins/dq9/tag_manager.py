"""Tag manager of the Dragon Quest IX plugin: the game's ``<tags>`` and the byte tags of ``dqtext.py``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .dqtext import TAG_RE


class TagManager(GenericTagManager):
    """``<PAGE>``, ``<HERO>``, ``<1>``, ``[LF]``, ``[xNN]``..."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
