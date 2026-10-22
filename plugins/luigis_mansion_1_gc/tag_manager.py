"""Tags of Luigi's Mansion (GameCube): ``<TAG>`` and ``<TAG>(n)``, for example ``<COLOR>(3)`` and ``<COLOR>(0)``."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

TAG_RE = re.compile(r"<[A-Z][A-Z0-9_]*>(?:\([^()\n]*\))?")


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
