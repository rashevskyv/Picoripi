"""Tag manager of the Lunar plugin: the codec's control tags."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .codec import TAG_RE


class TagManager(GenericTagManager):
    """``{wait}``, ``{page}``, ``{clear}``, ``{close}``, ``{end}``, ``{raw:HH}`` and ``{HH:LL}`` (HH from D6)."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        if not isinstance(tag_to_check, str) or TAG_RE.fullmatch(tag_to_check) is None:
            return False
        head = tag_to_check[1:3]
        return not all(c in "0123456789ABCDEF" for c in head) or tag_to_check[3] != ":" or int(head, 16) >= 0xD6
