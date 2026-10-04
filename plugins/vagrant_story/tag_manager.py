"""Tag manager of the Vagrant Story plugin: the codec's readable control tags."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .codec import TAG_RE, encode


class TagManager(GenericTagManager):
    """``{page}``, ``{>12}``, ``{down 13}``, ``{color 1}``, ``{xNN}``... -- every tag the codec can write."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        if not isinstance(tag_to_check, str) or TAG_RE.fullmatch(tag_to_check) is None:
            return False
        try:
            encode(tag_to_check)
        except ValueError:
            return False
        return True
