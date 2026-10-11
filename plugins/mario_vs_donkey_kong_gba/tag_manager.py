"""Tag manager of the Mario vs. Donkey Kong (GBA) plugin: a raw ROM byte that is not ASCII is ``{XX}``."""
import re

from plugins.common.tag_manager import GenericTagManager

GAME_TAG = re.compile(r"\{[0-9A-F]{2}\}")


class TagManager(GenericTagManager):
    """Curly hex tags are raw bytes of the ROM string; ``{7B}`` and ``{7D}`` are the braces themselves."""

    def is_tag_legitimate(self, tag: str) -> bool:
        return isinstance(tag, str) and bool(GAME_TAG.fullmatch(tag))
