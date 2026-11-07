"""Ocarina of Time (Switch 2) control tags: TotK's catalogue with the argument layouts of this game's UTF-8 text.

Measured on the English text (every layout below re-encodes each tag of the game to the same bytes; a tag that
does not stays raw, ``{tag:G:T:hex}``): a voice clip name is followed by one byte; the expression tag (3:0) has
three bytes; an inserted value (group 2) is a variable name, an s16 and, for some types, flags. The expression
numbers stay numbers: TotK's expression names do not match this game's values.
"""
from __future__ import annotations

from plugins.common.lms_tags import TagCodec
from plugins.zelda_totk import tags as totk

_VALUE = ("str", "s16")
_FLAGGED = ("str", "s16", "bool")
TAGS = {
    **totk.TAGS,
    (3, 0): ("emotion", ("u8", "bool", "u8"), "Speaker's facial expression (number, voice flag, extra byte)"),
    (4, 0): ("voice", ("str", "u8"), "Voice clip"),
    **{(2, kind): (f"value{kind}", layout, "Inserted value (the game's variable name)")
       for kind, layout in ((1, _FLAGGED), (3, _VALUE), (4, _FLAGGED), (5, _FLAGGED), (6, _FLAGGED),
                            (7, ("str", "s16", "bool", "bool")), (10, _FLAGGED), (12, _VALUE), (15, _VALUE),
                            (19, _VALUE), (20, _VALUE), (22, _VALUE), (23, _VALUE), (24, _VALUE))},
}
VALUE_NAMES = {key: names for key, names in totk.VALUE_NAMES.items() if key[0] != "emotion"}
# TotK's names of the replaced entries still read, so text saved before this catalogue loads
CODEC = TagCodec(TAGS, VALUE_NAMES, {totk.TAGS[key][0]: key for key in TAGS.keys() & totk.TAGS.keys()
                                     if TAGS[key][0] != totk.TAGS[key][0]})
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
