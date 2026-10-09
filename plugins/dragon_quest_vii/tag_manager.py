"""Dragon Quest VII control codes: ``{HERO}``-style names, ``%a00`` codes, ``%E``/``%Y`` grammar codes, ``{LF}``."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

TAG_RE = re.compile(r"\{[A-Za-z_0-9]+\}|%[a-zA-Z][0-9]{2}|%[A-Z]")


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
