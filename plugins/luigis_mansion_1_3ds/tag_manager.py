"""Tags of Luigi's Mansion (3DS): the GMSG control tags of the Ever Oasis grammar (``{clear}``, ``{cNN}``, ...)."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager
from plugins.luigis_mansion_1_3ds.gmsg import TAG_RE


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
