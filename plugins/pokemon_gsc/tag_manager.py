"""Tag manager of the Pokémon Gold, Silver and Crystal (pret) plugin: [line]-style commands, [text_ram ...]
text commands, charmap names (<PLAYER>) and rgbasm interpolations ({d:VALUE})."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

from .pret_text import COMMAND_TAG_RE, CONTROL_TAG_RE

_PATTERNS = (COMMAND_TAG_RE.pattern, CONTROL_TAG_RE.pattern, r"<[^<>\s]+>", r"\{[^{}]+\}")


class TagManager(GenericTagManager):
    """The editor tags of pret text (see ``pret_text``) are legitimate tags."""

    def get_legitimate_tags(self) -> Set[str]:
        return set(_PATTERNS)

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and any(re.fullmatch(p, tag_to_check) for p in _PATTERNS)
