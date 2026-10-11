"""Tag manager of the Silent Hill 2 plugin: the game's control codes (``~N``, ``~J0(2.5)``, ``~C2``)."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .mes import TAG_RE


class TagManager(GenericTagManager):
    """Control codes the game reads and does not print: line breaks, timing, colours, choices."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
