"""Dragon Quest Monsters: Joker 3 tags: control characters shown as ``{01}`` and ``[...]`` codes."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

TAG_RE = re.compile(r"\{[0-9A-F]{2}\}|\[[^\]\n]*\]|%[0-9A-Za-z]")


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
