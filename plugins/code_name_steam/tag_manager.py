"""Code Name: S.T.E.A.M. control codes kept in the text: ``$Ap$<icon>,`` (button / gear icons), ``$Arg$N,``
(a run-time number) and ``%NAME`` placeholders (``%USER``, ``%TITLE``, ``%TOURNAMENT``)."""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

TAG_RE = re.compile(r"\$[A-Za-z]+\$[^,\n$]*,|%[A-Z_]{2,}")


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check))
