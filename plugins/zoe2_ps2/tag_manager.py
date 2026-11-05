"""Tags of Zone of the Enders: The 2nd Runner: a control byte ``{0A}`` or a two-byte code ``{83:02}`` of a script string."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

CODE = re.compile(r"\{[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2})?\}")


class TagManager(GenericTagManager):
    """The tags of the stage scripts: the bytes the editor cannot show as characters."""

    def get_legitimate_tags(self) -> Set[str]:
        return {CODE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(CODE.fullmatch(tag_to_check))
