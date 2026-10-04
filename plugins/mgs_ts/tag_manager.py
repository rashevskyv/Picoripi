"""Tag manager of the Twin Snakes plugin: the only tags are raw bytes ``{xNN}``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .textcodec import TAG_RE


class TagManager(GenericTagManager):
    """``{x1F}``-style raw bytes the text codec could not show as characters."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
