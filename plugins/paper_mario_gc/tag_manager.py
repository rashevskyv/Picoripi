"""Tag manager of the Paper Mario: The Thousand-Year Door plugin: the game's ``<tag>`` shown as ``{tag}``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .msgfile import EDITOR_TAG_RE


class TagManager(GenericTagManager):
    """``{k}``, ``{p}``, ``{wait 250}``, ``{col c00000ff}``, ``{icon PAD_A 0.6 1 0 6}``, ``{x1F}``..."""

    def get_legitimate_tags(self) -> Set[str]:
        return {EDITOR_TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and EDITOR_TAG_RE.fullmatch(tag_to_check) is not None
