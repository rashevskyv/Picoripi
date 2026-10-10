"""Ace Attorney Trilogy (3DS) message tags: ``{page}``, ``{wait:N}`` and ``{xNNN}`` (a game character with no letter)."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

TAG_RE = re.compile(r"\{(?:page|wait:\d+|x[0-9a-fA-F]{1,4})\}")


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
