"""Fire Emblem Awakening control codes: ``$`` codes kept in the text (``$k``, ``$Wmクロム|0``, ``$E通常,|``...)."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

# a code: $ + letters, then either an argument ended by | (speaker, voice, expression) or a digit
TAG_RE = re.compile(r"\$(?:W[msd][^$|\n]*\|\d*|Wa|E[^$|\n]*\|?|S[a-z]{1,2}[^$|\n]*\|?|[a-zA-Z]\d*\|?)")


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern, r"\{[^}]+\}"}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
