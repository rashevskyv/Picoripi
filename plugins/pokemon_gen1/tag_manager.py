"""Tag manager of the Pokémon Red / Blue / Yellow plugin: {text commands} and <game codes>."""
import re
from typing import Set

from plugins.common.series_tags import TagMap, kind_by_name
from plugins.common.tag_manager import GenericTagManager
from core.tag_utils import ANY_NON_EMPTY_TAG_CAPTURE_PATTERN as TAG_RE


class TagManager(GenericTagManager):
    """Text commands in curly braces ({text_ram wStringBuffer}, {cont}) are legitimate tags."""

    def get_legitimate_tags(self) -> Set[str]:
        return {r"\{[^}]+\}"}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        if not isinstance(tag_to_check, str):
            return False
        return bool(TAG_RE.fullmatch(tag_to_check))


# Series kinds (plugins/common/series_tags.py): the commands pret uses for the same thing in gen 1 and gen 2.
_SERIES_NAMES = {"cont": "scroll", "para": "page", "page": "page", "line": "line", "next": "line"}
SERIES_TAG_MAP = TagMap(
    name="gen1",
    pattern=re.compile(r"\{[^{}]*\}|<[^<>]+>"),
    kind_of=lambda tag: kind_by_name(tag, _SERIES_NAMES),
)
