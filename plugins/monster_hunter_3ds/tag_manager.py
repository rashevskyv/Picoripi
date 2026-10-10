"""Tag manager of the Monster Hunter 3DS plugin: the games' ``<COLO 1>``-style codes and ``%s``/``%d`` values."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .mttext import TAG_RE


class TagManager(GenericTagManager):
    """``<COLO 1>``, ``</COL>``, ``<SUBS 3>``, ``<ICON A>``, ``%s``, ``%2d``..."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
