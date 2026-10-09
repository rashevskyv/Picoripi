"""Tag manager of the Pokémon (Switch) plugin: ``[VAR XXXX(...)]`` game commands and ``[XXXX]`` characters."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .tags import KNOWN_TAG_RE


class TagManager(GenericTagManager):
    """The game's square-bracket commands and special characters (``tags.py``) are legitimate."""

    def get_legitimate_tags(self) -> Set[str]:
        return {KNOWN_TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and KNOWN_TAG_RE.fullmatch(tag_to_check) is not None
