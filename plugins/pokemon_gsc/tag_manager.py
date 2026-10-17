"""Tag manager of the Pokémon Gold, Silver and Crystal (pret) plugin: [line]-style commands, [text_ram ...]
text commands, charmap names (<PLAYER>) and rgbasm interpolations ({d:VALUE})."""
import re
from typing import Set

from plugins.common.series_tags import TagMap, kind_by_name
from plugins.common.tag_manager import GenericTagManager

from .pret_text import COMMAND_TAG_RE, CONTROL_TAG_RE

_PATTERNS = (COMMAND_TAG_RE.pattern, CONTROL_TAG_RE.pattern, r"<[^<>\s]+>", r"\{[^{}]+\}")


class TagManager(GenericTagManager):
    """The editor tags of pret text (see ``pret_text``) are legitimate tags."""

    def get_legitimate_tags(self) -> Set[str]:
        return set(_PATTERNS)

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and any(re.fullmatch(p, tag_to_check) for p in _PATTERNS)


# Series kinds (plugins/common/series_tags.py): the pret commands that gen 1 and gen 2 share (see pokemon_gen1).
_SERIES_NAMES = {"line": "line", "next": "line", "cont": "scroll", "para": "page", "page": "page"}
SERIES_TAG_MAP = TagMap(
    name="gsc",
    pattern=re.compile("|".join(f"(?:{p})" for p in _PATTERNS)),
    kind_of=lambda tag: kind_by_name(tag, _SERIES_NAMES),
)
