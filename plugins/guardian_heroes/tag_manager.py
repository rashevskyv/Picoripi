"""Tag manager of the Guardian Heroes plugin: the script's control words, written ``{F900}`` or ``{E100:0039}``."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

CONTROL_TAG = re.compile(r"\{[0-9A-Fa-f]{4}(?::[0-9A-Fa-f]{4})?\}")


class TagManager(GenericTagManager):
    """A control word is a tag; nothing else in braces is legitimate."""

    def get_legitimate_tags(self) -> Set[str]:
        return {CONTROL_TAG.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(CONTROL_TAG.fullmatch(tag_to_check))
