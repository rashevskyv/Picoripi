"""Tag manager of the Pokémon generation IV (pret) plugin: ``{STRVAR_1 1, 0}``-style codes and ``{\\r}`` / ``{\\f}``."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .ds_text import TAG_RE


class TagManager(GenericTagManager):
    """The game's text codes (``ds_text``) are legitimate tags."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
