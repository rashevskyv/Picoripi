"""Tag manager of the Senran Kagura Burst plugin: ``{v02001}`` (voice), ``{b008}``, ``{s022}``, ``{cff0000ff}``, ``{r}``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .tams import TAG_RE


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
