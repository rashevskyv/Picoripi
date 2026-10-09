r"""Tag manager of the Infinite Space plugin: the script commands ``[\c,1,12]`` and the byte tags of ``scx.py``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .scx import TAG_RE


class TagManager(GenericTagManager):
    r"""``[\r]``, ``[\c,1,12]``, ``[x80NN]``..."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
