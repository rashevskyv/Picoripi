"""Tag manager of the Lunar: Silver Star Harmony plugin: the script's control tags."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .ltcv import CODES, TAG_RE, TAGS


class TagManager(GenericTagManager):
    """``{wait}``, ``{page}``, ``{speaker:41}``, ``{pause:30}``... -- every tag the script codec writes."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        match = TAG_RE.fullmatch(tag_to_check) if isinstance(tag_to_check, str) else None
        if match is None or match.group(1) not in CODES:
            return False
        return (match.group(2) is None) == (CODES[match.group(1)] in TAGS)
