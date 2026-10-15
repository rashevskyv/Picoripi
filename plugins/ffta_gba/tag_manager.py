"""Tag manager of the Final Fantasy Tactics Advance (GBA) plugin: the ``[...]`` tags of ``codec``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .codec import TAG_RE


class TagManager(GenericTagManager):
    """``[wait]``, ``[clear]``, ``[next]``, ``[sep]``, ``[crn:06]``, ``[var:21]``, ``[sp:03]``, ``[c67:00]``, ``[x8922]``..."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
