"""Tag manager of the Majora's Mask 3D plugin: the ``{...}`` tags of ``gmsg.py``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .gmsg import TAG_RE


class TagManager(GenericTagManager):
    """``{color:red}``, ``{box-break}``, ``{btn:A}``, ``{delay:10}``..."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
