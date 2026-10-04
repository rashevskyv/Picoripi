"""Tag manager of the Tingle Tuner plugin: ``{color:2}``, ``{wait:30}``, ``{x8E}`` ... (``tuner.TAG_RE``)."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .tuner import TAG_RE


class TagManager(GenericTagManager):
    """Control codes and raw glyph bytes of the Tingle Tuner text."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
