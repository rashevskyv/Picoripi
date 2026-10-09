"""Tag manager of the Super Metroid plugin: tiles that are not letters, ``[name]`` or ``[#XXXX]``."""
from typing import Set

from core.tag_utils import ANY_NON_EMPTY_TAG_CAPTURE_PATTERN as TAG_RE
from plugins.common.tag_manager import GenericTagManager


class TagManager(GenericTagManager):
    """Square-bracket tile tags ([press1], [#304B], [#2C0D/2C1D]) are legitimate tags."""

    def get_legitimate_tags(self) -> Set[str]:
        return {r"\[[^\]]+\]"}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
