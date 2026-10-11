"""Tag manager of the Snake Eater 3D plugin: ``{xNN}`` is a raw byte of the game text the codec keeps."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .textcodec import TAG_RE


class TagManager(GenericTagManager):
    """Every ``{xNN}`` in the editor text is a legitimate tag."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
