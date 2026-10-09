"""Tag manager of the Circle of the Moon plugin: control codes as ``{02}`` or ``{1D 44}`` (code + argument)."""
import re

from plugins.common.tag_manager import GenericTagManager

GAME_TAG = re.compile(r"\{[0-9A-F]{2}(?: [0-9A-F]{2})?\}")


class TagManager(GenericTagManager):
    """Curly hex tags are the game's control codes; square brackets are plain letters in this game."""

    def is_tag_legitimate(self, tag: str) -> bool:
        return isinstance(tag, str) and bool(GAME_TAG.fullmatch(tag))
