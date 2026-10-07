"""Metroid Prime 4: Beyond MSBT control tags as readable ``{tags}`` (codec: ``plugins.common.lms_tags``).

Every tag the 1.1.0 English text uses (98 tables, 5792 messages):
  ``{size:N}`` (0, 2)   text size in percent       ``{color:R:G:B:A}`` (0, 3)  text colour
  ``{pageBreak}`` (0, 4) next page / subtitle part  ``{icon:N}`` (1, 0)        button or symbol icon
  ``{column}`` (1, 5)   jump to the next column (credits)
Metroid Prime Remastered (plugin ``metroid_prime_remastered``) also uses ``{image:TXTR_RStickIdle:1}`` (1, 1),
an inline picture by texture name; its (1, 3) tag stays raw.
``{name}`` placeholders such as ``{0}`` are plain text the game fills in, not tags.
"""
from __future__ import annotations

from typing import Dict, Tuple

from plugins.common.lms_tags import TAG_RE, TagCodec  # noqa: F401 - TAG_RE is this module's API

TAGS: Dict[Tuple[int, int], Tuple[str, Tuple[str, ...], str]] = {
    (0, 2): ("size", ("u16",), "Text size in percent"),
    (0, 3): ("color", ("u8", "u8", "u8", "u8"), "Text colour (red, green, blue, alpha); 0:0:0:255 = default"),
    (0, 4): ("pageBreak", (), "Starts a new page or subtitle part"),
    (1, 0): ("icon", ("u8",), "Button or symbol icon"),
    (1, 5): ("column", (), "Moves on to the next column (credits)"),
    (1, 1): ("image", ("str", "u16"), "Inline picture: the texture's name and a number (Prime Remastered)"),
}
CODEC = TagCodec(TAGS, {})
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
describe = CODEC.describe
parse_tag = CODEC.parse_tag
