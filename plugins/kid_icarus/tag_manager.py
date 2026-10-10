"""Tag manager of the Kid Icarus: Uprising plugin: a tag is legitimate when it encodes to an MSBT tag."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from . import tags


class TagManager(GenericTagManager):
    """``{Name:args}`` tags of the LMS System group and raw ``{tag:G:T:hex}`` tags."""

    def get_legitimate_tags(self) -> Set[str]:
        return {tags.TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        if not isinstance(tag_to_check, str):
            return False
        try:
            tags.parse_tag(tag_to_check)
        except ValueError:
            return False
        return True
