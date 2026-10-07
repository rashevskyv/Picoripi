"""Tag manager of the Policenauts plugin: ``{dash}`` and ``{xHH}``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .codec import TAG_RE


class TagManager(GenericTagManager):
    """The codec's tags are the legitimate ones."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
