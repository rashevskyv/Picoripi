"""Donkey Kong Country: Tropical Freeze MSBT control tags (none in the USEN text; the codec keeps any that appear)."""
from __future__ import annotations

from typing import Dict, Tuple

from plugins.common.lms_tags import TAG_RE, TagCodec  # noqa: F401 - TAG_RE is this module's API

# No control tag occurs in the USEN tables of the three text packages (checked on the base game and the mod).
TAGS: Dict[Tuple[int, int], Tuple[str, Tuple[str, ...], str]] = {}
CODEC = TagCodec(TAGS, {})
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
describe = CODEC.describe
parse_tag = CODEC.parse_tag
