"""Tag manager of the Pokémon (Switch) plugin: the ``{PAGE}``, ``{VAR 0100 0000}``, ``{CHAR E305}`` tags of ``gfmsg``."""
from typing import Set

from plugins.common.gfmsg import TAG_RE
from plugins.common.tag_manager import GenericTagManager


class TagManager(GenericTagManager):
    """The game's commands, grammar branches and special characters (``plugins/common/gfmsg.py``) are legitimate."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
