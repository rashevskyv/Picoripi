"""Tag manager of the Final Fantasy Explorers plugin: ``{cNN}`` is a control character of the game text."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .textres import TAG_RE


class TagManager(GenericTagManager):
    """Every ``{cNN}`` in the editor text is a legitimate tag."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
