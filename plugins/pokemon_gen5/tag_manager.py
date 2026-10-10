"""Tag manager of the Pokémon Black / White (DS) plugin: the ``{PAGE}``, ``{VAR 0101 0000}``, ``{CHAR E447}`` tags
of ``gen5msg``."""
from typing import Set

from plugins.common.gen5msg import TAG_RE
from plugins.common.tag_manager import GenericTagManager


class TagManager(GenericTagManager):
    """The game's commands and special characters (``plugins/common/gen5msg.py``) are legitimate."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
