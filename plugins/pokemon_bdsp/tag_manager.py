"""Tag manager of the Pokémon Brilliant Diamond / Shining Pearl plugin: a tag is legitimate when it encodes back."""
import re
from typing import Set

from plugins.common.series_tags import TagMap, body_kind
from plugins.common.tag_manager import GenericTagManager

from .msg import TAG_RE, parse_tag


class TagManager(GenericTagManager):
    """``{tag:…}``, ``{scroll}``, ``{clear}``, ``{wait:…}``, ``{event:…}`` and TextMesh Pro rich-text tags."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        if not isinstance(tag_to_check, str) or not TAG_RE.fullmatch(tag_to_check):
            return False
        if tag_to_check.startswith("{tag:"):
            try:
                parse_tag(tag_to_check)
            except ValueError:
                return False
        return True


def _series_kind(tag: str) -> str:
    """Series kinds of the codec's tags: ``{scroll}``, ``{clear}`` (a new window), ``{wait:…}``, colour pairs."""
    if tag == "{scroll}":
        return "scroll"
    if tag == "{clear}":
        return "page"
    if tag.startswith("{wait:"):
        return "wait"
    if re.fullmatch(r"<color(=[^<>]*)?>", tag):
        return "colour:open"
    if tag == "</color>":
        return "colour:close"
    return body_kind(tag)


SERIES_TAG_MAP = TagMap(name="bdsp", pattern=TAG_RE, kind_of=_series_kind)
