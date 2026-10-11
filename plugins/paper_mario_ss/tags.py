"""Paper Mario: Sticker Star MSBT control tags: the editor codec.

The game ships no ``.msbp`` project, so the catalogue is read from the retail English text. Group 0 is the
standard LMS ``System`` group (``Ruby``, ``Font``, ``Size``, ``Color``, ``PageBreak``). The game's own groups
are named only where the text shows what they do: ``Icon`` (button and coin pictures such as ``mic_a``,
``mic_coin``: a picture name and four sizes), ``Choice`` (a menu such as ``yesno``), ``Variable`` (a value
name such as ``item``), ``Number`` (a ``%d`` style number) and ``Wait`` (milliseconds). Every other tag stays
raw ``{tag:G:T:hex}`` and still round-trips byte for byte.
"""
from __future__ import annotations

from plugins.common.lms_tags import TAG_RE, TagCodec  # noqa: F401 - TAG_RE is this module's API

TAGS = {
    (0, 0): ("Ruby", ("u16", "str"), "Ruby text drawn above the next N bytes of text"),
    (0, 1): ("Font", ("u16",), "Switch the font"),
    (0, 2): ("Size", ("u16",), "Text size in percent"),
    (0, 3): ("Color", ("u8", "u8", "u8", "u8"), "Text colour as red, green, blue, alpha (0-255)"),
    (0, 4): ("PageBreak", (), "Start a new page"),
    (2, 2): ("Icon", ("str", "u16", "u16", "u16", "u16"), "A picture in the text (mic_a = the A button, mic_coin = a coin)"),
    (3, 0): ("Choice", ("u16", "s16", "u16", "u16", "str"), "A choice menu named by the last argument (yesno, SHOP_SELECT_BUY ...)"),
    (3, 1): ("Variable", ("str",), "Insert a value by name (item = the sticker's name)"),
    (3, 2): ("Number", ("u16", "str"), "Insert a number; the text is a printf format (%d, %2d, %02d)"),
    (4, 4): ("Wait", ("u32",), "Wait N milliseconds, then close the message"),
}

CODEC = TagCodec(TAGS)
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
describe = CODEC.describe
parse_tag = CODEC.parse_tag
