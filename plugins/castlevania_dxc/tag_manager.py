"""Tag manager of the Castlevania: The Dracula X Chronicles plugin: ``{XX}`` bytes the text codecs keep."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .text import TAG_RE


class TagManager(GenericTagManager):
    """The codec's ``{XX}`` tags are the legitimate ones."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
