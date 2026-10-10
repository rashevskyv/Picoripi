"""Tag manager of the Kingdom Hearts 3D plugin: ``{UE026}`` stands for a private-area character (an icon or a colour switch)."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .ctd import TAG_RE


class TagManager(GenericTagManager):
    """Every ``{UXXXX}`` in the editor text is a legitimate tag."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
