"""Tag manager of the Yo-kai Watch plugin: the game's ``<...>`` codes shown as ``{...}`` (``tags.py``)."""
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .tags import TAG_RE


class TagManager(GenericTagManager):
    """``{PAGE}``, ``{CR}``...``{/C}``, ``{PNAME01}``, ``{SEL2/1/3}``, ``[g_coin]``..."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None
