"""Tags of Monster Hunter Stories (Switch) messages: ``<COL ..>``, ``<SPNM ..>``, ``<PAGE>``, ``<ICON ..>`` and friends."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

TAG_RE = re.compile(r"<[A-Z/][^<>\n]{0,40}>|%[0-9]*[sdcxXf]")


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
