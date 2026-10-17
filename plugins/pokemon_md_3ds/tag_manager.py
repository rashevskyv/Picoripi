"""Tag manager of the plugin template."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager
from core.tag_utils import ANY_NON_EMPTY_TAG_CAPTURE_PATTERN as TAG_RE
from plugins.common.series_tags import TagMap, body_kind
from .message import TAG_RE as MESSAGE_TAG_RE


class TagManager(GenericTagManager):
    """Baseline tag manager for new plugin projects."""

    def get_legitimate_tags(self) -> Set[str]:
        return {r"\[[^\]]+\]", r"\{[^}]+\}"}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        if not isinstance(tag_to_check, str):
            return False
        return bool(TAG_RE.fullmatch(tag_to_check))


# Series kinds: the square-bracket commands of the message files; each keeps its body (no common kind yet).
SERIES_TAG_MAP = TagMap(name="md_3ds", pattern=MESSAGE_TAG_RE, kind_of=body_kind)
