"""Tags of Luigi's Mansion (GameCube): ``<TAG>`` and ``<TAG>(n)``, for example ``<COLOR>(3)`` and ``<COLOR>(0)``.

The files keep the game's form; the editor shows each tag in the app's tag form, ``{COLOR(3)}``, so the core treats
it as a tag (style, hide-tags mode, tag checks, zero width). ``to_editor`` and ``to_data`` convert both ways.
"""
import re
from typing import Set

from plugins.common.tag_manager import GenericTagManager

TAG_RE = re.compile(r"<[A-Z][A-Z0-9_]*>(?:\([^()\n]*\))?")
EDITOR_TAG_RE = re.compile(r"\{[A-Z][A-Z0-9_]*(?:\([^()\n]*\))?\}")
_DATA_PARTS = re.compile(r"<([A-Z][A-Z0-9_]*)>(\([^()\n]*\))?")
_EDITOR_PARTS = re.compile(r"\{([A-Z][A-Z0-9_]*)(\([^()\n]*\))?\}")


def to_editor(text: str) -> str:
    return _DATA_PARTS.sub(lambda m: "{%s%s}" % (m.group(1), m.group(2) or ""), text)


def to_data(text: str) -> str:
    return _EDITOR_PARTS.sub(lambda m: "<%s>%s" % (m.group(1), m.group(2) or ""), text)


class TagManager(GenericTagManager):
    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern, EDITOR_TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and bool(TAG_RE.fullmatch(tag_to_check) or EDITOR_TAG_RE.fullmatch(tag_to_check))
