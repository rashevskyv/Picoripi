"""Tag manager of the Gravity Falls plugin: ``[C:RRGGBBAA]``, ``[s:1.5]``, ``[actor:path]`` and ``[!TR]``."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

TAG_RE = re.compile(r"\[(?:C|s|actor):[^\[\]\n]*\]|\[!TR\]")


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
