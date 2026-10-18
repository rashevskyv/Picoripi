"""Tag manager of the Rock N' Roll Racing (SNES) plugin: the ``[XX]`` tags of ``rom_text`` (one byte each)."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

TAG_PATTERN = r"\[[0-9A-F]{2}\]"


class TagManager(GenericTagManager):
    """``[80]`` .. ``[8F]``: the tile codes the ROM draws as pictures, and a literal ``[`` (``[5B]``)."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_PATTERN}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and re.fullmatch(TAG_PATTERN, tag_to_check) is not None
