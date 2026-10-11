"""Tags of One Piece: Unlimited World Red: ``{c:RRGGBB..}`` colour / reset commands and ``{u:XXXX}`` characters."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

TAG_RE = re.compile(r"\{[cu]:[0-9A-Fa-f]*\}")


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
