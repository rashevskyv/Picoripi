"""Tag manager of the Pokémon Brilliant Diamond / Shining Pearl plugin: a tag is legitimate when it encodes back."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .msg import TAG_RE, parse_tag


class TagManager(GenericTagManager):
    """``{tag:…}``, ``{scroll}``, ``{clear}``, ``{wait:…}``, ``{event:…}`` and TextMesh Pro rich-text tags."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        if not isinstance(tag_to_check, str) or not TAG_RE.fullmatch(tag_to_check):
            return False
        if tag_to_check.startswith("{tag:"):
            try:
                parse_tag(tag_to_check)
            except ValueError:
                return False
        return True
