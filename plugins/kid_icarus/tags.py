"""Kid Icarus: Uprising MSBT control tags: the editor codec.

The game's message project (``eu/00.arc/resident/01.bin``) names colours only, no tag groups, so the catalogue
is the standard LMS ``System`` group as the retail English text uses it: ``{Size:N}`` (text size in percent)
and ``{Color:R:G:B:A}`` (a direct RGBA colour, used twice in the SpotPass messages), plus ``{Ruby}``,
``{Font}`` and ``{PageBreak}`` for completeness. Anything else stays raw ``{tag:G:T:hex}`` and still
round-trips byte for byte.
"""
from __future__ import annotations

from plugins.common.lms_tags import TAG_RE, TagCodec  # noqa: F401 - TAG_RE is this module's API

TAGS = {
    (0, 0): ("Ruby", ("u16", "str"), "Ruby text drawn above the next N bytes of text"),
    (0, 1): ("Font", ("u16",), "Switch the font"),
    (0, 2): ("Size", ("u16",), "Text size in percent"),
    (0, 3): ("Color", ("u8", "u8", "u8", "u8"), "Text colour as red, green, blue, alpha (0-255)"),
    (0, 4): ("PageBreak", (), "Start a new page"),
}

CODEC = TagCodec(TAGS)
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
describe = CODEC.describe
parse_tag = CODEC.parse_tag
