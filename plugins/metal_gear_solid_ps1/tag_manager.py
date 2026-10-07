"""Tag manager of the Metal Gear Solid (PlayStation) plugin: the only tags are raw codes ``{901B}`` / ``{0A}``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .codec import TAG_RE


class TagManager(GenericTagManager):
    """Game codes the text codec does not show as characters: button icons, colours, extra glyphs."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
