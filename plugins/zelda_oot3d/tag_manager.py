"""Tag manager of the Ocarina of Time 3D plugin: the ``{...}`` tags of ``qm.py``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .qm import TAG_RE


class TagManager(GenericTagManager):
    """``{color:red}``, ``{box-break}``, ``{item-icon:45}``, ``{textid:0x0205}``..."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
