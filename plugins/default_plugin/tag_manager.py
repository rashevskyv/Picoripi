import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager


TAG_RE = re.compile(r"(\[[^\]]+\]|\{[^}]+\})")


class TagManager(GenericTagManager):
    """Baseline tag manager for new plugin projects."""

    def get_legitimate_tags(self) -> Set[str]:
        return {r"\[[^\]]+\]", r"\{[^}]+\}"}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        if not isinstance(tag_to_check, str):
            return False
        return bool(TAG_RE.fullmatch(tag_to_check))

