"""Tag manager of the Symphony of the Night plugin: raw bytes ``{8F}`` / ``{8168}`` and script commands ``{WAIT 30}``."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

TAG_PATTERN = r"\{(?:[0-9A-F]{2}|[0-9A-F]{4}|[A-Z][A-Z0-9]*(?: [0-9a-f]+)*)\}"
_TAG_RE = re.compile(TAG_PATTERN)


class TagManager(GenericTagManager):
    """Game codes the text codec does not show as characters, and cutscene commands inside a line."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_PATTERN}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and _TAG_RE.fullmatch(tag_to_check) is not None
