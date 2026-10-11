"""Tag manager of the Digimon World: Re:Digitize Decode plugin: ``{c:XXXX}`` control units of the text."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .btxt import TAG_RE


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
