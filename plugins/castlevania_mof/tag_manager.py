"""Tag manager of the Castlevania: Mirror of Fate plugin: ``{NAME}`` is a button icon or a value (``@[NAME]`` in the file)."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .text import TAG_RE


class TagManager(GenericTagManager):
    """Every ``{NAME}`` in the editor text is a legitimate tag."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
