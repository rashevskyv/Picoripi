"""Tag manager of the Ever Oasis plugin: a tag is legitimate when it is one of the GMSG control tags."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .gmsg import TAG_RE


class TagManager(GenericTagManager):
    """``{clear}``, ``{wait}``, ``{style:hex}``, ``{cNN}``, ``{cNN:hex}``, ``{cNN:text}``, ``{raw:hex}``."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
